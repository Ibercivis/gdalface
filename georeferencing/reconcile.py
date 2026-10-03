"""
Single source of truth for the denormalised counters.

Every cached number (UserProfile.geoattempts_done / controlPointsDone /
time_spent, GeoAttemptsByUserByDay, ChallengeParticipant.cached_cp_count) is
derived here from GeoAttempt rows with status DONE. The submit endpoint keeps
them incrementally; the `reconcile_counters` command and the admin actions use
these functions to recompute them from scratch.
"""
from collections import defaultdict
from datetime import timedelta

from django.db.models import F, Q


def _cp(ga):
    pts = ga.controlPoints
    return len(pts) if isinstance(pts, list) else 0


def _seconds(ga):
    if ga.finishedDateTime and ga.assignedDateTime and ga.finishedDateTime > ga.assignedDateTime:
        return int((ga.finishedDateTime - ga.assignedDateTime).total_seconds())
    return 0


def done_queryset():
    from .models import GeoAttempt
    return GeoAttempt.objects.filter(status='DONE')


def expected_profile_totals():
    """{user_id: {'tasks': n, 'cp': n, 'seconds': n}} for every user with ≥1 DONE task."""
    out = defaultdict(lambda: {'tasks': 0, 'cp': 0, 'seconds': 0})
    qs = done_queryset().filter(assignedUser__isnull=False).only(
        'assignedUser_id', 'controlPoints', 'assignedDateTime', 'finishedDateTime')
    for ga in qs.iterator(chunk_size=2000):
        row = out[ga.assignedUser_id]
        row['tasks'] += 1
        row['cp'] += _cp(ga)
        row['seconds'] += _seconds(ga)
    return out


def expected_daily_counts():
    """{(user_id, date): {'tasks', 'cp', 'seconds'}} from DONE tasks by finish date (UTC)."""
    out = defaultdict(lambda: {'tasks': 0, 'cp': 0, 'seconds': 0})
    qs = done_queryset().filter(assignedUser__isnull=False, finishedDateTime__isnull=False).only(
        'assignedUser_id', 'finishedDateTime', 'controlPoints', 'assignedDateTime')
    for ga in qs.iterator(chunk_size=5000):
        row = out[(ga.assignedUser_id, ga.finishedDateTime.date())]
        row['tasks'] += 1
        row['cp'] += _cp(ga)
        row['seconds'] += _seconds(ga)
    return out


def participant_tasks(participant, challenge=None):
    """DONE tasks that count for this enrollment: by the participant, finished
    inside the challenge window AND inside one of the participant's enrollment
    periods (ChallengeEnrollmentPeriod), on an image matching the challenge
    (batch ∩ bbox). This is THE rule; the submit endpoint credits live under
    the same conditions. Falls back to joined_at/left_at if no period exists."""
    ch = challenge or participant.challenge
    periods = list(participant.periods.values_list('joined_at', 'left_at'))
    if not periods:
        periods = [(participant.joined_at, participant.left_at)]
    window = Q(pk__in=[])
    for joined, left in periods:
        lo = max(joined, ch.start_at)
        hi = min(left or ch.end_at, ch.end_at)
        if lo < hi:
            window |= Q(finishedDateTime__gte=lo, finishedDateTime__lt=hi)
    return (done_queryset()
            .filter(assignedUser_id=participant.user_id)
            .filter(window)
            .filter(image__in=ch.matching_images()))


def expected_participant_cp(participant, challenge=None):
    return sum(_cp(ga) for ga in participant_tasks(participant, challenge).only('controlPoints'))


def recompute_challenge(challenge):
    """Rewrite cached_cp_count for every participant of a challenge. Returns
    the number of participants whose value changed."""
    changed = 0
    for p in challenge.participants.all():
        cp = expected_participant_cp(p, challenge)
        if cp != p.cached_cp_count:
            p.cached_cp_count = cp
            p.save(update_fields=['cached_cp_count'])
            changed += 1
    return changed
