"""
Fill metadata gaps on existing Image rows from the cached NASA mission tables
(media/nasa_cache, written by import_task_list). Never overwrites a value that
is already set; only fills NULL/empty camera, taken, nadir, photo centre, ML
centre and focal length. Dry-run by default.

    manage.py enrich_images                 # report what would be filled
    manage.py enrich_images --apply
    manage.py enrich_images --apply --fetch # also download missing mission tables
"""
import os

from decouple import config
from django.conf import settings
from django.core.management.base import BaseCommand

from georeferencing.management.commands.import_task_list import ID_RE, NasaCache, TABLES, resolve
from georeferencing.models import Image

FIELDS = ('camera', 'taken', 'spacecraftNadirPoint', 'photoCenterPoint', 'photoCenterByMachineLearning', 'focalLength')


class Command(BaseCommand):
    help = 'Fill NULL metadata on existing images from the cached NASA mission tables.'

    def add_arguments(self, p):
        p.add_argument('--apply', action='store_true')
        p.add_argument('--fetch', action='store_true', help='Fetch missing mission tables from the API first')
        p.add_argument('--cache-dir', default=os.path.join(settings.MEDIA_ROOT, 'nasa_cache'))
        p.add_argument('--api-workers', type=int, default=6)

    def handle(self, *args, **o):
        log = self.stdout.write
        cache = NasaCache(o['cache_dir'], config('NASA_API_KEY'), log=log)
        by_mission = {}
        for img in Image.objects.all().only('id', 'name', *FIELDS):
            m = ID_RE.search(img.name or '')
            if m:
                by_mission.setdefault(m.group(1), []).append(img)
        missions = sorted(by_mission)
        cached = [m for m in missions if all(os.path.exists(cache.path(m, t)) for t in TABLES)]
        if o['fetch']:
            cache.fetch_all([m for m in missions if m not in cached], workers=o['api_workers'])
            cached = [m for m in missions if all(os.path.exists(cache.path(m, t)) for t in TABLES)]
        log(f'images={sum(len(v) for v in by_mission.values())} missions={len(missions)} cached={len(cached)} '
            f'not_cached={[m for m in missions if m not in cached]}')
        filled = {f: 0 for f in FIELDS}
        touched = 0
        for m in cached:
            idx = cache.index(m)
            for img in by_mission[m]:
                pid = ID_RE.search(img.name).group(0)
                fields, reason = resolve(pid, idx)
                if not fields:
                    continue
                changed = []
                for f in FIELDS:
                    cur = getattr(img, f)
                    new = fields.get(f)
                    if (cur in (None, '', 0) and f != 'focalLength' or (f == 'focalLength' and not cur)) and new not in (None, ''):
                        setattr(img, f, new if f != 'camera' else str(new)[:100])
                        changed.append(f)
                if changed:
                    touched += 1
                    for f in changed:
                        filled[f] += 1
                    if o['apply']:
                        img.save()  # save() recomputes photoCenterLat/Lon
        mode = 'APPLIED' if o['apply'] else 'DRY RUN'
        log(f'[{mode}] images_touched={touched} ' + ' '.join(f'{k}={v}' for k, v in filled.items()))
