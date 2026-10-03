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
    """{(user_id, date): n} from DONE tasks by finish date (UTC)."""
    out = defaultdict(int)
    qs = done_queryset().filter(assignedUser__isnull=False, finishedDateTime__isnull=False).only(
        'assignedUser_id', 'finishedDateTime')
    for ga in qs.iterator(chunk_size=5000):
        out[(ga.assignedUser_id, ga.finishedDateTime.date())] += 1
    return out


def participant_tasks(participant, challenge=None):
    """DONE tasks that count for this enrollment: by the participant, finished
    inside both the challenge window and the enrollment window, on an image
    that matches the challenge (batch ∩ bbox). This is THE rule; the submit
    endpoint credits live under the same conditions."""
    from .models import ChallengeParticipant
    ch = challenge or participant.challenge
    lo = max(participant.joined_at, ch.start_at)
    hi = min(participant.left_at or ch.end_at, ch.end_at)
    # Joining another challenge implicitly ends this enrollment (the live
    # endpoint credits a single enrollment per task; legacy rows may still
    # have left_at=NULL while a later enrollment exists).
    next_join = (ChallengeParticipant.objects
                 .filter(user_id=participant.user_id, joined_at__gt=participant.joined_at)
                 .exclude(pk=participant.pk)
                 .order_by('joined_at').values_list('joined_at', flat=True).first())
    if next_join and next_join < hi:
        hi = next_join
    if lo >= hi:
        return done_queryset().none()
    return (done_queryset()
            .filter(assignedUser_id=participant.user_id,
                    finishedDateTime__gte=lo, finishedDateTime__lt=hi,
                    image__in=ch.matching_images()))


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
