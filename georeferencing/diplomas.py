"""Diploma / badge logic.

Single source of truth for the achievement tiers, medals and the data each
certificate shows. Shared by the profile badge grid and the rendered PDF
diplomas so the two never drift apart.

Two independent axes describe a user's standing in a challenge:

* ``individual_medal``  — their placement (1st/2nd/3rd → gold/silver/bronze,
  everyone else → participant).
* ``collective_tier``   — the level the whole community reached in that
  challenge (total CP vs the bronze/silver/gold targets).

The general (all-time) badge uses ``global_tier`` on the user's lifetime CP.
"""
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


# ── Global (all-time) tiers ──────────────────────────────────────────────
# Absolute, *frozen* thresholds on lifetime control points. They were derived
# once from the live percentile distribution among contributors (≈ p15 / p50 /
# p75 / p90 / top-6%) so the cut-offs are data-driven — and then fixed. A
# diploma is a permanent record: its tier must not change as the population
# shifts, so we deliberately do NOT recompute percentiles on the fly.
GLOBAL_TIERS = (
    # (slug, min_cp)
    ('diamond', 1000),
    ('platinum', 300),
    ('gold', 125),
    ('silver', 50),
    ('bronze', 10),
)

# slug → presentation metadata. ``color`` is the rim/ribbon colour,
# ``metal`` the lighter face used for the seal gradient. Labels are lazy so
# they translate per-request when rendered.
# `slug` backs the SVG <defs> id prefix (avoids collisions when several badges
# share a page); `stars` (1–6) is the rank shown on the mission-patch.
TIER_META = {
    'diamond':     {'slug': 'diamond',     'label': _('Diamond'),     'color': '#b9a7ff', 'metal': '#ede8ff', 'stars': 6},
    'platinum':    {'slug': 'platinum',    'label': _('Platinum'),    'color': '#7fdfff', 'metal': '#dcf5ff', 'stars': 5},
    'gold':        {'slug': 'gold',        'label': _('Gold'),        'color': '#ffd45e', 'metal': '#fff1c2', 'stars': 4},
    'silver':      {'slug': 'silver',      'label': _('Silver'),      'color': '#cfd4dc', 'metal': '#f0f3f8', 'stars': 3},
    'bronze':      {'slug': 'bronze',      'label': _('Bronze'),      'color': '#cd7f32', 'metal': '#eab886', 'stars': 2},
    'participant': {'slug': 'participant', 'label': _('Participant'),  'color': '#9b8cff', 'metal': '#cbc1ff', 'stars': 1},
    'contributor': {'slug': 'contributor','label': _('Contributor'), 'color': '#9b8cff', 'metal': '#cbc1ff', 'stars': 1},
}


def tier_meta(slug):
    """Return presentation metadata for a tier/medal slug (never KeyErrors)."""
    return TIER_META.get(slug or 'contributor', TIER_META['contributor'])


# Alias matching the design handoff's helper name.
get_tier_meta = tier_meta


def global_tier(total_cp):
    """Lifetime-CP tier slug. Everyone with any contribution is at least a
    'contributor'; ``None`` only for users who have never scored."""
    if not total_cp:
        return None
    for slug, threshold in GLOBAL_TIERS:
        if total_cp >= threshold:
            return slug
    return 'contributor'


def individual_medal(rank):
    """Placement medal from a 1-based rank within a challenge."""
    return {1: 'gold', 2: 'silver', 3: 'bronze'}.get(rank, 'participant')


def collective_tier(challenge, total_cp=None):
    """Tier the whole community reached in a challenge, or ``None``."""
    total = challenge.total_cp() if total_cp is None else total_cp
    if total >= challenge.target_gold:
        return 'gold'
    if total >= challenge.target_silver:
        return 'silver'
    if total >= challenge.target_bronze:
        return 'bronze'
    return None


def _percentile(rank, total):
    """Top-X%% from a 1-based rank. rank 1 of 100 → 1 (top 1%)."""
    if not total:
        return None
    return max(1, round(rank / total * 100))


def _verify_url(request, code):
    from django.urls import reverse
    path = reverse('diploma_verify', kwargs={'code': code})
    return request.build_absolute_uri(path) if request is not None else path


# ── Context builders ─────────────────────────────────────────────────────
def general_context(user, profile, request=None):
    """Everything the general (all-time) diploma / badge needs."""
    total_cp = profile.controlPointsDone or 0
    tasks = profile.geoattempts_done or 0
    time_spent = profile.time_spent or 0

    # Rank inside the verified population (georeferencing.metrics); the
    # percentile is taken over population members with at least one CP.
    from . import metrics
    total_contributors = metrics.population().filter(controlPointsDone__gt=0).count()
    rank = metrics.global_rank(profile, 'cp')['rank'] if total_cp else None
    percentile = _percentile(rank, total_contributors) if rank else None

    slug = global_tier(total_cp)
    code = profile.ensure_diploma_code()
    return {
        'kind': 'general',
        'display_name': user.username,
        'tier': slug,
        'tier_meta': tier_meta(slug),
        'control_points': total_cp,
        'tasks': tasks,
        'time_spent': time_spent,
        'rank': rank,
        'total_contributors': total_contributors,
        'percentile': percentile,
        'issued_at': timezone.now(),
        'joined': user.date_joined,
        'dossier_id': f'LAN-{user.date_joined:%Y}-{user.id:05d}',
        'verify_code': code,
        'verify_url': _verify_url(request, code),
    }


def challenge_context(participant, request=None):
    """Everything a per-challenge diploma / badge needs."""
    challenge = participant.challenge
    cp = participant.cached_cp_count or 0
    participants = challenge.participants
    n_participants = participants.count()
    rank = participants.filter(cached_cp_count__gt=cp).count() + 1
    medal = individual_medal(rank)
    ctier = collective_tier(challenge)
    percentile = _percentile(rank, n_participants)

    code = participant.ensure_verify_code()
    return {
        'kind': 'challenge',
        'display_name': participant.user.username,
        'challenge': challenge,
        'medal': medal,
        'medal_meta': tier_meta(medal),
        'collective_tier': ctier,
        'collective_meta': tier_meta(ctier) if ctier else None,
        'control_points': cp,
        'rank': rank,
        'n_participants': n_participants,
        'percentile': percentile,
        # Active/upcoming/paused challenges still change → mark as provisional.
        'provisional': challenge.status != 'finished',
        'left_at': participant.left_at,
        'issued_at': timezone.now(),
        'joined': participant.user.date_joined,
        'dossier_id': f'LAN-{participant.user.date_joined:%Y}-'
                      f'{participant.user.id:05d}-CH-{challenge.id:04d}',
        'verify_code': code,
        'verify_url': _verify_url(request, code),
    }
