"""
One-shot: populate Image.photoCenterLat / Lon from the legacy CharField
coordinates, using the priority chain:
  photoCenterPoint → photoCenterByMachineLearning → spacecraftNadirPoint.

For new images the same logic runs in Image.save() automatically; this
command is only needed once for the existing dataset.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from georeferencing.models import Image


class Command(BaseCommand):
    help = 'Populate Image.photoCenterLat/Lon from legacy CharField coords.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--only-missing',
            action='store_true',
            help='Only update rows whose photoCenterLat/Lon are NULL.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print stats without writing.',
        )

    def handle(self, *args, **opts):
        qs = Image.objects.all()
        if opts['only_missing']:
            qs = qs.filter(photoCenterLat__isnull=True)
        total = qs.count()
        self.stdout.write(f'Scanning {total} images…')

        n_set = 0
        n_no_coords = 0
        n_unchanged = 0

        # Bulk-update in chunks to avoid loading everything into memory.
        BATCH = 500
        with transaction.atomic():
            buffer = []
            for img in qs.only(
                'id', 'photoCenterPoint', 'photoCenterByMachineLearning',
                'spacecraftNadirPoint', 'photoCenterLat', 'photoCenterLon',
            ).iterator(chunk_size=BATCH):
                center = img.best_center()
                if center is None:
                    if img.photoCenterLat is not None or img.photoCenterLon is not None:
                        img.photoCenterLat = None
                        img.photoCenterLon = None
                        buffer.append(img)
                    n_no_coords += 1
                    continue
                lat, lon = center
                if img.photoCenterLat == lat and img.photoCenterLon == lon:
                    n_unchanged += 1
                    continue
                img.photoCenterLat = lat
                img.photoCenterLon = lon
                buffer.append(img)
                n_set += 1
                if len(buffer) >= BATCH and not opts['dry_run']:
                    Image.objects.bulk_update(
                        buffer, ['photoCenterLat', 'photoCenterLon'],
                    )
                    buffer = []
            if buffer and not opts['dry_run']:
                Image.objects.bulk_update(
                    buffer, ['photoCenterLat', 'photoCenterLon'],
                )

        self.stdout.write(self.style.SUCCESS(
            f'{n_set} updated, {n_unchanged} unchanged, {n_no_coords} without parseable coords'
        ))
        if opts['dry_run']:
            self.stdout.write(self.style.WARNING('--dry-run, no rows written'))
