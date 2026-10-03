"""
One definition per metric. Every surface (homepage, user area, task-info
stats, result overlay, rankings, diplomas, public snapshot, staff panel) must
read its numbers from here instead of recomputing them locally.

Definitions
-----------
population   Users with at least one verified e-mail (allauth). This is the
             set that counts as "participants" and the only population used
             for ranks. Invisible profiles stay in the population (they are
             anonymised when displayed, never dropped from counts).
contribution A GeoAttempt with status DONE. Anonymous ones count towards
             project totals but belong to nobody.
user totals  UserProfile.geoattempts_done / controlPointsDone / time_spent.
             They are kept incrementally by the submit endpoint and rebuilt by
             `reconcile_counters` from the DONE rows, so they equal
             Σ over the user's DONE GeoAttempts.
rank         1 + number of population members with a strictly greater metric.
             Ties share a rank.
active user  A population member with ≥1 contribution in the last N days
             (GeoAttemptsByUserByDay).
"""
from datetime import timedelta

from django.core.cache import cache
from django.db.models import Count, F, Max, Min, Q, Sum
from django.utils import timezone

CACHE_TTL = 300
METRIC_FIELDS = {
    'tasks': 'geoattempts_done',
    'cp': 'controlPointsDone',
    'time': 'time_spent',
}


# ── Population ───────────────────────────────────────────────────────────
def verified_user_ids():
    from allauth.account.models import EmailAddress
    return EmailAddress.objects.filter(verified=True).values_list('user_id', flat=True)


def population():
    """UserProfile queryset of the ranking population."""
    from user_profile.models import UserProfile
    return UserProfile.objects.filter(user_id__in=verified_user_ids())


def participants(use_cache=True):
    key = 'metrics:participants:v1'
    n = cache.get(key) if use_cache else None
    if n is None:
        n = verified_user_ids().distinct().count()
        if use_cache:
            cache.set(key, n, CACHE_TTL)
    return n


def active_users(days):
    from .models import GeoAttemptsByUserByDay
    since = timezone.now().date() - timedelta(days=days)
    return (GeoAttemptsByUserByDay.objects
            .filter(date__gte=since, numberGeoAttempts__gt=0, user_id__in=verified_user_ids())
            .values('user_id').distinct().count())


# ── Project totals ───────────────────────────────────────────────────────
def project_totals(use_cache=True):
    """Project-wide counters. Cached CACHE_TTL seconds."""
    key = 'metrics:project_totals:v1'
    data = cache.get(key) if use_cache else None
    if data is not None:
        return data
    from .models import GeoAttempt, Image
    done = GeoAttempt.objects.filter(status='DONE')
    cp = 0
    seconds = 0
    for ga in done.only('controlPoints', 'assignedDateTime', 'finishedDateTime').iterator(chunk_size=2000):
        if isinstance(ga.controlPoints, list):
            cp += len(ga.controlPoints)
        if ga.finishedDateTime and ga.assignedDateTime and ga.finishedDateTime > ga.assignedDateTime:
            seconds += int((ga.finishedDateTime - ga.assignedDateTime).total_seconds())
    tasks_total = GeoAttempt.objects.count()
    tasks_done = done.count()
    data = {
        'tasks_total': tasks_total,
        'tasks_done': tasks_done,
        'tasks_pending': GeoAttempt.objects.filter(status='PENDING').count(),
        'completion_pct': round(tasks_done / tasks_total * 100, 1) if tasks_total else 0,
        'anonymous_done': done.filter(assignedUser__isnull=True).count(),
        'contributors': done.filter(assignedUser__isnull=False).values('assignedUser_id').distinct().count(),
        'images_total': Image.objects.count(),
        'images_georeferenced': Image.objects.filter(
            id__in=done.values('image_id')).count(),
        'control_points': cp,
        'seconds': seconds,
        'participants': participants(use_cache=use_cache),
    }
    data['avg_tasks_per_participant'] = (
        round(tasks_done / data['participants'], 1) if data['participants'] else 0)
    if use_cache:
        cache.set(key, data, CACHE_TTL)
    return data


def invalidate():
    cache.delete_many(['metrics:project_totals:v1', 'metrics:participants:v1'])


# ── Per-user ─────────────────────────────────────────────────────────────
def user_totals(profile):
    return {
        'tasks': profile.geoattempts_done or 0,
        'cp': profile.controlPointsDone or 0,
        'seconds': profile.time_spent or 0,
    }


def global_rank(profile, metric='cp', value=None):
    """Rank of `profile` (or of an arbitrary `value`) inside the population.

    Returns {'rank', 'total', 'value', 'to_next', 'to_first'} where to_next is
    how much more is needed to pass the closest member strictly ahead, and
    to_first how much to reach the leader. Both are 0 for the leader. If the
    profile is not in the population (unverified e-mail) rank is still
    computed against the population so the number is meaningful, but
    `in_population` is False.
    """
    field = METRIC_FIELDS[metric]
    pop = population()
    mine = getattr(profile, field) or 0 if value is None else value
    ahead = pop.filter(**{f'{field}__gt': mine})
    rank = ahead.count() + 1
    agg = ahead.aggregate(nxt=Min(field), top=Max(field))
    return {
        'rank': rank,
        'total': pop.count(),
        'value': mine,
        'to_next': (agg['nxt'] - mine) if agg['nxt'] is not None else 0,
        'to_first': (agg['top'] - mine) if agg['top'] is not None else 0,
        'in_population': pop.filter(pk=profile.pk).exists() if profile is not None else False,
    }


def all_ranks(profile):
    return {m: global_rank(profile, m) for m in METRIC_FIELDS}


def streak(user, tolerate_today=True):
    """(current, best) consecutive-day streaks from GeoAttemptsByUserByDay.
    `tolerate_today`: an empty today does not break the current streak."""
    from .models import GeoAttemptsByUserByDay
    dates = sorted(set(GeoAttemptsByUserByDay.objects
                       .filter(user=user, numberGeoAttempts__gt=0)
                       .values_list('date', flat=True)))
    if not dates:
        return 0, 0
    best = run = 1
    for a, b in zip(dates, dates[1:]):
        run = run + 1 if (b - a).days == 1 else 1
        best = max(best, run)
    today = timezone.now().date()
    gap = (today - dates[-1]).days
    if gap > (1 if tolerate_today else 0):
        return 0, best
    current = 1
    i = len(dates) - 1
    while i > 0 and (dates[i] - dates[i - 1]).days == 1:
        current += 1
        i -= 1
    return current, best


def weekly_contributions(weeks=12, use_cache=True):
    """[{'week': 'YYYY-MM-DD' (Monday), 'n': contributions}] for the last `weeks`
    weeks including the current one. Project-wide, anonymous included."""
    key = f'metrics:weekly:{weeks}:v1'
    data = cache.get(key) if use_cache else None
    if data is not None:
        return data
    from django.db.models.functions import TruncWeek
    from .models import GeoAttempt
    today = timezone.now().date()
    this_monday = today - timedelta(days=today.weekday())
    start = this_monday - timedelta(weeks=weeks - 1)
    rows = (GeoAttempt.objects.filter(status='DONE', finishedDateTime__date__gte=start)
            .annotate(w=TruncWeek('finishedDateTime')).values('w')
            .annotate(n=Count('id')).order_by())
    counts = {r['w'].date() if hasattr(r['w'], 'date') else r['w']: r['n'] for r in rows}
    data = [{'week': (start + timedelta(weeks=i)).isoformat(),
             'n': counts.get(start + timedelta(weeks=i), 0)} for i in range(weeks)]
    if use_cache:
        cache.set(key, data, CACHE_TTL)
    return data
