"""
Time series for the staff panel.

Two kinds of metric:
- EVENT metrics are recomputed from timestamps in the database (contributions
  by finish date, sign-ups by join date, activity from the daily table…).
- STATE metrics have no history in the database (pending tasks, team count,
  newsletter subscribers…). `record_daily_metrics()` snapshots them once a day
  into DailyMetric; `backfill_daily_metrics()` reconstructs the ones that can
  be derived from timestamps so charts have history from day one.

`series(range_key)` returns every chart series bucketed by day / week / month
according to the range (7d, 30d, 1y, 4y).
"""
from collections import defaultdict
from datetime import date, timedelta

from django.db.models import Count, Q
from django.db.models.functions import TruncDay, TruncMonth, TruncWeek
from django.utils import timezone

RANGES = {
    '7d':  {'days': 7,        'bucket': 'day',   'label': '7 days'},
    '30d': {'days': 30,       'bucket': 'day',   'label': '30 days'},
    '1y':  {'days': 365,      'bucket': 'week',  'label': '1 year'},
    '4y':  {'days': 4 * 365,  'bucket': 'month', 'label': '4 years'},
}
DEFAULT_RANGE = '30d'

STATE_KEYS = (
    'tasks_pending', 'tasks_assigned', 'tasks_done', 'images_total',
    'users_total', 'users_verified', 'newsletter', 'teams', 'team_members',
    'challenges_open', 'challenge_participants', 'active_7', 'active_30',
)


# ── Buckets ──────────────────────────────────────────────────────────────
def bucket_start(d, bucket):
    if bucket == 'day':
        return d
    if bucket == 'week':
        return d - timedelta(days=d.weekday())
    return d.replace(day=1)


def next_bucket(d, bucket):
    if bucket == 'day':
        return d + timedelta(days=1)
    if bucket == 'week':
        return d + timedelta(days=7)
    return (d.replace(day=28) + timedelta(days=4)).replace(day=1)


def buckets_for(range_key, today=None):
    """(start_date, end_date, bucket, [bucket_start_dates])"""
    spec = RANGES.get(range_key, RANGES[DEFAULT_RANGE])
    today = today or timezone.now().date()
    start = bucket_start(today - timedelta(days=spec['days'] - 1), spec['bucket'])
    labels = []
    d = start
    while d <= today:
        labels.append(d)
        d = next_bucket(d, spec['bucket'])
    return start, today, spec['bucket'], labels


_TRUNC = {'day': TruncDay, 'week': TruncWeek, 'month': TruncMonth}


def _as_date(v):
    from datetime import datetime
    return v.date() if isinstance(v, datetime) else v


def _count_by_bucket(qs, field, start, end, bucket, distinct=None):
    """{bucket_start: count} of rows whose `field` (datetime or date) is in [start, end]."""
    lookup = f'{field}__date' if _is_datetime(qs.model, field) else field
    rows = (qs.filter(**{f'{lookup}__gte': start, f'{lookup}__lte': end})
            .annotate(_b=_TRUNC[bucket](field)).values('_b')
            .annotate(n=Count(distinct, distinct=True) if distinct else Count('id')).order_by())
    return {_as_date(r['_b']): r['n'] for r in rows}


def _is_datetime(model, field):
    from django.db.models import DateTimeField
    return isinstance(model._meta.get_field(field), DateTimeField)


def _fill(counts, labels):
    return [counts.get(d, 0) for d in labels]


# ── Event metrics (from timestamps) ──────────────────────────────────────
def event_series(start, end, bucket, labels):
    from django.contrib.auth import get_user_model
    from .models import ChallengeEnrollmentPeriod, GeoAttempt, GeoAttemptsByUserByDay
    from teams.models import TeamMembership
    User = get_user_model()
    done = GeoAttempt.objects.filter(status='DONE')
    out = {
        'contributions': _fill(_count_by_bucket(done, 'finishedDateTime', start, end, bucket), labels),
        'contributions_registered': _fill(_count_by_bucket(
            done.filter(assignedUser__isnull=False), 'finishedDateTime', start, end, bucket), labels),
        'signups': _fill(_count_by_bucket(User.objects.all(), 'date_joined', start, end, bucket), labels),
        'active_users': _fill(_count_by_bucket(
            GeoAttemptsByUserByDay.objects.filter(numberGeoAttempts__gt=0), 'date', start, end, bucket,
            distinct='user_id'), labels),
        'challenge_joins': _fill(_count_by_bucket(
            ChallengeEnrollmentPeriod.objects.all(), 'joined_at', start, end, bucket), labels),
        'team_joins': _fill(_count_by_bucket(
            TeamMembership.objects.all(), 'joined_at', start, end, bucket), labels),
    }
    out['contributions_anonymous'] = [a - b for a, b in zip(out['contributions'], out['contributions_registered'])]
    return out


# ── State metrics (snapshots) ────────────────────────────────────────────
def compute_state_metrics(today=None):
    from django.contrib.auth import get_user_model
    from allauth.account.models import EmailAddress
    from user_profile.models import UserProfile
    from teams.models import Team, TeamMembership
    from .models import Challenge, ChallengeParticipant, GeoAttempt, GeoAttemptsByUserByDay, Image
    from . import metrics
    today = today or timezone.now().date()
    by_status = dict(GeoAttempt.objects.values_list('status').annotate(n=Count('id')).order_by())
    return {
        'tasks_pending': by_status.get('PENDING', 0),
        'tasks_assigned': by_status.get('ASSIGNED', 0),
        'tasks_done': by_status.get('DONE', 0),
        'images_total': Image.objects.count(),
        'users_total': get_user_model().objects.count(),
        'users_verified': EmailAddress.objects.filter(verified=True).values('user_id').distinct().count(),
        'newsletter': UserProfile.objects.filter(newsletter_subscribed=True).count(),
        'teams': Team.objects.count(),
        'team_members': TeamMembership.objects.filter(left_at__isnull=True).count(),
        'challenges_open': sum(1 for c in Challenge.objects.all() if c.status in ('active', 'paused', 'upcoming')),
        'challenge_participants': ChallengeParticipant.objects.filter(left_at__isnull=True).count(),
        'active_7': metrics.active_users(7),
        'active_30': metrics.active_users(30),
    }


def record_daily_metrics(today=None, values=None):
    """Upsert today's state snapshot. Returns the number of keys written."""
    from .models import DailyMetric
    today = today or timezone.now().date()
    values = values or compute_state_metrics(today)
    for key, value in values.items():
        DailyMetric.objects.update_or_create(date=today, key=key, defaults={'value': value})
    return len(values)


def record_daily_metrics_if_missing(today=None):
    from .models import DailyMetric
    today = today or timezone.now().date()
    if DailyMetric.objects.filter(date=today, key='tasks_done').exists():
        return False
    record_daily_metrics(today)
    return True


def backfill_daily_metrics(start=None, end=None):
    """Reconstruct the state keys that can be derived from timestamps, one row
    per day from the first contribution to yesterday. Idempotent."""
    from django.contrib.auth import get_user_model
    from .models import (ChallengeEnrollmentPeriod, DailyMetric, GeoAttempt,
                         GeoAttemptsByUserByDay, Image)
    from teams.models import TeamMembership
    User = get_user_model()
    first = GeoAttempt.objects.filter(status='DONE', finishedDateTime__isnull=False).order_by('finishedDateTime').first()
    if not first and start is None:
        return 0
    start = start or first.finishedDateTime.date()
    end = end or (timezone.now().date() - timedelta(days=1))

    # Daily deltas, then cumulative sums.
    done_by_day = _count_by_bucket(GeoAttempt.objects.filter(status='DONE'), 'finishedDateTime', date(2000, 1, 1), end, 'day')
    created_by_day = _count_by_bucket(GeoAttempt.objects.all(), 'createdDateTime', date(2000, 1, 1), end, 'day')
    users_by_day = _count_by_bucket(User.objects.all(), 'date_joined', date(2000, 1, 1), end, 'day')
    images_by_day = _count_by_bucket(Image.objects.all(), 'createdDateTime', date(2000, 1, 1), end, 'day')
    activity = defaultdict(set)
    for uid, d in GeoAttemptsByUserByDay.objects.filter(numberGeoAttempts__gt=0, date__lte=end).values_list('user_id', 'date'):
        activity[d].add(uid)
    periods = list(ChallengeEnrollmentPeriod.objects.values_list('joined_at', 'left_at'))
    memberships = list(TeamMembership.objects.values_list('joined_at', 'left_at'))

    def cumulative(by_day, upto):
        return sum(n for d, n in by_day.items() if d <= upto)

    def active_window(d, days):
        users = set()
        for k in range(days):
            users |= activity.get(d - timedelta(days=k), set())
        return len(users)

    def open_at(rows, d):
        end_of_day = timezone.make_aware(timezone.datetime.combine(d, timezone.datetime.max.time()))
        return sum(1 for j, l in rows if j <= end_of_day and (l is None or l > end_of_day))

    n = 0
    d = start
    while d <= end:
        done_c = cumulative(done_by_day, d)
        values = {
            'tasks_done': done_c,
            'tasks_pending': max(0, cumulative(created_by_day, d) - done_c),
            'users_total': cumulative(users_by_day, d),
            'images_total': cumulative(images_by_day, d),
            'active_7': active_window(d, 7),
            'active_30': active_window(d, 30),
            'challenge_participants': open_at(periods, d),
            'team_members': open_at(memberships, d),
        }
        for key, value in values.items():
            DailyMetric.objects.update_or_create(date=d, key=key, defaults={'value': value})
            n += 1
        d += timedelta(days=1)
    return n


def state_series(start, end, bucket, labels, keys=STATE_KEYS):
    """Last recorded value per bucket for each state key; None where missing."""
    from .models import DailyMetric
    rows = DailyMetric.objects.filter(date__gte=start, date__lte=end, key__in=keys).order_by('date')
    last = {k: {} for k in keys}
    for r in rows:
        last[r.key][bucket_start(r.date, bucket)] = r.value  # later dates overwrite → last in bucket
    return {k: [last[k].get(d) for d in labels] for k in keys}


# ── Public entry point ───────────────────────────────────────────────────
def series(range_key=DEFAULT_RANGE, today=None):
    start, end, bucket, labels = buckets_for(range_key, today)
    ev = event_series(start, end, bucket, labels)
    st = state_series(start, end, bucket, labels)
    # Previous range of the same length, for deltas on the tiles.
    spec = RANGES.get(range_key, RANGES[DEFAULT_RANGE])
    p_end = start - timedelta(days=1)
    p_start = p_end - timedelta(days=spec['days'] - 1)
    p_labels = [p_start]
    prev = event_series(p_start, p_end, 'day', [p_start + timedelta(days=i) for i in range((p_end - p_start).days + 1)])
    totals = {k: sum(v) for k, v in ev.items()}
    prev_totals = {k: sum(v) for k, v in prev.items()}
    from .models import StatsEvent
    events = [{
        'date': e.happened_at.date().isoformat(), 'kind': e.kind,
        'kind_label': str(e.get_kind_display()), 'title': e.title, 'url': e.url,
    } for e in StatsEvent.objects.filter(happened_at__date__gte=start, happened_at__date__lte=end)]
    return {
        'range': range_key if range_key in RANGES else DEFAULT_RANGE,
        'bucket': bucket,
        'start': start.isoformat(), 'end': end.isoformat(),
        'labels': [d.isoformat() for d in labels],
        'events': ev,
        'states': st,
        'totals': totals,
        'prev_totals': prev_totals,
        'markers': events,
        'cohorts': cohorts(range_key, today),
    }


# ── Retention cohorts ────────────────────────────────────────────────────
def cohorts(range_key=DEFAULT_RANGE, today=None, max_rows=12):
    """Sign-up cohorts (weekly for short ranges, monthly for 1y/4y): size, how
    many ever contributed, contributed within the first period, and the share
    active in each of the 4 periods after joining. Activity = a DONE task
    (GeoAttemptsByUserByDay). Periods not yet elapsed are None."""
    from django.contrib.auth import get_user_model
    from .models import GeoAttemptsByUserByDay
    today = today or timezone.now().date()
    spec = RANGES.get(range_key, RANGES[DEFAULT_RANGE])
    unit = 'month' if spec['bucket'] == 'month' or spec['days'] >= 365 else 'week'
    unit_days = 30 if unit == 'month' else 7
    first_start = bucket_start(today - timedelta(days=spec['days'] - 1), unit)
    # Cohort buckets (cap the number of rows)
    starts = []
    d = first_start
    while d <= today:
        starts.append(d)
        d = next_bucket(d, unit)
    starts = starts[-max_rows:]

    User = get_user_model()
    users = list(User.objects.filter(date_joined__date__gte=starts[0]).values_list('id', 'date_joined'))
    activity = defaultdict(list)
    for uid, dt in GeoAttemptsByUserByDay.objects.filter(
            numberGeoAttempts__gt=0, user_id__in=[u for u, _ in users]).values_list('user_id', 'date'):
        activity[uid].append(dt)

    rows = []
    for i, start in enumerate(starts):
        end = next_bucket(start, unit) - timedelta(days=1)
        members = [(uid, dj.date()) for uid, dj in users if start <= dj.date() <= end]
        size = len(members)
        ever = sum(1 for uid, _ in members if activity.get(uid))
        first_period = sum(1 for uid, dj in members if any(dj <= a <= dj + timedelta(days=unit_days - 1) for a in activity.get(uid, [])))
        periods = []
        for k in range(4):
            lo_off, hi_off = k * unit_days, (k + 1) * unit_days - 1
            # elapsed only if the whole cohort could have completed period k
            if end + timedelta(days=hi_off) > today:
                periods.append(None)
                continue
            n = sum(1 for uid, dj in members if any(dj + timedelta(days=lo_off) <= a <= dj + timedelta(days=hi_off) for a in activity.get(uid, [])))
            periods.append(round(n / size * 100) if size else None)
        rows.append({
            'label': start.isoformat() if unit == 'week' else start.strftime('%Y-%m'),
            'size': size,
            'ever_pct': round(ever / size * 100) if size else None,
            'first_pct': round(first_period / size * 100) if size else None,
            'periods': periods,
        })
    return {'unit': unit, 'rows': rows}
