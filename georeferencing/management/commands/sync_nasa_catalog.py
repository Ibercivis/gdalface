"""
Build / refresh the NasaPhoto catalogue from the cached mission tables.

    manage.py sync_nasa_catalog                 # every mission present in media/nasa_cache
    manage.py sync_nasa_catalog --missions ISS057 ISS046
    manage.py sync_nasa_catalog --link-only     # only refresh image links / done & pending counts

Per photo: file availability (images), nadir + time (nadir), catalogued centre,
tilt, features, cloud, NASA sun elevation, region (frames), camera + focal
(camera / frames), ML centre (mlcoord). Then computed: our sun elevation,
night (<= -6°), difficulty tier, link to our Image row and task counts.
"""
import json
import os
import re
from datetime import datetime, timezone as dt_tz

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count, Q

from georeferencing.management.commands.import_task_list import CAMERA_CODES, TABLES
from georeferencing.models import GeoAttempt, Image, NasaPhoto
from georeferencing.solar import sun_elevation

NIGHT_ELEV = -6.0
ID_RE = re.compile(r'(ISS\d{3})-([A-Z])-(\d+)')


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _i(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _dt(pdate, ptime):
    try:
        return datetime.strptime(f'{pdate} {ptime}', '%Y%m%d %H%M%S').replace(tzinfo=dt_tz.utc)
    except (TypeError, ValueError):
        return None


def tier_for(center_lat, ml_lat, nadir_lat, focal, tilt):
    if center_lat is not None:
        return 'A'
    if ml_lat is not None:
        return 'B'
    if nadir_lat is None:
        return ''
    if (focal or 0) >= 50 and tilt not in ('HO',):
        return 'C'
    return 'D'


def build_rows(mission, cache_dir):
    """Yield NasaPhoto instances (unsaved) for a cached mission."""
    def load(t):
        p = os.path.join(cache_dir, mission, f'{t}.json')
        return json.load(open(p)) if os.path.exists(p) else []
    by_frame = {}
    for r in load('images'):
        fr = _i(r.get('images.frame'))
        if fr is not None:
            by_frame.setdefault(fr, {})['img'] = r
    for t in ('nadir', 'camera', 'mlcoord', 'frames'):
        for r in load(t):
            fr = _i(r.get(f'{t}.frame'))
            if fr is not None:
                by_frame.setdefault(fr, {})[t] = r
    for fr, d in by_frame.items():
        img, nd, cam, ml, frm = d.get('img'), d.get('nadir'), d.get('camera'), d.get('mlcoord'), d.get('frames')
        nadir_lat = _f(nd and nd.get('nadir.lat')); nadir_lon = _f(nd and nd.get('nadir.lon'))
        if nadir_lat is None and frm:
            nadir_lat, nadir_lon = _f(frm.get('frames.nlat')), _f(frm.get('frames.nlon'))
        center_lat = _f(frm and frm.get('frames.lat')); center_lon = _f(frm and frm.get('frames.lon'))
        ml_lat = _f(ml and ml.get('mlcoord.lat')); ml_lon = _f(ml and ml.get('mlcoord.lon'))
        taken = (_dt(nd.get('nadir.pdate'), nd.get('nadir.ptime')) if nd else None) or \
                (_dt(frm.get('frames.pdate'), frm.get('frames.ptime')) if frm else None)
        focal = _i(cam and cam.get('camera.fclt')) or _i(frm and frm.get('frames.fclt'))
        camera = (cam and cam.get('camera.camera')) or (frm and CAMERA_CODES.get(frm.get('frames.camera'), frm.get('frames.camera'))) or ''
        tilt = (frm and frm.get('frames.tilt')) or ''
        lat_for_sun, lon_for_sun = (center_lat, center_lon) if center_lat is not None else (nadir_lat, nadir_lon)
        sun = sun_elevation(lat_for_sun, lon_for_sun, taken) if (taken and lat_for_sun is not None) else None
        yield NasaPhoto(
            mission=mission, roll='E', frame=fr,
            has_large=bool(img), filename=(img or {}).get('images.filename', '') or '',
            directory=(img or {}).get('images.directory', '') or '',
            nadir_lat=nadir_lat, nadir_lon=nadir_lon, center_lat=center_lat, center_lon=center_lon,
            ml_lat=ml_lat, ml_lon=ml_lon, taken=taken, camera=str(camera)[:100], focal=focal,
            tilt=str(tilt)[:4], features=str((frm or {}).get('frames.feat') or '')[:200],
            cloud_pct=_i(frm and frm.get('frames.cldp')), region=str((frm or {}).get('frames.geon') or '')[:120],
            sun_elev_nasa=_f(frm and frm.get('frames.elev')), sun_elev=sun,
            night=(sun is not None and sun <= NIGHT_ELEV), tier=tier_for(center_lat, ml_lat, nadir_lat, focal, tilt),
        )


def link_images(missions=None):
    """Point catalogue rows at our Image rows and refresh task counts."""
    qs = Image.objects.all()
    if missions:
        qs = qs.filter(name__regex=r'^(' + '|'.join(missions) + r')-')
    counts = {r['image_id']: r for r in GeoAttempt.objects.values('image_id').annotate(
        done=Count('id', filter=Q(status='DONE')), pending=Count('id', filter=Q(status='PENDING')))}
    linked = 0
    for img in qs.only('id', 'name'):
        m = ID_RE.search(img.name or '')
        if not m:
            continue
        c = counts.get(img.id, {})
        linked += NasaPhoto.objects.filter(mission=m.group(1), roll=m.group(2), frame=int(m.group(3))).update(
            image=img, done_count=c.get('done', 0), pending_count=c.get('pending', 0))
    return linked


class Command(BaseCommand):
    help = 'Build the NasaPhoto catalogue from media/nasa_cache.'

    def add_arguments(self, p):
        p.add_argument('--missions', nargs='*')
        p.add_argument('--link-only', action='store_true')
        p.add_argument('--cache-dir', default=os.path.join(settings.MEDIA_ROOT, 'nasa_cache'))

    def handle(self, *args, **o):
        cache_dir = o['cache_dir']
        missions = o['missions'] or sorted(
            d for d in os.listdir(cache_dir)
            if os.path.isdir(os.path.join(cache_dir, d)) and os.path.exists(os.path.join(cache_dir, d, 'images.json')))
        if not o['link_only']:
            total = 0
            for m in missions:
                rows = list(build_rows(m, cache_dir))
                with transaction.atomic():
                    NasaPhoto.objects.filter(mission=m).delete()
                    NasaPhoto.objects.bulk_create(rows, batch_size=5000)
                total += len(rows)
                self.stdout.write(f'  {m}: {len(rows)} photos, {sum(1 for r in rows if r.night)} night, '
                                  f'{sum(1 for r in rows if r.tier == "A")} catalogued')
            self.stdout.write(f'synced {len(missions)} missions, {total} photos')
        linked = link_images(missions)
        self.stdout.write(f'linked {linked} catalogue rows to our images; catalogue size {NasaPhoto.objects.count()}')
