"""
Auto-park photos the crowd says are not worth locating: at least --votes skip
reasons among not_night / no_city / bad_image (distinct users or sessions)
on an image with no DONE task → its PENDING tasks are removed and replicas=0.
Dry-run by default; run with --apply once the reasons prove reliable.

    manage.py park_by_votes [--votes 2] [--apply]
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count, Q

from georeferencing.models import GeoAttempt, Image, SkipReason, StatsEvent


class Command(BaseCommand):
    help = 'Park photos with enough "not night / no city / bad image" skip votes (dry-run unless --apply).'

    def add_arguments(self, p):
        p.add_argument('--votes', type=int, default=2)
        p.add_argument('--apply', action='store_true')

    def handle(self, *args, **o):
        votes = (SkipReason.objects.filter(reason__in=SkipReason.PARKING_REASONS)
                 .values('image_id').annotate(n=Count('id')).filter(n__gte=o['votes']))
        candidates = []
        for v in votes:
            img = Image.objects.filter(pk=v['image_id'], replicas__gt=0).first()
            if not img or GeoAttempt.objects.filter(image=img).exclude(status='PENDING').exists():
                continue
            top = (SkipReason.objects.filter(image=img, reason__in=SkipReason.PARKING_REASONS)
                   .values('reason').annotate(n=Count('id')).order_by('-n').first())
            candidates.append((img, v['n'], top['reason']))
        from collections import Counter
        self.stdout.write(f"candidates={len(candidates)} by_reason={dict(Counter(c[2] for c in candidates))} "
                          f"pending_tasks={GeoAttempt.objects.filter(image_id__in=[c[0].id for c in candidates], status='PENDING').count()}")
        for img, n, reason in candidates[:15]:
            self.stdout.write(f'  {img.name} votes={n} top={reason}')
        if not o['apply']:
            self.stdout.write('DRY RUN, nothing written'); return
        with transaction.atomic():
            ids = [c[0].id for c in candidates]
            GeoAttempt.objects.filter(image_id__in=ids, status='PENDING').delete()
            Image.objects.filter(id__in=ids).update(replicas=0)
            if ids:
                StatsEvent.objects.create(kind='batch', title=f'Parked {len(ids)} photos by skip votes',
                                          note=', '.join(f'{k}={v}' for k, v in Counter(c[2] for c in candidates).items()))
        self.stdout.write(f'APPLIED: parked {len(candidates)} images')
