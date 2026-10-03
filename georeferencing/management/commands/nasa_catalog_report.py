"""
Per-mission summary of the NasaPhoto catalogue: what NASA has, what is usable
at night, what we have loaded and what the community has located.

    manage.py nasa_catalog_report [--csv path] [--min-focal 50]
"""
import csv
import sys

from django.core.management.base import BaseCommand
from django.db.models import Count, Q, Sum

from georeferencing.models import NasaPhoto

COLUMNS = ['mission', 'photos', 'with_file', 'catalogued_centre', 'ml_centre', 'nadir_only', 'no_coords',
           'night', 'night_usable', 'night_tier_A', 'night_tier_B', 'night_tier_C', 'night_tier_D',
           'in_our_db', 'located_once', 'complete_5', 'pending_tasks']


def summarize(min_focal=50):
    # Annotation names are prefixed so they never shadow model fields used in
    # the filters (e.g. `night`), which Postgres rejects as aggregate-in-FILTER.
    spec = {
        'photos': Q(), 'with_file': Q(has_large=True),
        'catalogued_centre': Q(center_lat__isnull=False),
        'ml_centre': Q(center_lat__isnull=True, ml_lat__isnull=False),
        'nadir_only': Q(center_lat__isnull=True, ml_lat__isnull=True, nadir_lat__isnull=False),
        'no_coords': Q(center_lat__isnull=True, ml_lat__isnull=True, nadir_lat__isnull=True),
        'night': Q(night=True), 'night_usable': Q(night=True, has_large=True, focal__gte=min_focal),
        'night_tier_A': Q(night=True, has_large=True, tier='A'), 'night_tier_B': Q(night=True, has_large=True, tier='B'),
        'night_tier_C': Q(night=True, has_large=True, tier='C'), 'night_tier_D': Q(night=True, has_large=True, tier='D'),
        'in_our_db': Q(image__isnull=False), 'located_once': Q(done_count__gte=1), 'complete_5': Q(done_count__gte=5),
    }
    annotations = {f'c_{k}': Count('id', filter=q) for k, q in spec.items()}
    annotations['c_pending_tasks'] = Sum('pending_count')
    agg = NasaPhoto.objects.values('mission').annotate(**annotations).order_by('mission')
    rows = [{'mission': a['mission'], **{c: (a.get(f'c_{c}') or 0) for c in COLUMNS if c != 'mission'}} for a in agg]
    total = {c: (sum(r[c] for r in rows) if c != 'mission' else 'TOTAL') for c in COLUMNS}
    rows.append(total)
    return rows


class Command(BaseCommand):
    help = 'Per-mission summary of the NASA photo catalogue.'

    def add_arguments(self, p):
        p.add_argument('--csv', default=None, help='write the table to this CSV path')
        p.add_argument('--min-focal', type=int, default=50)

    def handle(self, *args, **o):
        rows = summarize(o['min_focal'])
        w = csv.DictWriter(sys.stdout, fieldnames=COLUMNS)
        w.writeheader(); w.writerows(rows)
        if o['csv']:
            with open(o['csv'], 'w', newline='') as fh:
                cw = csv.DictWriter(fh, fieldnames=COLUMNS); cw.writeheader(); cw.writerows(rows)
            self.stderr.write(f'written {o["csv"]}')
