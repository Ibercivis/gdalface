import csv
from pathlib import Path
from django.core.management.base import BaseCommand
from georeferencing.models import Expedition


class Command(BaseCommand):
    help = 'Load ISS expedition crew data from iss_expeditions.csv'

    def handle(self, *args, **options):
        csv_path = Path(__file__).resolve().parents[3] / 'iss_expeditions.csv'
        if not csv_path.exists():
            self.stderr.write(f'File not found: {csv_path}')
            return

        expeditions = {}
        with open(csv_path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                number = int(row['expedition_number'])
                name = row['astronaut_name'].strip()
                if not name:
                    continue
                expeditions.setdefault(number, []).append({
                    'name': name,
                    'image_url': row['astronaut_image_url'].strip(),
                    'wikipedia_url': row['astronaut_wikipedia_url'].strip(),
                })

        created = updated = 0
        for number, crew in expeditions.items():
            obj, was_created = Expedition.objects.update_or_create(
                number=number,
                defaults={'crew': crew},
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            f'Done: {created} created, {updated} updated — {len(expeditions)} expeditions total.'
        ))
