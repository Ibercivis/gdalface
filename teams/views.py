"""
Teams: public list, team page, join by code or invite link, create/leave,
owner management and the team leaderboard API.

Scoring (see TeamMembership): a member adds what they did *while a member*;
points earned inside the team stay banked on the team when they leave.
Only verified users score (same population as every ranking).
"""
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.db.models import Count, F, Q, Sum
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from georeferencing.metrics import verified_user_ids
from georeferencing.models import GeoAttemptsByUserByDay
from user_profile.models import UserProfile

from .models import Team, TeamMembership

RANKING_CACHE_KEYS = [f'teams_ranking:v3:{p}' for p in ('all', 'week', 'month')]


def _invalidate_rankings():
    cache.delete_many(RANKING_CACHE_KEYS)


def _safe_next(request, default='/teams/'):
    nxt = request.POST.get('next') or request.GET.get('next')
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        return nxt
    return default


def _active_membership(user):
    if not user.is_authenticated:
        return None
    return (TeamMembership.objects
            .filter(user=user, left_at__isnull=True)
            .select_related('team')
            .first())


def _leave_current_team(user, at=None):
    """Close the user's active membership (banking their contribution). If
    they owned the team, ownership passes to the longest-standing member."""
    mine = _active_membership(user)
    if not mine:
        return None
    at = at or timezone.now()
    team = mine.team
    was_owner = mine.role == TeamMembership.ROLE_OWNER
    mine.close(at)
    if was_owner:
        heir = (team.active_memberships().exclude(pk=mine.pk)
                .order_by('joined_at').first())
        if heir:
            heir.role = TeamMembership.ROLE_OWNER
            heir.save(update_fields=['role'])
    return mine


def _enroll(team, user, role=TeamMembership.ROLE_MEMBER):
    """Join `team`, reusing the historical row if the user was here before.
    Takes a fresh scoring baseline; earlier stints stay banked on the row."""
    with transaction.atomic():
        _leave_current_team(user)
        membership, created = TeamMembership.objects.get_or_create(
            team=team, user=user, defaults={'role': role},
        )
        membership.left_at = None
        membership.joined_at = timezone.now()
        if role == TeamMembership.ROLE_OWNER:
            membership.role = role
        membership.take_baseline()
        membership.save()
    _invalidate_rankings()
    return membership


def _require_owner(request, team):
    mine = _active_membership(request.user)
    if not (mine and mine.team_id == team.pk and mine.role == TeamMembership.ROLE_OWNER):
        raise Http404
    return mine


def _can_edit(user, team):
    """Name / description / open-or-closed: the current owner or the team's creator
    (so a creator who left, or whose team is empty, can still fix it)."""
    if not user.is_authenticated:
        return False
    if team.creator_id == user.pk:
        return True
    mine = _active_membership(user)
    return bool(mine and mine.team_id == team.pk and mine.role == TeamMembership.ROLE_OWNER)


def _rows_with_weekly_trend():
    """All teams (unsorted, see _rank_with_trend), each with what changed in the last 7 days
    (same rolling window as the weekly ranking): new members, new tasks, new
    CP and places gained/lost versus the table as it stood a week ago.

    Nothing is snapshotted: the week's tasks/CP come from the per-day rows of
    each member, counted from the later of window start / join date (and up to
    the day they left), capped at what the membership actually contributed.
    Last week's table is today's totals minus those deltas."""
    start = _period_start('week')
    verified = set(verified_user_ids())
    teams = list(Team.objects.prefetch_related('memberships'))
    daily = {}
    user_ids = {m.user_id for t in teams for m in t.memberships.all()}
    for uid, d, n, c in (GeoAttemptsByUserByDay.objects
                         .filter(user_id__in=user_ids, date__gte=start)
                         .values_list('user_id', 'date', 'numberGeoAttempts', 'controlPoints')):
        daily.setdefault(uid, []).append((d, n or 0, c or 0))

    rows = []
    for t in teams:
        members = new_members = tasks = cp = w_tasks = w_cp = 0
        for m in t.memberships.all():
            joined = timezone.localtime(m.joined_at).date()
            left = timezone.localtime(m.left_at).date() if m.left_at else None
            if left is None:
                members += 1
                if joined >= start:
                    new_members += 1
            if m.user_id not in verified:
                continue
            c = m.contribution()
            tasks += c['tasks']; cp += c['cp']
            if left is not None and left < start:
                continue
            since = max(start, joined)
            mt = mc = 0
            for d, n, k in daily.get(m.user_id, ()):
                if d >= since and (left is None or d <= left):
                    mt += n; mc += k
            w_tasks += min(mt, c['tasks']); w_cp += min(mc, c['cp'])
        rows.append({
            'team': t, 'members': members, 'tasks': tasks, 'cp': cp,
            'new_members': new_members, 'new_tasks': w_tasks, 'new_cp': w_cp,
            'is_new': timezone.localtime(t.created_at).date() >= start,
        })

    return rows


def _rank_with_trend(rows, key='cp'):
    """Sort team rows by `key` ('cp' | 'tasks') and stamp rank + places
    gained/lost versus the same ordering a week ago (teams created this week
    are 'new' and have no previous place)."""
    new_key = 'new_' + key
    name = lambda r: r['team'].name.lower()
    rows = sorted(rows, key=lambda r: (-r[key], -r['members'], name(r)))
    before = sorted(
        (r for r in rows if not r['is_new']),
        key=lambda r: (-(r[key] - r[new_key]), -(r['members'] - r['new_members']), name(r)),
    )
    prev_rank = {r['team'].pk: i + 1 for i, r in enumerate(before)}
    for i, r in enumerate(rows):
        r['rank'] = i + 1
        prev = prev_rank.get(r['team'].pk)
        r['rank_change'] = (prev - r['rank']) if prev else 0
        r['rank_change_abs'] = abs(r['rank_change'])
    return rows


# ── Pages ────────────────────────────────────────────────────────────────
def team_list(request):
    """Public directory: open teams first, searchable; create/join forms for
    logged-in users without a team."""
    q = (request.GET.get('q') or '').strip()
    rows = _rank_with_trend(_rows_with_weekly_trend())
    if q:
        ql = q.lower()
        rows = [r for r in rows
                if ql in r['team'].name.lower() or ql in (r['team'].description or '').lower()]
    mine = _active_membership(request.user)
    return render(request, 'team_list.html', {
        'rows': rows, 'q': q, 'my_membership': mine,
        'my_stats': mine.team.stats() if mine else None,
    })


def team_detail(request, slug):
    """Public team page: totals, rank among teams, member list, owner tools."""
    team = get_object_or_404(Team, slug=slug)
    stats = team.stats()
    my_cp = stats['control_points']
    better = sum(1 for t in Team.objects.exclude(pk=team.pk) if t.stats()['control_points'] > my_cp)
    rank = better + 1

    verified = set(verified_user_ids())
    memberships = team.active_memberships().select_related('user').order_by('joined_at')
    profiles = {p.user_id: p for p in UserProfile.objects.filter(user_id__in=[m.user_id for m in memberships])}
    members = []
    for m in memberships:
        prof = profiles.get(m.user_id)
        is_you = request.user.is_authenticated and m.user_id == request.user.id
        visible = bool(prof and prof.visible) or is_you
        c = m.contribution()
        members.append({
            'membership': m, 'visible': visible, 'is_you': is_you,
            'username': m.user.username if visible else None,
            'profile': prof if visible else None,
            'tasks': c['tasks'], 'control_points': c['cp'],
            'lifetime_cp': prof.controlPointsDone if prof else 0,
            'verified': m.user_id in verified,
        })
    members.sort(key=lambda r: (-r['control_points'], r['membership'].joined_at))

    mine = _active_membership(request.user)
    is_member = bool(mine and mine.team_id == team.pk)
    is_owner = bool(is_member and mine.role == TeamMembership.ROLE_OWNER)
    invite_url = request.build_absolute_uri(f'/teams/join/?code={team.invite_code}')
    return render(request, 'team_detail.html', {
        'team': team, 'stats': stats, 'rank': rank, 'members': members,
        'is_member': is_member, 'is_owner': is_owner, 'can_edit': _can_edit(request.user, team), 'my_membership': mine,
        'owner': team.owner(), 'invite_url': invite_url if is_member else None,
    })


# ── Membership actions ───────────────────────────────────────────────────
@login_required
@require_POST
def create_team(request):
    name = (request.POST.get('name') or '').strip()
    description = (request.POST.get('description') or '').strip()[:500]
    is_open = request.POST.get('is_open') in ('1', 'on', 'true', 'True')
    back = _safe_next(request)
    if len(name) < 3 or len(name) > 60:
        messages.error(request, _('Team names must be between 3 and 60 characters.'))
        return redirect(back)
    if Team.objects.filter(name__iexact=name).exists():
        messages.error(request, _('A team with that name already exists.'))
        return redirect(back)
    try:
        with transaction.atomic():
            team = Team.objects.create(name=name, description=description,
                                       is_open=is_open, creator=request.user)
    except IntegrityError:
        messages.error(request, _('A team with that name already exists.'))
        return redirect(back)
    _enroll(team, request.user, role=TeamMembership.ROLE_OWNER)
    messages.success(request, _('Your team is ready. Share the invite link to grow it!'))
    return redirect('team_detail', slug=team.slug)


def join_team(request):
    """GET /teams/join/?code=…  → confirmation page for an invite link.
    POST with invite_code (any team) or slug (open teams only) → join."""
    if request.method == 'GET':
        code = (request.GET.get('code') or '').strip().lower()
        team = Team.objects.filter(invite_code=code).first() if code else None
        if not team:
            messages.error(request, _('No team matches that invite code.'))
            return redirect('team_list')
        if not request.user.is_authenticated:
            return redirect(f"/accounts/login?next=/teams/join/?code={team.invite_code}")
        mine = _active_membership(request.user)
        return render(request, 'team_join_confirm.html', {
            'team': team, 'stats': team.stats(),
            'already': bool(mine and mine.team_id == team.pk),
            'current': mine.team if (mine and mine.team_id != team.pk) else None,
        })
    if not request.user.is_authenticated:
        return redirect('/accounts/login?next=/teams/')
    code = (request.POST.get('invite_code') or '').strip().lower()
    slug = (request.POST.get('slug') or '').strip()
    back = _safe_next(request)
    team = None
    if code:
        team = Team.objects.filter(invite_code=code).first()
        if not team:
            messages.error(request, _('No team matches that invite code.'))
            return redirect(back)
    elif slug:
        team = Team.objects.filter(slug=slug, is_open=True).first()
        if not team:
            messages.error(request, _('This team is invite-only.'))
            return redirect(back)
    if not team:
        messages.error(request, _('Enter an invite code to join a team.'))
        return redirect(back)

    mine = _active_membership(request.user)
    if mine and mine.team_id == team.pk:
        messages.info(request, _('You are already a member of this team.'))
    else:
        _enroll(team, request.user)
        messages.success(request, _('Welcome to %(team)s!') % {'team': team.name})
    return redirect('team_detail', slug=team.slug)


@login_required
@require_POST
def leave_team(request):
    mine = _leave_current_team(request.user)
    if mine:
        _invalidate_rankings()
        messages.success(request, _('You have left %(team)s. The points you earned there stay with the team.') % {'team': mine.team.name})
    return redirect(_safe_next(request, '/teams/'))


# ── Owner tools ──────────────────────────────────────────────────────────
@login_required
@require_POST
def team_edit(request, slug):
    team = get_object_or_404(Team, slug=slug)
    if not _can_edit(request.user, team):
        raise Http404
    name = (request.POST.get('name') or team.name).strip()
    if not 3 <= len(name) <= 60:
        messages.error(request, _('Team names must be between 3 and 60 characters.'))
        return redirect('team_detail', slug=team.slug)
    if Team.objects.filter(name__iexact=name).exclude(pk=team.pk).exists():
        messages.error(request, _('A team with that name already exists.'))
        return redirect('team_detail', slug=team.slug)
    team.name = name
    team.description = (request.POST.get('description') or '').strip()[:500]
    team.is_open = request.POST.get('is_open') in ('1', 'on', 'true', 'True')
    team.save(update_fields=['name', 'description', 'is_open'])
    _invalidate_rankings()
    messages.success(request, _('Team updated.'))
    return redirect('team_detail', slug=team.slug)


@login_required
@require_POST
def team_rotate_code(request, slug):
    team = get_object_or_404(Team, slug=slug)
    _require_owner(request, team)
    team.rotate_invite_code()
    messages.success(request, _('New invite code generated. Old links no longer work.'))
    return redirect('team_detail', slug=team.slug)


@login_required
@require_POST
def team_remove_member(request, slug):
    team = get_object_or_404(Team, slug=slug)
    _require_owner(request, team)
    m = team.active_memberships().filter(pk=request.POST.get('membership_id')).select_related('user').first()
    if not m or m.user_id == request.user.id:
        raise Http404
    m.close()
    _invalidate_rankings()
    messages.success(request, _('%(user)s was removed from the team.') % {'user': m.user.username})
    return redirect('team_detail', slug=team.slug)


@login_required
@require_POST
def team_transfer(request, slug):
    team = get_object_or_404(Team, slug=slug)
    mine = _require_owner(request, team)
    heir = team.active_memberships().filter(pk=request.POST.get('membership_id')).exclude(pk=mine.pk).select_related('user').first()
    if not heir:
        raise Http404
    heir.role = TeamMembership.ROLE_OWNER
    heir.save(update_fields=['role'])
    mine.role = TeamMembership.ROLE_MEMBER
    mine.save(update_fields=['role'])
    messages.success(request, _('%(user)s is now the team owner.') % {'user': heir.user.username})
    return redirect('team_detail', slug=team.slug)


@login_required
@require_POST
def team_delete(request, slug):
    team = get_object_or_404(Team, slug=slug)
    _require_owner(request, team)
    if team.active_memberships().count() > 1:
        messages.error(request, _('Remove the other members before deleting the team.'))
        return redirect('team_detail', slug=team.slug)
    name = team.name
    team.delete()
    _invalidate_rankings()
    messages.success(request, _('Team %(team)s deleted.') % {'team': name})
    return redirect('team_list')


# ── Ranking API ──────────────────────────────────────────────────────────
def _period_start(period):
    from user_profile.views import _period_start as ps
    return ps(period)


def teams_ranking_api(request):
    """
    GET /api/v1/ranking/teams/?period=all|week|month&ordering=cp|tasks
    all-time: Σ membership contributions (active delta + banked) of verified users.
    week/month: GeoAttemptsByUserByDay of current verified members from the
    later of window start / their join date.
    """
    period = request.GET.get('period', 'all')
    if period not in ('all', 'week', 'month'):
        period = 'all'
    ordering = request.GET.get('ordering', 'cp')
    if ordering not in ('cp', 'tasks'):
        ordering = 'cp'

    cache_key = f'teams_ranking:v3:{period}'
    raw = cache.get(cache_key)
    if raw is None:
        raw = []
        if period == 'all':
            for r in _rows_with_weekly_trend():
                t = r['team']
                raw.append({'name': t.name, 'slug': t.slug, 'is_open': t.is_open,
                            'members': r['members'], 'tasks': r['tasks'], 'control_points': r['cp'],
                            'new_members': r['new_members'], 'new_tasks': r['new_tasks'],
                            'new_cp': r['new_cp'], 'is_new': r['is_new']})
        else:
            verified = set(verified_user_ids())
            start = _period_start(period)
            for team in Team.objects.prefetch_related('memberships'):
                active = [m for m in team.memberships.all() if m.left_at is None]
                tasks = cp = 0
                for m in active:
                    if m.user_id not in verified:
                        continue
                    since = max(start, m.joined_at.date())
                    agg = (GeoAttemptsByUserByDay.objects
                           .filter(user_id=m.user_id, date__gte=since)
                           .aggregate(t=Sum('numberGeoAttempts'), c=Sum('controlPoints')))
                    tasks += agg['t'] or 0
                    cp += agg['c'] or 0
                raw.append({'name': team.name, 'slug': team.slug, 'is_open': team.is_open,
                            'members': len(active), 'tasks': tasks, 'control_points': cp})
        cache.set(cache_key, raw, 300)

    key = 'control_points' if ordering == 'cp' else 'tasks'
    rows = sorted(raw, key=lambda r: (-r[key], -r['members'], r['name'].lower()))
    my_slug = None
    my_rank = None
    mine = _active_membership(request.user)
    if mine:
        my_slug = mine.team.slug
        my_rank = next((i + 1 for i, r in enumerate(rows) if r['slug'] == my_slug), None)
    for i, r in enumerate(rows):
        r['rank'] = i + 1
    if period == 'all':
        # Places gained/lost vs the same ordering a week ago (rolling 7 days).
        new_key = 'new_cp' if ordering == 'cp' else 'new_tasks'
        before = sorted(
            (r for r in rows if not r['is_new']),
            key=lambda r: (-(r[key] - r[new_key]), -(r['members'] - r['new_members']), r['name'].lower()))
        prev_rank = {r['slug']: i + 1 for i, r in enumerate(before)}
        for r in rows:
            prev = prev_rank.get(r['slug'])
            r['rank_change'] = (prev - r['rank']) if prev else 0
    return JsonResponse({
        'ordering': ordering, 'period': period, 'total_teams': len(rows),
        'my_team_slug': my_slug, 'my_team_rank': my_rank, 'rows': rows,
    })
