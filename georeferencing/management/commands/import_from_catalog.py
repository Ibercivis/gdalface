"""
Populate Image (+ tasks, + files) from a selection of the NasaPhoto catalogue.

    manage.py import_from_catalog --batch "Brazil" --bbox -33.8 5.3 -74.0 -34.8 \
        --night --min-focal 50 --tiers A B C --dedup 0.5 [--limit 1000] [--dry-run]
    manage.py import_from_catalog --batch "ISS060" --missions ISS060 --night --min-focal 50

Selection runs on the catalogue (no API calls); downloads and task creation
reuse import_task_list's machinery. Photos already in Image are skipped.
"""
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from georeferencing.management.commands.import_task_list import _dl
from georeferencing.management.commands.sync_nasa_catalog import link_images
from georeferencing.models import Batch, GeoAttempt, Image, NasaPhoto, StatsEvent


def select(o):
    qs = NasaPhoto.objects.filter(has_large=True, image__isnull=True)
    if o.get('missions'):
        qs = qs.filter(mission__in=o['missions'])
    if o.get('night'):
        qs = qs.filter(night=True)
    if o.get('min_focal') is not None:
        qs = qs.filter(focal__gte=o['min_focal'])
    if o.get('tiers'):
        qs = qs.filter(tier__in=o['tiers'])
    if o.get('bbox'):
        s, n, w, e = o['bbox']
        # best available coordinate: centre > ML > nadir (same priority as Image)
        from django.db.models import Case, F, When, FloatField
        qs = qs.annotate(
            blat=Case(When(center_lat__isnull=False, then=F('center_lat')), When(ml_lat__isnull=False, then=F('ml_lat')), default=F('nadir_lat'), output_field=FloatField()),
            blon=Case(When(center_lon__isnull=False, then=F('center_lon')), When(ml_lon__isnull=False, then=F('ml_lon')), default=F('nadir_lon'), output_field=FloatField()),
        ).filter(blat__gte=s, blat__lte=n)
        qs = qs.filter(blon__gte=w, blon__lte=e) if w <= e else qs.filter(models_Q(blon__gte=w) | models_Q(blon__lte=e))
    if o.get('min_mission'):
        qs = qs.filter(mission__gte=o['min_mission'])
    rows = list(qs.order_by('mission', 'frame'))
    if o.get('dedup_seconds'):
        # Bursts / time-lapses: consecutive frames of a mission taken less than N
        # seconds apart form a sequence; keep the middle frame of each sequence.
        import math
        gap = o['dedup_seconds']; kept = []; seq = []
        overlap = o.get('overlap', 0.5)
        def km(a, b):
            la1, lo1, la2, lo2 = a.best_lat, a.best_lon, b.best_lat, b.best_lon
            return 1e9 if None in (la1, lo1, la2, lo2) else math.hypot(la2 - la1, (lo2 - lo1) * math.cos(math.radians(la1))) * 111
        def flush():
            # inside a burst keep one frame every half footprint (36 mm / focal × 420 km)
            last = None
            for p in seq:
                step = max(5.0, overlap * 36.0 / p.focal * 420.0) if (overlap and p.focal) else 50.0
                if last is None or km(last, p) >= step:
                    kept.append(p); last = p
        for p in rows:
            if seq and p.mission == seq[-1].mission and p.taken and seq[-1].taken \
                    and abs((p.taken - seq[-1].taken).total_seconds()) <= gap and p.focal == seq[-1].focal:
                seq.append(p)
            else:
                flush(); seq = [p]
        flush(); rows = kept
    if o.get('dedup'):
        cell = o['dedup']; seen = {}
        for p in rows:
            lat, lon = p.best_lat, p.best_lon
            key = (p.mission, round(lat / cell), round(lon / cell))
            seen.setdefault(key, p)
        rows = list(seen.values())
    if o.get('sample') == 'random':
        import random
        random.Random(o.get('seed', 42)).shuffle(rows)
    if o.get('limit'):
        rows = rows[:o['limit']]
    return rows


def models_Q(**kw):
    from django.db.models import Q
    return Q(**kw)


class Command(BaseCommand):
    help = 'Create a batch of images + tasks from a catalogue selection.'

    def add_arguments(self, p):
        p.add_argument('--batch', required=True)
        p.add_argument('--missions', nargs='*')
        p.add_argument('--night', action='store_true')
        p.add_argument('--min-focal', type=int, default=None)
        p.add_argument('--tiers', nargs='*', choices=['A', 'B', 'C', 'D'])
        p.add_argument('--bbox', nargs=4, type=float, metavar=('S', 'N', 'W', 'E'))
        p.add_argument('--dedup', type=float, default=None, help='keep one photo per mission per cell of this many degrees')
        p.add_argument('--dedup-seconds', type=float, default=None, help='collapse bursts: consecutive frames closer than N seconds form a sequence')
        p.add_argument('--overlap', type=float, default=0.5, help='inside a sequence keep one frame per this fraction of the footprint')
        p.add_argument('--min-mission', default=None, help='e.g. ISS030 to skip the early film-era missions')
        p.add_argument('--sample', choices=['random'], default=None, help='random order before --limit (stratifies the pick)')
        p.add_argument('--seed', type=int, default=42)
        p.add_argument('--limit', type=int, default=None)
        p.add_argument('--replicas', type=int, default=5)
        p.add_argument('--download-workers', type=int, default=8)
        p.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **o):
        log = self.stdout.write
        rows = select(o)
        from collections import Counter
        log(f'selected={len(rows)} by_mission={dict(Counter(r.mission for r in rows).most_common(8))} '
            f'tiers={dict(Counter(r.tier for r in rows))}')
        if not rows:
            return
        if o['dry_run']:
            log('dry run, nothing written'); return
        owner = get_user_model().objects.filter(is_staff=True).order_by('id').first()
        batch, _ = Batch.objects.get_or_create(name=o['batch'], defaults={'type': 'LIST', 'user': owner, 'replicas': o['replicas'], 'originalImages': ''})
        listed = set((batch.originalImages or '').split())
        batch.originalImages = '\n'.join(sorted(listed | {r.nasa_id for r in rows}))
        batch.processing_status = 'PROCESSING'; batch.processing_start_time = batch.processing_start_time or timezone.now()
        batch.total_images_in_queue = len(listed | {r.nasa_id for r in rows}); batch.save()

        def do_one(p):
            large = f'https://eol.jsc.nasa.gov/DatabaseImages/{p.directory}/{p.filename}'
            img, _c = Image.objects.get_or_create(name=p.filename, defaults=dict(
                taken=p.taken, focalLength=p.focal or 0, camera=p.camera[:100] or None,
                spacecraftNadirPoint=f'{p.nadir_lat}, {p.nadir_lon}' if p.nadir_lat is not None else None,
                photoCenterPoint=f'{p.center_lat}, {p.center_lon}' if p.center_lat is not None else None,
                photoCenterByMachineLearning=f'{p.ml_lat}, {p.ml_lon}' if p.ml_lat is not None else None,
                largeImageURL=large, smallImageURL=large.replace('large', 'small'),
                batch=batch, replicas=o['replicas'], status='PENDING', cameraTilt=None))
            if img.status == 'DOWNLOADED_GENERATED' and GeoAttempt.objects.filter(image=img).exists():
                return p.nasa_id, True
            if not (_dl(large, 'original') or _dl(large.replace('large', 'small'), 'small')):
                img.status = 'FAILED_DOWNLOADED'; img.save(update_fields=['status']); return p.nasa_id, False
            GeoAttempt.objects.filter(image=img, status='PENDING').delete()
            for _ in range(o['replicas']):
                GeoAttempt.objects.create(image=img, status='PENDING')
            img.status = 'DOWNLOADED_GENERATED'; img.save(update_fields=['status'])
            return p.nasa_id, True

        def wrap(p):
            from django.db import connection
            try:
                return do_one(p)
            except Exception as e:
                return p.nasa_id, f'{type(e).__name__}: {e}'
            finally:
                connection.close()

        ok = bad = 0; errors = []; t0 = time.time()
        with ThreadPoolExecutor(o['download_workers']) as ex:
            for i, fut in enumerate(as_completed([ex.submit(wrap, p) for p in rows]), 1):
                pid, res = fut.result()
                if res is True: ok += 1
                else:
                    bad += 1
                    if res is not False: errors.append((pid, res))
                if i % 50 == 0 or i == len(rows):
                    log(f'  {i}/{len(rows)} ok={ok} failed={bad} {time.time() - t0:.0f}s')
        for pid, err in errors[:10]:
            log(f'  error {pid}: {err}')
        batch.numberImages = Image.objects.filter(batch=batch).count()
        batch.processed_images_in_queue = batch.total_images_in_queue
        batch.processing_status = 'COMPLETED'; batch.processing_end_time = timezone.now(); batch.save()
        linked = link_images(sorted({r.mission for r in rows}))
        from georeferencing.models import Challenge
        for ch in Challenge.objects.all():
            if ch.status != 'finished':
                ch.cached_image_count, ch.cached_task_count = ch.compute_counts()
                ch.save(update_fields=['cached_image_count', 'cached_task_count'])
        StatsEvent.objects.create(kind='batch', title=f'Photo set loaded from catalogue: {batch.name}',
                                  note=f'{ok} images, {bad} failed, replicas={o["replicas"]}', url=f'/admin/georeferencing/batch/{batch.id}/change/', created_by=owner)
        log(f'DONE batch #{batch.id} {batch.name}: imported={ok} failed={bad} catalogue rows linked={linked}')
