"""
Create a new challenge from an existing one (same scope: batch + bbox +
description), with a fresh window and optional new targets.

    manage.py clone_challenge --from 6 --name "Europe 2026-27" --days 365 --gold 6000
    manage.py clone_challenge --from 4 --name "France 2026-27" --days 365          # keeps targets
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from georeferencing.models import Challenge, StatsEvent


class Command(BaseCommand):
    help = 'Clone a challenge (scope + description) into a new one with a fresh window.'

    def add_arguments(self, parser):
        parser.add_argument('--from', dest='source', type=int, required=True, help='Source challenge id')
        parser.add_argument('--name', required=True)
        parser.add_argument('--days', type=int, default=365, help='Duration from now (default 365)')
        parser.add_argument('--start-in', type=int, default=0, help='Days until start (default 0 = now)')
        parser.add_argument('--gold', type=int, help='Gold target; bronze/silver become 1/3 and 2/3 of it')
        parser.add_argument('--description', help='Override the description')
        parser.add_argument('--by', help='Username recorded as creator (default: first staff user)')

    def handle(self, *args, **o):
        try:
            src = Challenge.objects.get(pk=o['source'])
        except Challenge.DoesNotExist:
            raise CommandError(f"No challenge with id {o['source']}")
        if Challenge.objects.filter(name=o['name']).exists():
            raise CommandError(f"A challenge named {o['name']!r} already exists")
        User = get_user_model()
        by = User.objects.filter(username=o['by']).first() if o['by'] else User.objects.filter(is_staff=True).order_by('id').first()
        now = timezone.now()
        start = now + timedelta(days=o['start_in'])
        if o['gold']:
            gold = o['gold']; bronze, silver = round(gold / 3), round(gold * 2 / 3)
        else:
            bronze, silver, gold = src.target_bronze, src.target_silver, src.target_gold
        ch = Challenge.objects.create(
            name=o['name'], description=o['description'] if o['description'] is not None else src.description,
            batch=src.batch, start_at=start, end_at=start + timedelta(days=o['days']),
            target_bronze=bronze, target_silver=silver, target_gold=gold, created_by=by,
            bbox_min_lat=src.bbox_min_lat, bbox_max_lat=src.bbox_max_lat,
            bbox_min_lon=src.bbox_min_lon, bbox_max_lon=src.bbox_max_lon,
        )
        StatsEvent.objects.create(
            kind='challenge', title=f'Challenge created: {ch.name}',
            note=f'Cloned from #{src.id} {src.name}. {ch.start_at:%Y-%m-%d} → {ch.end_at:%Y-%m-%d}, gold {gold}.',
            url=f'/challenges/{ch.id}/', created_by=by, happened_at=now,
        )
        self.stdout.write(
            f"#{ch.id} {ch.name}: {ch.start_at:%Y-%m-%d} -> {ch.end_at:%Y-%m-%d} | targets {bronze}/{silver}/{gold} | "
            f"batch={ch.batch_id} bbox={ch.has_bbox} | images={ch.cached_image_count} tasks={ch.cached_task_count}")
