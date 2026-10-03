"""
Import NASA photo lists (CSV) as a batch of images + tasks, using the NASA
EOL API as the source of truth and the CSV as a cross-check.

Why this and not the admin "LIST batch" flow: that flow makes 3-4 API calls
per photo and the API answers in ~2 minutes per call whatever the size of
the result. This command asks for each *mission* once per table (images,
nadir, camera, mlcoord, frames), in parallel, caches the answers on disk and
resolves every photo locally. Downloads run in a thread pool.

    manage.py import_task_list --batch "ISS057" --replicas 5 \
        --min-sun-elev -6 /path/nasa_ids_ISS057.csv [more.csv] [--dry-run]

CSV columns: a column containing the NASA id (ISS057-E-61) is required;
`lat`, `lon` (nadir) and `elev` (sun elevation) are used when present.
Re-running is safe: photos already in the database are skipped.
"""
import csv
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone as dt_tz

import requests
import urllib3.util.connection as _urllib3_conn
from decouple import config

# This host has an IPv6 address but no IPv6 route: connections to the NASA
# servers (dual-stack) hang in SYN-SENT until the timeout before falling back
# to IPv4. Force IPv4 for everything this process downloads.
_urllib3_conn.allowed_gai_family = lambda: __import__('socket').AF_INET
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from georeferencing.models import Batch, FailedImage, GeoAttempt, Image, StatsEvent
from georeferencing.tasks import CAMERA_CODES

API = 'https://eol.jsc.nasa.gov/SearchPhotos/PhotosDatabaseAPI/PhotosDatabaseAPI.pl'
ID_RE = re.compile(r'(ISS\d{3})-([A-Z])-(\d+)')
TABLES = {
    'images': ('images|mission|eq|{m}|images|directory|like|*large*', 'images|frame|images|filename|images|directory'),
    'nadir':  ('nadir|mission|eq|{m}',  'nadir|frame|nadir|lat|nadir|lon|nadir|pdate|nadir|ptime'),
    'camera': ('camera|mission|eq|{m}', 'camera|frame|camera|camera|camera|fclt'),
    'mlcoord': ('mlcoord|mission|eq|{m}', 'mlcoord|frame|mlcoord|lat|mlcoord|lon'),
    'frames': ('frames|mission|eq|{m}', 'frames|frame|frames|lat|frames|lon|frames|nlat|frames|nlon|frames|camera|frames|fclt|frames|pdate|frames|ptime'),
}


def parse_rows(paths):
    """→ {id: {'lat','lon','elev','fclt'}} (floats or None) from any CSV with an id column."""
    out = {}
    for path in paths:
        with open(path, newline='', encoding='utf-8', errors='replace') as fh:
            for row in csv.DictReader(fh):
                pid = None
                for v in row.values():
                    m = ID_RE.search(str(v or ''))
                    if m:
                        pid = m.group(0); break
                if not pid:
                    continue
                def f(k):
                    try:
                        return float(row.get(k)) if row.get(k) not in (None, '') else None
                    except ValueError:
                        return None
                out.setdefault(pid, {'lat': f('lat'), 'lon': f('lon'), 'elev': f('elev'), 'fclt': f('fclt')})
    return out


def parse_dt(pdate, ptime):
    try:
        return datetime.strptime(f'{pdate} {ptime}', '%Y%m%d %H%M%S').replace(tzinfo=dt_tz.utc)
    except (TypeError, ValueError):
        return None


class NasaCache:
    """Whole-mission table dumps on disk (media/nasa_cache/<mission>/<table>.json)."""

    def __init__(self, root, key, timeout=900, log=print):
        self.root, self.key, self.timeout, self.log = root, key, timeout, log
        os.makedirs(root, exist_ok=True)

    def path(self, mission, table):
        return os.path.join(self.root, mission, f'{table}.json')

    def fetch(self, mission, table, force=False):
        p = self.path(mission, table)
        if not force and os.path.exists(p):
            with open(p, encoding='utf-8') as fh:
                return json.load(fh)
        q, ret = TABLES[table]
        t = time.time()
        r = requests.get(API, params={'query': q.format(m=mission), 'return': ret, 'key': self.key}, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, list):   # {"result": "SQL found no records..."}
            data = []
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'w', encoding='utf-8') as fh:
            json.dump(data, fh)
        self.log(f'  API {mission}/{table}: {len(data)} rows in {time.time() - t:.0f}s')
        return data

    def fetch_all(self, missions, workers=6, force=False):
        jobs = [(m, t) for m in missions for t in TABLES]
        with ThreadPoolExecutor(workers) as ex:
            futs = {ex.submit(self.fetch, m, t, force): (m, t) for m, t in jobs}
            for f in as_completed(futs):
                m, t = futs[f]
                try:
                    f.result()
                except Exception as e:
                    self.log(f'  API {m}/{t} FAILED: {type(e).__name__}: {e}')

    def index(self, mission):
        """{table: {frame(int): row}} for a mission (missing tables → {})."""
        out = {}
        for table in TABLES:
            try:
                rows = self.fetch(mission, table) if os.path.exists(self.path(mission, table)) else []
            except Exception:
                rows = []
            d = {}
            for r in rows:
                try:
                    d[int(r[f'{table}.frame'])] = r
                except (KeyError, TypeError, ValueError):
                    pass
            out[table] = d
        return out


def resolve(pid, idx):
    """Build the Image field dict for a NASA id from the cached mission tables.
    Returns (fields, reason) — fields None when the photo has no large file."""
    mission, roll, frame = ID_RE.match(pid).groups()
    frame = int(frame)
    img = idx['images'].get(frame)
    if not img:
        return None, 'NOT_FOUND'
    large = f"https://eol.jsc.nasa.gov/DatabaseImages/{img['images.directory']}/{img['images.filename']}"
    fields = {
        'name': img['images.filename'], 'largeImageURL': large, 'smallImageURL': large.replace('large', 'small'),
        'spacecraftNadirPoint': None, 'photoCenterPoint': None, 'photoCenterByMachineLearning': None,
        'camera': None, 'focalLength': None, 'taken': None,
    }
    nd = idx['nadir'].get(frame)
    fr = idx['frames'].get(frame)
    if nd:
        if nd.get('nadir.lat') not in (None, '') and nd.get('nadir.lon') not in (None, ''):
            fields['spacecraftNadirPoint'] = f"{nd['nadir.lat']}, {nd['nadir.lon']}"
        fields['taken'] = parse_dt(nd.get('nadir.pdate'), nd.get('nadir.ptime'))
    if fr:
        if fr.get('frames.lat') not in (None, '') and fr.get('frames.lon') not in (None, ''):
            fields['photoCenterPoint'] = f"{fr['frames.lat']}, {fr['frames.lon']}"
        if not fields['spacecraftNadirPoint'] and fr.get('frames.nlat') not in (None, ''):
            fields['spacecraftNadirPoint'] = f"{fr['frames.nlat']}, {fr['frames.nlon']}"
        code = fr.get('frames.camera')
        fields['camera'] = CAMERA_CODES.get(code, code) if code else None
        try:
            fields['focalLength'] = int(fr['frames.fclt'])
        except (KeyError, TypeError, ValueError):
            pass
        fields['taken'] = fields['taken'] or parse_dt(fr.get('frames.pdate'), fr.get('frames.ptime'))
    cam = idx['camera'].get(frame)
    if cam:
        fields['camera'] = fields['camera'] or cam.get('camera.camera')
        try:
            fields['focalLength'] = fields['focalLength'] or int(cam['camera.fclt'])
        except (KeyError, TypeError, ValueError):
            pass
    ml = idx['mlcoord'].get(frame)
    if ml and ml.get('mlcoord.lat') not in (None, ''):
        fields['photoCenterByMachineLearning'] = f"{ml['mlcoord.lat']}, {ml['mlcoord.lon']}"
    if not (fields['spacecraftNadirPoint'] or fields['photoCenterPoint']):
        return None, 'NO_COORDS'
    return fields, None


def _dl(url, subdir):
    """Download url into media/<subdir>/ unless already there. Returns True if the file is available."""
    name = os.path.basename(url)
    rel = os.path.join(subdir, name)
    if default_storage.exists(rel):
        return True
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=(10, 120))
            r.raise_for_status()
            default_storage.save(rel, ContentFile(r.content))
            return True
        except requests.RequestException:
            time.sleep(2 * (attempt + 1))
    return False


class Command(BaseCommand):
    help = 'Import NASA photo lists as a batch (API per mission, cached; CSV as cross-check).'

    def add_arguments(self, p):
        p.add_argument('csv', nargs='+')
        p.add_argument('--batch', required=True, help='Batch name (existing name → photos are added to it)')
        p.add_argument('--replicas', type=int, default=5)
        p.add_argument('--min-sun-elev', type=float, default=None,
                       help='Drop rows whose `elev` is above this (e.g. -6 keeps night only)')
        p.add_argument('--cache-dir', default=os.path.join(settings.MEDIA_ROOT, 'nasa_cache'))
        p.add_argument('--api-workers', type=int, default=6)
        p.add_argument('--download-workers', type=int, default=8)
        p.add_argument('--refresh-cache', action='store_true')
        p.add_argument('--fetch-only', action='store_true', help='Only fill the API cache, write nothing')
        p.add_argument('--dry-run', action='store_true')
        p.add_argument('--mismatch-deg', type=float, default=0.5, help='Report CSV vs API nadir gaps above this')

    def handle(self, *args, **o):
        log = lambda m: self.stdout.write(m)  # noqa: E731
        rows = parse_rows(o['csv'])
        if not rows:
            raise CommandError('No NASA ids found in the CSV files')
        total_rows = len(rows)
        if o['min_sun_elev'] is not None:
            rows = {k: v for k, v in rows.items() if v['elev'] is None or v['elev'] <= o['min_sun_elev']}
        dropped_day = total_rows - len(rows)
        existing = {}
        for name, status in Image.objects.values_list('name', 'status'):
            existing[re.sub(r'\.(jpg|jpeg)$', '', name, flags=re.I)] = status
        # Skip photos already fully imported; retry rows left PENDING / FAILED by
        # an interrupted run (their files and tasks are (re)created below).
        todo = [pid for pid in rows if existing.get(pid) in (None, 'PENDING', 'FAILED_DOWNLOADED')]
        retry = sum(1 for pid in todo if pid in existing)
        missions = sorted({ID_RE.match(p).group(1) for p in todo})
        log(f'rows={total_rows} dropped_daylight={dropped_day} already_in_db={len(rows) - len(todo)} to_import={len(todo)} (retrying {retry} incomplete) missions={missions}')
        if not todo:
            return

        cache = NasaCache(o['cache_dir'], config('NASA_API_KEY'), log=log)
        missing = [(m, t) for m in missions for t in TABLES if not os.path.exists(cache.path(m, t))]
        if missing or o['refresh_cache']:
            log(f'fetching {len(missing) if not o["refresh_cache"] else len(missions) * len(TABLES)} mission tables from the API ({o["api_workers"]} in parallel, ~2.5 min each)…')
            cache.fetch_all(missions, workers=o['api_workers'], force=o['refresh_cache'])
        if o['fetch_only']:
            return

        # Resolve locally
        indexes = {m: cache.index(m) for m in missions}
        resolved, failures, mismatches = {}, {}, []
        for pid in todo:
            fields, reason = resolve(pid, indexes[ID_RE.match(pid).group(1)])
            if fields is None:
                failures[pid] = reason
                continue
            csvrow = rows[pid]
            if csvrow['lat'] is not None and fields['spacecraftNadirPoint']:
                alat, alon = (float(x) for x in fields['spacecraftNadirPoint'].split(','))
                if abs(alat - csvrow['lat']) > o['mismatch_deg'] or abs(alon - csvrow['lon']) > o['mismatch_deg']:
                    mismatches.append((pid, (csvrow['lat'], csvrow['lon']), (alat, alon)))
            if fields['focalLength'] is None and csvrow['fclt']:
                fields['focalLength'] = int(csvrow['fclt'])
            resolved[pid] = fields
        log(f'resolved={len(resolved)} unresolved={len(failures)} csv/api nadir mismatches={len(mismatches)}')
        for pid, c, a in mismatches[:15]:
            log(f'  mismatch {pid}: csv={c} api={a}')
        for reason in set(failures.values()):
            log(f'  {reason}: {sum(1 for r in failures.values() if r == reason)} e.g. {[p for p, r in failures.items() if r == reason][:5]}')
        if o['dry_run']:
            log('dry run, nothing written')
            return

        # Batch
        owner = get_user_model().objects.filter(is_staff=True).order_by('id').first()
        batch, created = Batch.objects.get_or_create(
            name=o['batch'], defaults={'type': 'LIST', 'user': owner, 'replicas': o['replicas'], 'originalImages': ''})
        listed = set(re.findall(r'ISS\d{3}-E-\d+', batch.originalImages or ''))
        batch.originalImages = '\n'.join(sorted(listed | set(todo)))
        batch.processing_status = 'PROCESSING'
        batch.processing_start_time = batch.processing_start_time or timezone.now()
        batch.total_images_in_queue = len(listed | set(todo))
        batch.save()
        for pid, reason in failures.items():
            FailedImage.objects.update_or_create(batch=batch, name=pid, defaults={'reason': reason, 'detail': 'import_task_list'})

        # Create images, download, create tasks
        def do_one(pid):
            f = resolved[pid]
            img, _created = Image.objects.get_or_create(name=f['name'], defaults=dict(
                taken=f['taken'], focalLength=f['focalLength'] or 0, camera=(f['camera'] or '')[:100] or None,
                spacecraftNadirPoint=f['spacecraftNadirPoint'], photoCenterPoint=f['photoCenterPoint'],
                photoCenterByMachineLearning=f['photoCenterByMachineLearning'],
                largeImageURL=f['largeImageURL'], smallImageURL=f['smallImageURL'],
                batch=batch, replicas=o['replicas'], status='PENDING'))
            if GeoAttempt.objects.filter(image=img).exists() and img.status == 'DOWNLOADED_GENERATED':
                return pid, True
            ok_l = _dl(f['largeImageURL'], 'original')
            ok_s = _dl(f['smallImageURL'], 'small')
            if not (ok_l or ok_s):
                img.status = 'FAILED_DOWNLOADED'; img.save(update_fields=['status'])
                FailedImage.objects.update_or_create(batch=batch, name=pid, defaults={'reason': 'DOWNLOAD_FAILED', 'detail': f['largeImageURL']})
                return pid, False
            GeoAttempt.objects.filter(image=img, status='PENDING').delete()  # from an interrupted run
            for _ in range(o['replicas']):
                GeoAttempt.objects.create(image=img, status='PENDING')
            img.status = 'DOWNLOADED_GENERATED'; img.save(update_fields=['status'])
            FailedImage.objects.filter(batch=batch, name=pid).delete()
            return pid, True

        ok = bad = 0
        errors = []
        t0 = time.time()
        with ThreadPoolExecutor(o['download_workers']) as ex:
            futs = [ex.submit(self._wrap, do_one, pid, errors) for pid in resolved]
            for i, fut in enumerate(as_completed(futs), 1):
                pid, good = fut.result()
                ok += good; bad += (not good)
                if i % 50 == 0 or i == len(futs):
                    log(f'  {i}/{len(futs)} ok={ok} failed={bad} {time.time() - t0:.0f}s')
        batch.numberImages = Image.objects.filter(batch=batch).count()
        batch.processed_images_in_queue = batch.total_images_in_queue
        batch.processing_status = 'COMPLETED'
        batch.processing_end_time = timezone.now()
        batch.save()
        StatsEvent.objects.create(
            kind='batch', title=f'Photo set loaded: {batch.name}',
            note=f'import_task_list: {ok} images imported ({bad} download failures, {len(failures)} unresolved, '
                 f'{dropped_day} daylight rows dropped, {len(mismatches)} csv/api mismatches), replicas={o["replicas"]}.',
            url=f'/admin/georeferencing/batch/{batch.id}/change/', created_by=owner)
        # Challenge scope is evaluated live, but the cached image/task counts shown
        # in the join modal and admin are not: refresh them for open challenges.
        try:
            from georeferencing.models import Challenge
            refreshed = 0
            for ch in Challenge.objects.all():
                if ch.status != 'finished':
                    ch.cached_image_count, ch.cached_task_count = ch.compute_counts()
                    ch.save(update_fields=['cached_image_count', 'cached_task_count'])
                    refreshed += 1
            log(f'refreshed cached counts on {refreshed} open challenge(s)')
        except Exception as e:
            log(f'could not refresh challenge counts: {e}')
        log(f'DONE batch #{batch.id} {batch.name}: imported={ok} download_failed={bad} unresolved={len(failures)}')

        for pid, err in errors[:10]:
            log(f'  error {pid}: {err}')

    @staticmethod
    def _wrap(fn, pid, errors):
        from django.db import connection
        try:
            return fn(pid)
        except Exception as e:  # keep the pool alive; report per photo
            errors.append((pid, f'{type(e).__name__}: {e}'))
            return pid, False
        finally:
            connection.close()
