"""
Find burst / time-lapse sequences among the photos already loaded as tasks and
park the redundant ones: consecutive frames of the same mission and focal taken
less than N seconds apart form a sequence; inside it one frame every
--min-distance-km along the track stays (a time-lapse sweeps thousands of km), the others
lose their PENDING tasks (nothing done or assigned is touched) and get
replicas=0 so they are not re-generated. Files stay on disk. Dry-run by default.

    manage.py park_bursts [--gap-seconds 20] [--apply]
"""
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count, Q

from georeferencing.models import GeoAttempt, Image, NasaPhoto, StatsEvent


def find_bursts(gap):
    """→ list of sequences (lists of NasaPhoto rows linked to loaded images), length ≥ 2."""
    rows = list(NasaPhoto.objects.filter(image__isnull=False, taken__isnull=False)
                .select_related('image').order_by('mission', 'frame'))
    seqs, seq = [], []
    for p in rows:
        if seq and p.mission == seq[-1].mission and p.focal == seq[-1].focal \
                and abs((p.taken - seq[-1].taken).total_seconds()) <= gap:
            seq.append(p)
        else:
            if len(seq) >= 2:
                seqs.append(seq)
            seq = [p]
    if len(seq) >= 2:
        seqs.append(seq)
    return seqs


class Command(BaseCommand):
    help = 'Park redundant burst photos already loaded as tasks (dry-run unless --apply).'

    def add_arguments(self, p):
        p.add_argument('--gap-seconds', type=float, default=20)
        p.add_argument('--min-distance-km', type=float, default=50, help='fixed spacing inside a burst when --overlap is 0 or focal unknown')
        p.add_argument('--overlap', type=float, default=0.5, help='spacing as a fraction of the frame footprint (0.5 = frames overlap by half); 0 disables')
        p.add_argument('--apply', action='store_true')

    def handle(self, *args, **o):
        seqs = find_bursts(o['gap_seconds'])
        counts = {r['image_id']: r for r in GeoAttempt.objects.values('image_id').annotate(
            pend=Count('id', filter=Q(status='PENDING')), other=Count('id', filter=~Q(status='PENDING')))}
        to_park, pend_total, keep_with_work = [], 0, 0
        by_batch = defaultdict(int)
        import math
        def km(a, b):
            la1, lo1 = (a.center_lat, a.center_lon) if a.center_lat is not None else ((a.ml_lat, a.ml_lon) if a.ml_lat is not None else (a.nadir_lat, a.nadir_lon))
            la2, lo2 = (b.center_lat, b.center_lon) if b.center_lat is not None else ((b.ml_lat, b.ml_lon) if b.ml_lat is not None else (b.nadir_lat, b.nadir_lon))
            if None in (la1, lo1, la2, lo2):
                return 1e9
            return math.hypot(la2 - la1, (lo2 - lo1) * math.cos(math.radians(la1))) * 111
        def step_km(p):
            # Frame footprint across track ≈ 36 mm sensor / focal × 420 km altitude;
            # keep one frame every --overlap × footprint (default half a footprint),
            # or the fixed --min-distance-km when no focal is known.
            if o['overlap'] and p.focal:
                return max(5.0, o['overlap'] * 36.0 / p.focal * 420.0)
            return o['min_distance_km']
        for seq in seqs:
            # A time-lapse sweeps thousands of km: inside a sequence keep one frame
            # every step along track (first frame always kept).
            keep, last = set(), None
            for p in seq:
                if last is None or km(last, p) >= step_km(p):
                    keep.add(p.image_id); last = p
            # also keep any frame that already has work on it
            for p in seq:
                c = counts.get(p.image_id, {'pend': 0, 'other': 0})
                if p.image_id in keep:
                    continue
                if c['other']:
                    keep_with_work += 1
                    continue
                to_park.append(p.image_id); pend_total += c['pend']
                by_batch[p.image.batch.name if p.image.batch_id else '-'] += 1
        self.stdout.write(f"sequences={len(seqs)} frames_in_sequences={sum(len(s) for s in seqs)} "
                          f"to_park={len(to_park)} pending_tasks_removed={pend_total} kept_because_worked={keep_with_work}")
        self.stdout.write('by batch: ' + ', '.join(f'{k}={v}' for k, v in sorted(by_batch.items(), key=lambda x: -x[1])))
        if not o['apply']:
            self.stdout.write('DRY RUN, nothing written'); return
        with transaction.atomic():
            GeoAttempt.objects.filter(image_id__in=to_park, status='PENDING').delete()
            Image.objects.filter(id__in=to_park).update(replicas=0)
            StatsEvent.objects.create(kind='batch', title=f'Parked {len(to_park)} burst photos',
                                      note=f'{pend_total} pending tasks removed; gap {o["gap_seconds"]}s; ' + ', '.join(f'{k}={v}' for k, v in by_batch.items()))
        self.stdout.write(f'APPLIED: parked {len(to_park)} images')
