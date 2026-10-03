"""
Merge duplicate Image rows (same NASA file name) into one and repair statuses.

Duplicates come from re-running a batch with the old pipeline (2025) and from
two overlapping import runs (2026-10-03). Rule per duplicated name:
  primary = row with most DONE tasks, then most ASSIGNED, then DOWNLOADED_GENERATED,
            then lowest id.
  other rows: their DONE/ASSIGNED tasks are moved to the primary (volunteer work
            is never deleted), their PENDING tasks are dropped, the row is deleted.
Then: images marked PENDING that do have their files on disk become
DOWNLOADED_GENERATED, and every downloaded image ends with at least `replicas`
tasks. Dry-run by default; --apply writes. Take a pg_dump of
georeferencing_image / georeferencing_geoattempt first.
"""
import os

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count

from georeferencing.models import GeoAttempt, Image, StatsEvent


def _has_file(img):
    return os.path.exists(os.path.join('media', 'original', img.name)) or \
           os.path.exists(os.path.join('media', 'small', img.name))


class Command(BaseCommand):
    help = 'Merge duplicate Image rows and repair statuses (dry-run unless --apply).'

    def add_arguments(self, p):
        p.add_argument('--apply', action='store_true')

    def handle(self, *args, **o):
        apply = o['apply']
        log = self.stdout.write
        stats = dict(rows_removed=0, tasks_moved=0, pending_dropped=0, relabelled=0, tasks_created=0, topped_up=0)
        with transaction.atomic():
            dup_names = [d['name'] for d in Image.objects.values('name').annotate(n=Count('id')).filter(n__gt=1)]
            for name in dup_names:
                rows = list(Image.objects.filter(name=name).order_by('id'))

                def score(i):
                    t = GeoAttempt.objects.filter(image=i)
                    return (t.filter(status='DONE').count(), t.filter(status='ASSIGNED').count(),
                            1 if i.status == 'DOWNLOADED_GENERATED' else 0, -i.id)
                primary = max(rows, key=score)
                for dup in rows:
                    if dup.id == primary.id:
                        continue
                    keep = GeoAttempt.objects.filter(image=dup).exclude(status='PENDING')
                    drop = GeoAttempt.objects.filter(image=dup, status='PENDING')
                    stats['tasks_moved'] += keep.count()
                    stats['pending_dropped'] += drop.count()
                    stats['rows_removed'] += 1
                    if apply:
                        keep.update(image=primary)
                        drop.delete()
                        dup.delete()
            for img in Image.objects.filter(status='PENDING'):
                if _has_file(img):
                    stats['relabelled'] += 1
                    if apply:
                        img.status = 'DOWNLOADED_GENERATED'
                        img.save(update_fields=['status'])
                    if not GeoAttempt.objects.filter(image=img).exists():
                        n = img.replicas or 5
                        stats['tasks_created'] += n
                        if apply:
                            for _ in range(n):
                                GeoAttempt.objects.create(image=img, status='PENDING')
            if apply:
                for img in Image.objects.filter(status='DOWNLOADED_GENERATED').annotate(n=Count('geoattempt')).filter(n__lt=5):
                    for _ in range(5 - img.n):
                        GeoAttempt.objects.create(image=img, status='PENDING')
                        stats['topped_up'] += 1
                StatsEvent.objects.create(
                    kind='other', title=f"Image table de-duplicated: {stats['rows_removed']} rows merged, {stats['relabelled']} statuses repaired",
                    note=' '.join(f'{k}={v}' for k, v in stats.items()))
            if not apply:
                transaction.set_rollback(True)
        mode = 'APPLIED' if apply else 'DRY RUN'
        log(f"[{mode}] " + ' '.join(f'{k}={v}' for k, v in stats.items()))
        log(f"duplicate names now: {Image.objects.values('name').annotate(n=Count('id')).filter(n__gt=1).count()} | images: {Image.objects.count()}")
        if apply:
            from django.core.cache import cache
            from georeferencing import metrics
            metrics.invalidate()
            cache.delete_many(['map:located:v1:all'] + [f'staff_stats:v1:{d}' for d in (7, 30, 365, 1460)]
                              + [f'staff_series:v1:{r}' for r in ('7d', '30d', '1y', '4y')])
