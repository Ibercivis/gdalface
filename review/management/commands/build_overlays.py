"""
Build the map overlays (warped WebP + footprint) for DONE attempts.

    manage.py build_overlays                  # everything missing or out of date
    manage.py build_overlays --attempt 12 13  # specific attempts
    manage.py build_overlays --limit 50 --workers 6
    manage.py build_overlays --force          # rebuild even if up to date
    manage.py build_overlays --retry-failed

Rendering runs GDAL in a thread pool (subprocesses); database writes stay in the
main thread.
"""
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.core.management.base import BaseCommand

from georeferencing.models import GeoAttempt
from review import build


class Command(BaseCommand):
    help = 'Build map overlays for finished georeferencing attempts.'

    def add_arguments(self, parser):
        parser.add_argument('--attempt', type=int, nargs='*', help='only these geoattempt ids')
        parser.add_argument('--limit', type=int, default=0)
        parser.add_argument('--workers', type=int, default=6)
        parser.add_argument('--force', action='store_true')
        parser.add_argument('--retry-failed', action='store_true')

    def handle(self, *args, **opts):
        qs = GeoAttempt.objects.filter(status='DONE').select_related('image', 'overlay').order_by('id')
        if opts['attempt']:
            qs = qs.filter(pk__in=opts['attempt'])
        todo = []
        for ga in qs.iterator(chunk_size=500):
            job = build.plan(ga, force=opts['force'], retry_failed=opts['retry_failed'])
            if job:
                todo.append((ga, *job))
                if opts['limit'] and len(todo) >= opts['limit']:
                    break
        self.stdout.write(f'{len(todo)} attempts to build')
        counts = {'ok': 0, 'skipped': 0, 'failed': 0}
        started = time.time()
        with ThreadPoolExecutor(max_workers=max(1, opts['workers'])) as pool:
            futures = {pool.submit(build.run, ga, points, rel): (ga, points, digest, rel)
                       for ga, points, digest, rel in todo}
            for i, fut in enumerate(as_completed(futures), 1):
                ga, points, digest, rel = futures[fut]
                status, payload = fut.result()
                build.store(ga, points, digest, rel, status, payload)
                counts[status] += 1
                if status == 'failed':
                    self.stderr.write(f'  attempt {ga.pk}: {payload}')
                if i % 100 == 0:
                    self.stdout.write(f'  {i}/{len(todo)} ({time.time() - started:.0f}s)')
        self.stdout.write(self.style.SUCCESS(
            f'done in {time.time() - started:.0f}s: {counts["ok"]} ok, {counts["skipped"]} skipped, {counts["failed"]} failed'))
