"""
Views for teams: public team page, create/join/leave actions and the
team leaderboard API.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, F, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from georeferencing.models import GeoAttemptsByUserByDay
from user_profile.models import UserProfile

from .models import Team, TeamMembership


def _active_membership(user):
    if not user.is_authenticated:
        return None
    return (TeamMembership.objects
            .filter(user=user, left_at__isnull=True)
            .select_related('team')
            .first())


def _close_active_membership(user):
    """Leave whatever team the user is currently in (no-op if none)."""
    TeamMembership.objects.filter(
        user=user, left_at__isnull=True,
    ).update(left_at=timezone.now())


def _enroll(team, user, role=TeamMembership.ROLE_MEMBER):
    """Join `team`, reusing the historical row if the user was here before."""
    _close_active_membership(user)
    membership, created = TeamMembership.objects.get_or_create(
        team=team, user=user, defaults={'role': role},
    )
    if not created:
        membership.left_at = None
        membership.joined_at = timezone.now()
        if role == TeamMembership.ROLE_OWNER:
            membership.role = role
        membership.save(update_fields=['left_at', 'joined_at', 'role'])
    return membership


def team_detail(request, slug):
    """Public team page: totals, rank among teams, member list."""
    team = get_object_or_404(Team, slug=slug)
    stats = team.stats()
    my_cp = stats['control_points'] or 0

    # Rank = teams whose current members add up to strictly more CP, + 1.
    better = 0
    others = Team.objects.exclude(pk=team.pk).annotate(
        cp=Sum('memberships__user__userprofile__controlPointsDone',
               filter=Q(memberships__left_at__isnull=True)),
    ).values_list('cp', flat=True)
    for cp in others:
        if (cp or 0) > my_cp:
            better += 1
    rank = better + 1

    memberships = (team.active_memberships()
                   .select_related('user')
                   .order_by('-joined_at'))
    profiles = {
        p.user_id: p
        for p in UserProfile.objects.filter(
            user_id__in=[m.user_id for m in memberships],
        )
    }
    members = []
    for m in memberships:
        prof = profiles.get(m.user_id)
        is_you = request.user.is_authenticated and m.user_id == request.user.id
        visible = bool(prof and prof.visible) or is_you
        members.append({
            'membership': m,
            'visible': visible,
            'username': m.user.username if visible else None,
            'profile': prof if visible else None,
            'is_you': is_you,
            'tasks': prof.geoattempts_done if prof else 0,
            'control_points': prof.controlPointsDone if prof else 0,
        })
    members.sort(key=lambda r: -(r['control_points'] or 0))

    mine = _active_membership(request.user)
    is_member = bool(mine and mine.team_id == team.pk)
    return render(request, 'team_detail.html', {
        'team': team,
        'stats': stats,
        'rank': rank,
        'members': members,
        'is_member': is_member,
        'is_owner': bool(is_member and mine.role == TeamMembership.ROLE_OWNER),
        'my_membership': mine,
    })


@login_required
@require_POST
def create_team(request):
    name = (request.POST.get('name') or '').strip()
    description = (request.POST.get('description') or '').strip()
    is_open = request.POST.get('is_open') != '0'
    if len(name) < 3 or len(name) > 60:
        messages.error(request, _('Team names must be between 3 and 60 characters.'))
        return redirect('/user-profile/')
    if Team.objects.filter(name__iexact=name).exists():
        messages.error(request, _('A team with that name already exists.'))
        return redirect('/user-profile/')
    team = Team.objects.create(
        name=name, description=description[:500],
        is_open=is_open, creator=request.user,
    )
    _enroll(team, request.user, role=TeamMembership.ROLE_OWNER)
    messages.success(request, _('Your team is ready. Share the invite code to grow it!'))
    return redirect('team_detail', slug=team.slug)


@login_required
@require_POST
def join_team(request):
    """Join by invite code (any team) or by slug (open teams only)."""
    code = (request.POST.get('invite_code') or '').strip().lower()
    slug = (request.POST.get('slug') or '').strip()
    team = None
    if code:
        team = Team.objects.filter(invite_code=code).first()
        if not team:
            messages.error(request, _('No team matches that invite code.'))
            return redirect(request.POST.get('next') or '/user-profile/')
    elif slug:
        team = Team.objects.filter(slug=slug, is_open=True).first()
        if not team:
            messages.error(request, _('This team is invite-only.'))
            return redirect(request.POST.get('next') or '/user-profile/')
    if not team:
        messages.error(request, _('Enter an invite code to join a team.'))
        return redirect(request.POST.get('next') or '/user-profile/')

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
    mine = _active_membership(request.user)
    if mine:
        _close_active_membership(request.user)
        messages.success(request, _('You have left %(team)s.') % {'team': mine.team.name})
    return redirect('/user-profile/')


def teams_ranking_api(request):
    """
    Team leaderboard.
    Query params:
      ordering: 'cp' (default) | 'tasks' — all-time only
      period:   'all' (default) | 'week' | 'month' — rolling windows ranked by
                tasks from daily activity of *current* members
    Response:
      { ordering, period, total_teams, my_team_slug, my_team_rank,
        rows: [{ rank, name, slug, is_open, members, tasks,
                 control_points }] }
    Full board, no pagination; all-time numbers cached for 5 minutes.
    """
    from django.core.cache import cache

    period = request.GET.get('period', 'all')
    if period not in ('all', 'week', 'month'):
        period = 'all'
    ordering = request.GET.get('ordering', 'cp')
    if period != 'all' or ordering not in ('cp', 'tasks'):
        ordering = 'tasks' if period != 'all' else 'cp'

    cache_key = f'teams_ranking:v1:{period}'
    raw = cache.get(cache_key)
    if raw is None:
        meta = {
            t['id']: t
            for t in Team.objects.values('id', 'name', 'slug', 'is_open').annotate(
                members=Count('memberships',
                              filter=Q(memberships__left_at__isnull=True)),
            )
        }
        # Same population as every other ranking (georeferencing.metrics):
        # only members with a verified e-mail score for their team.
        from georeferencing.metrics import verified_user_ids
        verified = verified_user_ids()
        if period == 'all':
            active_verified = Q(memberships__left_at__isnull=True,
                                memberships__user_id__in=verified)
            agg = (Team.objects
                   .values('id')
                   .annotate(
                       tasks=Sum('memberships__user__userprofile__geoattempts_done',
                                 filter=active_verified),
                       control_points=Sum('memberships__user__userprofile__controlPointsDone',
                                          filter=active_verified),
                   ))
            totals = {a['id']: a for a in agg}
        else:
            from user_profile.views import _period_start
            start = _period_start(period)
            agg = (GeoAttemptsByUserByDay.objects
                   .filter(date__gte=start, user_id__in=verified,
                           user__team_memberships__left_at__isnull=True)
                   .values(team_id=F('user__team_memberships__team_id'))
                   .annotate(tasks=Sum('numberGeoAttempts')))
            totals = {a['team_id']: a for a in agg}

        raw = []
        for team_id, m in meta.items():
            t = totals.get(team_id, {})
            raw.append({
                'name': m['name'],
                'slug': m['slug'],
                'is_open': m['is_open'],
                'members': m['members'],
                'tasks': t.get('tasks') or 0,
                'control_points': (t.get('control_points') or 0) if period == 'all' else None,
            })
        cache.set(cache_key, raw, 300)

    sort_key = {
        'cp': lambda r: r['control_points'] or 0,
        'tasks': lambda r: r['tasks'] or 0,
    }[ordering]
    rows = sorted(raw, key=sort_key, reverse=True)

    mine = _active_membership(request.user)
    my_team_slug = mine.team.slug if mine else None
    my_team_rank = None
    out = []
    for i, r in enumerate(rows, start=1):
        if my_team_slug and r['slug'] == my_team_slug:
            my_team_rank = i
        out.append({'rank': i, **r})

    return JsonResponse({
        'ordering': ordering,
        'period': period,
        'total_teams': len(out),
        'my_team_slug': my_team_slug,
        'my_team_rank': my_team_rank,
        'rows': out,
    })
