"""
Download whole-mission NASA EOL tables into media/nasa_cache (one API call per
mission and table, in parallel). Missions that do not exist come back empty and
are cached as [] so they are not asked again.

    manage.py fetch_nasa_cache --missions ISS001-ISS080 --workers 8
    manage.py fetch_nasa_cache --missions ISS046 ISS057 --refresh frames
"""
import os
import re
import time

from decouple import config
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from georeferencing.management.commands.import_task_list import NasaCache, TABLES


def expand(tokens):
    out = []
    for t in tokens:
        m = re.fullmatch(r'(ISS|STS)(\d{3})-(?:ISS|STS)?(\d{3})', t)
        if m:
            out += [f'{m.group(1)}{i:03d}' for i in range(int(m.group(2)), int(m.group(3)) + 1)]
        else:
            out.append(t)
    return out


class Command(BaseCommand):
    help = 'Fill media/nasa_cache with whole-mission NASA tables.'

    def add_arguments(self, p):
        p.add_argument('--missions', nargs='+', required=True, help='e.g. ISS001-ISS080 or ISS046 ISS057')
        p.add_argument('--workers', type=int, default=6)
        p.add_argument('--refresh', nargs='*', default=[], choices=list(TABLES), help='tables to re-download even if cached')
        p.add_argument('--cache-dir', default=os.path.join(settings.MEDIA_ROOT, 'nasa_cache'))

    def handle(self, *args, **o):
        missions = expand(o['missions'])
        cache = NasaCache(o['cache_dir'], config('NASA_API_KEY'), log=lambda m: self.stdout.write(m))
        pending = [(m, t) for m in missions for t in TABLES if t in o['refresh'] or not os.path.exists(cache.path(m, t))]
        self.stdout.write(f'missions={len(missions)} tables_to_fetch={len(pending)} workers={o["workers"]} (~2.5 min per call)')
        t0 = time.time()
        cache.fetch_all(missions, workers=o['workers'], refresh_tables=tuple(o['refresh']))
        empty = sum(1 for m in missions if os.path.exists(cache.path(m, 'images')) and os.path.getsize(cache.path(m, 'images')) <= 2)
        self.stdout.write(f'FETCH_DONE in {(time.time() - t0) / 60:.0f} min; missions without photos: {empty}')
