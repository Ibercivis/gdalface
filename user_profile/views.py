"""
This module contains the views for the user_profile app
"""
from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.db.models import Sum, Count, Avg, F
from django.http import JsonResponse, HttpResponse, Http404
from georeferencing.models import GeoAttempt, GeoAttemptsByUserByDay, ChallengeParticipant, DiplomaDownload
from user_profile.models import UserProfile
from user_profile.forms import UserProfileForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from datetime import date
from django.utils.translation import gettext as _, ngettext


def _wants_json(request):
    """True if the client asked for JSON (AJAX from the profile modal)."""
    accept = request.META.get('HTTP_ACCEPT', '')
    return 'application/json' in accept or request.headers.get('X-Requested-With') == 'XMLHttpRequest'

User = get_user_model()

# Create your views here.
def user_view(request):
    """
    Handles the user profile view.

    This view checks if the user is authenticated and retrieves 
    various user profile attributes such as time spent, geo attempts done, 
    control points done...
    These attributes are then passed to the 'user.html' 
    template for rendering.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        HttpResponse: The rendered 'user.html' template with user 
        profile context if the user is authenticated.
        Otherwise, it returns the 'user.html' template without 
        additional context.
    """
    user = request.user
    if user.is_authenticated:
        # Obtener o crear el perfil de usuario si no existe
        try:
            profile = user.userprofile
        except UserProfile.DoesNotExist:
            # Si el perfil no existe, lo creamos
            profile = UserProfile.objects.create(user=user)
        
        from georeferencing import metrics
        totals = metrics.user_totals(profile)
        time = convert_time_spent(totals['seconds'])
        geo = totals['tasks']
        cp = totals['cp']
        che = profile.cheating

        # Streaks (shared definition; an empty today does not break the run).
        streak_current, streak_best = metrics.streak(user)

        # Contribution heatmap range (last 12 months up to today).
        today = date.today()
        heatmap_end = today.strftime("%B %Y")
        heatmap_start = date(today.year - 1, today.month, 1).strftime("%B %Y")

        # Ranks inside the verified population (ties share a rank).
        ranks = metrics.all_ranks(profile)
        user_task_position = ranks['tasks']['rank']
        user_points_position = ranks['cp']['rank']
        user_time_position = ranks['time']['rank']
        total_users = ranks['cp']['total']

        # Share of the project totals (anonymous contributions included in
        # the denominator, same numbers as the homepage).
        project = metrics.project_totals()
        user_tasks_percentage = min(100, geo / project['tasks_done'] * 100) if project['tasks_done'] else 0
        user_time_percentage = min(100, totals['seconds'] / project['seconds'] * 100) if project['seconds'] else 0
        user_control_points_percentage = min(100, cp / project['control_points'] * 100) if project['control_points'] else 0

        # Visited places: first control point of each completed attempt
        visited_places = []
        for attempt in GeoAttempt.objects.filter(assignedUser=user, status='DONE').select_related('image'):
            try:
                cps = attempt.controlPoints
                if cps and isinstance(cps, list) and len(cps) > 0:
                    first = cps[0]
                    lat, lon = first.get('lat'), first.get('lon')
                    if lat is not None and lon is not None:
                        visited_places.append({
                            'lat': lat,
                            'lon': lon,
                            'name': attempt.image.name if attempt.image_id else '',
                            'small_url': attempt.image.smallImageURL if attempt.image_id else '',
                        })
            except Exception:
                pass

        # Challenge enrollments for this user (current + history),
        # ranked within each challenge by cached_cp_count. Each row carries the
        # badge data (placement medal + collective tier) for the profile grid.
        from georeferencing import diplomas
        my_enrollments_qs = ChallengeParticipant.objects.filter(
            user=user,
        ).select_related('challenge').order_by('-joined_at')
        my_enrollments = []
        for ep in my_enrollments_qs:
            ch = ep.challenge
            better = ch.participants.filter(
                cached_cp_count__gt=ep.cached_cp_count,
            ).count()
            rank = better + 1
            medal = diplomas.individual_medal(rank)
            ctier = diplomas.collective_tier(ch)
            my_enrollments.append({
                'enrollment': ep,
                'challenge': ch,
                'rank': rank,
                'medal_meta': diplomas.tier_meta(medal),
                'collective_meta': diplomas.tier_meta(ctier) if ctier else None,
                'provisional': ch.status != 'finished',
            })

        # Active team membership (one at most) for the "My team" card.
        from teams.models import TeamMembership
        my_team = (TeamMembership.objects
                   .filter(user=user, left_at__isnull=True)
                   .select_related('team')
                   .first())

        # General (all-time) badge for the badge grid header.
        _gtier = diplomas.global_tier(profile.controlPointsDone or 0)
        general_badge = {
            'tier_meta': diplomas.tier_meta(_gtier or 'contributor'),
            'control_points': profile.controlPointsDone or 0,
        }

        context = {
            'user': user,
            'profile': profile,
            'time': time,
            'geo': geo,
            'cp': cp,
            'visited_places': visited_places,
            'che': che,
            'my_enrollments': my_enrollments,
            'my_team': my_team,
            'general_badge': general_badge,
            'streak_current': streak_current,
            'streak_best': streak_best,
            'heatmap_start': heatmap_start,
            'heatmap_end': heatmap_end,
            'user_task_position': user_task_position,
            'user_time_position': user_time_position,
            'user_points_position': user_points_position,
            'total_users': total_users,
            'user_tasks_percentage': round(user_tasks_percentage, 2),
            'user_time_percentage': round(user_time_percentage, 2),
            'user_control_points_percentage': round(user_control_points_percentage, 2),
            'profile_form': UserProfileForm(instance=profile),
        }
        return render(request, 'user.html', context)
    # Anonymous → send them through login with a return-back next param.
    from urllib.parse import urlencode
    from django.urls import reverse
    return redirect(reverse('account_login') + '?' + urlencode({'next': '/user-profile/'}))


def edit_profile(request):
    """
    View for editing user profile.
    
    Handles both GET and POST requests. For GET requests, it shows the profile
    editing form. For POST requests, it validates the form data and updates
    the profile if valid.
    
    Args:
        request: The HTTP request object
        
    Returns:
        HttpResponse: The rendered 'edit_profile.html' template or a redirect to the profile page
    """
    if not request.user.is_authenticated:
        return redirect('/accounts/login/')
    
    try:
        profile = request.user.userprofile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=request.user)
    
    if request.method == 'POST':
        was_subscribed = profile.newsletter_subscribed
        form = UserProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            obj = form.save(commit=False)
            # Optional explicit clear of the profile picture from the modal.
            if request.POST.get('clear_pic') == '1':
                if obj.profile_pic:
                    obj.profile_pic.delete(save=False)
                obj.profile_pic = None
            # Newsletter consent timestamps + token rotation.
            from django.utils import timezone as _tz
            now = _tz.now()
            if obj.newsletter_subscribed and not was_subscribed:
                obj.newsletter_subscribed_at = now
                obj.newsletter_unsubscribed_at = None
                obj.ensure_newsletter_token()
            elif was_subscribed and not obj.newsletter_subscribed:
                obj.newsletter_unsubscribed_at = now
            obj.save()
            if _wants_json(request):
                return JsonResponse({'ok': True})
            messages.success(request, _('Your profile has been updated successfully!'))
            return redirect('/user-profile/')
        else:
            if _wants_json(request):
                return JsonResponse({'ok': False, 'errors': form.errors}, status=400)
    else:
        form = UserProfileForm(instance=profile)

    return render(request, 'edit_profile.html', {
        'form': form,
        'user': request.user
    })


def convert_time_spent(total_seconds):
    """
    Convierte el tiempo total en segundos a un formato legible con días, horas y minutos.
    Solo muestra las unidades de tiempo que son necesarias (por ejemplo, no muestra "0 días").
    
    Args:
        total_seconds: Tiempo total en segundos
        
    Returns:
        str: Tiempo formateado en una cadena legible
    """
    # Calculate days, hours, minutes
    days, remainder = divmod(total_seconds, 86400)  # 86400 seconds = 1 day
    hours, remainder = divmod(remainder, 3600)      # 3600 seconds = 1 hour
    minutes = remainder // 60                        # 60 seconds = 1 minute
    
    # Crear partes del tiempo con formato
    time_parts = []
    
    # Solo agregar unidades si son mayores que 0
    if days > 0:
        time_parts.append(ngettext("%(count)d day", "%(count)d days", days) % {'count': days})
    if hours > 0:
        time_parts.append(ngettext("%(count)d hour", "%(count)d hours", hours) % {'count': hours})
    if minutes > 0 or (days == 0 and hours == 0):  # Siempre mostramos minutos si no hay días ni horas
        time_parts.append(ngettext("%(count)d minute", "%(count)d minutes", minutes) % {'count': minutes})

    # Unir las partes con comas y "and" para la última parte
    if len(time_parts) > 1:
        return ", ".join(time_parts[:-1]) + _(" and ") + time_parts[-1]
    elif len(time_parts) == 1:
        return time_parts[0]
    else:
        return _("0 minutes")


def _verified_user_ids():
    """user_ids with at least one allauth-verified email — the population that
    counts for every public ranking."""
    from allauth.account.models import EmailAddress
    return EmailAddress.objects.filter(
        verified=True,
    ).values_list('user_id', flat=True)


def _period_start(period):
    """Start date for a rolling ranking period, or None for all-time.
    Periods are rolling windows (last 7 / last 30 days including today) so the
    board never resets to an empty table at midnight on Monday."""
    from datetime import timedelta
    if period == 'week':
        return date.today() - timedelta(days=6)
    if period == 'month':
        return date.today() - timedelta(days=29)
    return None


def _period_ranking(request, period, page_size):
    """Ranking over a rolling window, built from GeoAttemptsByUserByDay.
    Only tasks are tracked per-day, so the metric is always 'tasks' here.
    Returns the same response shape as the all-time ranking; control_points
    and time_seconds are null in the rows."""
    start = _period_start(period)
    verified = _verified_user_ids()
    agg = (GeoAttemptsByUserByDay.objects
           .filter(date__gte=start, user_id__in=verified)
           .values('user_id')
           .annotate(metric=Sum('numberGeoAttempts'))
           .filter(metric__gt=0)
           .order_by('-metric', 'user_id'))

    total_users = agg.count()
    total_pages = max(1, (total_users + page_size - 1) // page_size)

    my_rank = None
    my_metric = None
    my_username = None
    if request.user.is_authenticated:
        my_metric = (GeoAttemptsByUserByDay.objects
                     .filter(date__gte=start, user=request.user)
                     .aggregate(total=Sum('numberGeoAttempts'))['total']) or 0
        if my_metric > 0:
            my_rank = agg.filter(metric__gt=my_metric).count() + 1
            my_username = request.user.username
        else:
            my_metric = None

    if request.GET.get('jump_to_me') == '1' and my_rank:
        page = ((my_rank - 1) // page_size) + 1
    else:
        try:
            page = max(1, int(request.GET.get('page', 1)))
        except (TypeError, ValueError):
            page = 1
    page = min(page, total_pages)

    offset = (page - 1) * page_size
    window = list(agg[offset:offset + page_size])
    profiles = {
        p.user_id: p
        for p in UserProfile.objects.select_related('user').filter(
            user_id__in=[w['user_id'] for w in window],
        )
    }

    rows = []
    for i, w in enumerate(window):
        prof = profiles.get(w['user_id'])
        if not prof:
            continue
        rank = offset + i + 1
        is_you = (request.user.is_authenticated and prof.user_id == request.user.id)
        visible = bool(prof.visible) or is_you
        country_obj = prof.country if visible else None
        rows.append({
            'rank': rank,
            'username': prof.user.username if visible else None,
            'country': country_obj.name if country_obj else None,
            'country_code': country_obj.code.lower() if country_obj else None,
            'profile_pic_url': prof.profile_pic.url if (visible and prof.profile_pic) else None,
            'visible': visible,
            'is_you': is_you,
            'tasks': w['metric'],
            'control_points': None,
            'time_seconds': None,
            'time_pretty': None,
        })

    return JsonResponse({
        'ordering': 'tasks',
        'period': period,
        'page': page,
        'page_size': page_size,
        'total_pages': total_pages,
        'total_users': total_users,
        'my_rank': my_rank,
        'my_metric': my_metric,
        'my_username': my_username,
        'rows': rows,
    })


def ranking_api(request):
    """
    Paginated ranking endpoint.
    Query params:
      ordering: 'cp' (default) | 'tasks' | 'time'
      period:   'all' (default) | 'week' | 'month' — rolling windows built from
                daily activity; non-all periods rank by tasks only.
      page:     1-based page number
      page_size: optional override (default 20, max 100)
      jump_to_me: '1' → return the page that contains the requesting user

    Response:
      {
        ordering, period, page, page_size, total_pages, total_users,
        my_rank, my_metric, my_username,
        rows: [
          { rank, username, country, country_code, profile_pic_url,
            visible, is_you, tasks, control_points, time_seconds, time_pretty }
        ]
      }
    Invisible profiles are still counted but anonymised in the rows.
    """
    try:
        page_size_pre = max(1, min(100, int(request.GET.get('page_size', 20))))
    except (TypeError, ValueError):
        page_size_pre = 20
    period = request.GET.get('period', 'all')
    if period in ('week', 'month'):
        return _period_ranking(request, period, page_size_pre)

    ordering = request.GET.get('ordering', 'cp')
    field_map = {
        'cp':    'controlPointsDone',
        'tasks': 'geoattempts_done',
        'time':  'time_spent',
    }
    field = field_map.get(ordering, 'controlPointsDone')

    page_size = page_size_pre

    # Only include users who have confirmed at least one email address.
    base = UserProfile.objects.select_related('user').filter(
        user_id__in=_verified_user_ids(),
    )
    total_users = base.count()
    total_pages = max(1, (total_users + page_size - 1) // page_size)

    my_rank = None
    my_metric = None
    my_username = None
    if request.user.is_authenticated:
        try:
            mine = UserProfile.objects.only('id', field).get(user=request.user)
            my_metric = getattr(mine, field, 0) or 0
            # Rank = number of profiles with strictly greater metric + 1.
            my_rank = base.filter(**{f'{field}__gt': my_metric}).count() + 1
            my_username = request.user.username
        except UserProfile.DoesNotExist:
            pass

    if request.GET.get('jump_to_me') == '1' and my_rank:
        page = ((my_rank - 1) // page_size) + 1
    else:
        try:
            page = max(1, int(request.GET.get('page', 1)))
        except (TypeError, ValueError):
            page = 1
    page = min(page, total_pages)

    offset = (page - 1) * page_size
    qs = base.order_by(f'-{field}', 'id')[offset:offset + page_size]

    rows = []
    for i, prof in enumerate(qs):
        rank = offset + i + 1
        is_you = (request.user.is_authenticated and prof.user_id == request.user.id)
        # Always count rank position; hide PII for invisible profiles
        # (unless it's the requesting user looking at themselves).
        visible = bool(prof.visible) or is_you
        country_obj = prof.country if visible else None
        rows.append({
            'rank': rank,
            'username': prof.user.username if visible else None,
            'country': country_obj.name if country_obj else None,
            'country_code': country_obj.code.lower() if country_obj else None,
            'profile_pic_url': prof.profile_pic.url if (visible and prof.profile_pic) else None,
            'visible': visible,
            'is_you': is_you,
            'tasks': prof.geoattempts_done,
            'control_points': prof.controlPointsDone,
            'time_seconds': prof.time_spent,
            'time_pretty': convert_time_spent(prof.time_spent),
        })

    return JsonResponse({
        'ordering': ordering,
        'period': 'all',
        'page': page,
        'page_size': page_size,
        'total_pages': total_pages,
        'total_users': total_users,
        'my_rank': my_rank,
        'my_metric': my_metric,
        'my_username': my_username,
        'rows': rows,
    })


def country_ranking_api(request):
    """
    Country leaderboard. Aggregates verified, ranking-visible profiles that
    have a country set; profiles without a country simply don't score.
    Query params:
      ordering: 'cp' (default) | 'tasks' | 'cp_per_user' — all-time only
      period:   'all' (default) | 'week' | 'month' — rolling windows ranked
                by tasks (the only per-day metric)
    Response:
      {
        ordering, period, total_countries,
        my_country_code, my_country_rank, my_country_missing,
        rows: [{ rank, country, country_code, users, tasks,
                 control_points, cp_per_user }]
      }
    Returns the full board (≤ ~250 rows); no pagination.
    All-time numbers come from a short server-side cache (5 min).
    """
    from django.core.cache import cache
    from django_countries import countries as COUNTRIES

    period = request.GET.get('period', 'all')
    if period not in ('all', 'week', 'month'):
        period = 'all'
    ordering = request.GET.get('ordering', 'cp')
    if period != 'all' or ordering not in ('cp', 'tasks', 'cp_per_user'):
        ordering = 'tasks' if period != 'all' else 'cp'

    cache_key = f'country_ranking:v1:{period}'
    raw = cache.get(cache_key)
    if raw is None:
        verified = _verified_user_ids()
        if period == 'all':
            # Population rule (georeferencing.metrics): verified users count,
            # invisible ones included — they are never named, only aggregated.
            agg = (UserProfile.objects
                   .filter(user_id__in=verified)
                   .exclude(country__isnull=True).exclude(country='')
                   .values('country')
                   .annotate(users=Count('id'),
                             tasks=Sum('geoattempts_done'),
                             control_points=Sum('controlPointsDone'))
                   .order_by())
        else:
            start = _period_start(period)
            agg = (GeoAttemptsByUserByDay.objects
                   .filter(date__gte=start, user_id__in=verified)
                   .exclude(user__userprofile__country__isnull=True)
                   .exclude(user__userprofile__country='')
                   .values(country=F('user__userprofile__country'))
                   .annotate(users=Count('user_id', distinct=True),
                             tasks=Sum('numberGeoAttempts'))
                   .order_by())
        raw = []
        for row in agg:
            cp = row.get('control_points') or 0
            users = row['users'] or 0
            raw.append({
                'country_code': str(row['country']).lower(),
                'users': users,
                'tasks': row['tasks'] or 0,
                'control_points': cp if period == 'all' else None,
                'cp_per_user': round(cp / users, 1) if (period == 'all' and users) else None,
            })
        cache.set(cache_key, raw, 300)

    sort_key = {
        'cp': lambda r: r['control_points'] or 0,
        'tasks': lambda r: r['tasks'] or 0,
        'cp_per_user': lambda r: r['cp_per_user'] or 0,
    }[ordering]
    rows = sorted(raw, key=sort_key, reverse=True)

    my_country_code = None
    my_country_missing = False
    if request.user.is_authenticated:
        prof = UserProfile.objects.filter(user=request.user).first()
        if prof and prof.country:
            my_country_code = prof.country.code.lower()
        else:
            my_country_missing = True

    my_country_rank = None
    out = []
    for i, r in enumerate(rows, start=1):
        name = COUNTRIES.name(r['country_code'].upper())
        if my_country_code and r['country_code'] == my_country_code:
            my_country_rank = i
        out.append({'rank': i, 'country': str(name) or r['country_code'].upper(), **r})

    return JsonResponse({
        'ordering': ordering,
        'period': period,
        'total_countries': len(out),
        'my_country_code': my_country_code,
        'my_country_rank': my_country_rank,
        'my_country_missing': my_country_missing,
        'rows': out,
    })


def cookies_consent_api(request):
    """
    Persist cookie banner choice on UserProfile when the visitor is signed in.
    Anonymous visitors keep their preference in the `lan_consent` cookie only.
    Body: {"functional": bool, "analytics": bool}.
    """
    import json
    from django.utils import timezone as _tz
    from django.views.decorators.csrf import csrf_protect

    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'method_not_allowed'}, status=405)
    if not request.user.is_authenticated:
        return JsonResponse({'ok': True, 'persisted': False})
    try:
        data = json.loads(request.body or b'{}')
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'invalid_json'}, status=400)
    profile, _c = UserProfile.objects.get_or_create(user=request.user)
    profile.cookies_functional_consent = bool(data.get('functional'))
    profile.cookies_analytics_consent = bool(data.get('analytics'))
    profile.cookies_consent_at = _tz.now()
    profile.save(update_fields=[
        'cookies_functional_consent', 'cookies_analytics_consent', 'cookies_consent_at',
    ])
    return JsonResponse({'ok': True, 'persisted': True})


def newsletter_unsubscribe(request, token):
    """
    Public, idempotent unsubscribe link. Looks up the profile by token,
    flips `newsletter_subscribed` to False, records the timestamp and
    rotates the token (so the same URL can't be replayed).
    """
    from django.utils import timezone as _tz
    import secrets
    profile = UserProfile.objects.filter(newsletter_token=token).first()
    if not profile:
        return render(request, 'newsletter_unsubscribe.html', {'unknown': True})
    if profile.newsletter_subscribed:
        profile.newsletter_subscribed = False
        profile.newsletter_unsubscribed_at = _tz.now()
        profile.newsletter_token = secrets.token_urlsafe(32)
        profile.save(update_fields=[
            'newsletter_subscribed', 'newsletter_unsubscribed_at', 'newsletter_token',
        ])
    return render(request, 'newsletter_unsubscribe.html', {
        'unknown': False,
        'profile': profile,
    })


@login_required
def delete_account(request):
    """
    Vista para eliminar la cuenta de usuario.
    
    Antes de eliminar la cuenta, establece como NULL el campo assignedUser en todos los
    registros GeoAttempt asociados con el usuario, para mantener los registros de
    georreferenciación intactos pero sin asociación a un usuario específico.
    
    Args:
        request: El objeto de solicitud HTTP
        
    Returns:
        HttpResponse: Redirección a la página principal
    """
    if request.method == "POST":
        user = request.user
        
        # Importar el modelo GeoAttempt
        from georeferencing.models import GeoAttempt
        
        # Establecer como NULL el campo assignedUser en todos los registros asociados
        # en lugar de eliminarlos o transferirlos a otro usuario
        GeoAttempt.objects.filter(assignedUser=user).update(assignedUser=None)
        
        # Desconectar al usuario
        logout(request)
        
        # Eliminar el usuario y toda su información relacionada
        user.delete()
        messages.success(request, _("Your account has been permanently deleted."))
        return redirect('index')

    return render(request, 'delete_account.html')


# ── Diplomas ─────────────────────────────────────────────────────────────
def _static_file_uri(static_path):
    """Absolute file:// URI for a static asset, so WeasyPrint reads it from
    disk instead of doing an HTTP round-trip back to this same server."""
    from django.contrib.staticfiles import finders
    import os
    abs_path = finders.find(static_path)
    if not abs_path:
        from django.conf import settings
        candidate = os.path.join(settings.STATIC_ROOT or '', static_path)
        abs_path = candidate if os.path.exists(candidate) else None
    return 'file://' + abs_path if abs_path else ''


def _qr_svg(url):
    """Inline SVG QR (dark modules on white) pointing at the verify URL."""
    import io, segno
    qr = segno.make(url, error='m')
    buff = io.BytesIO()
    qr.save(buff, kind='svg', scale=4, border=0, dark='#241a47', light='#ffffff')
    return buff.getvalue().decode('utf-8')


def _compact_duration(total_seconds):
    """Short duration for the diploma stat box, e.g. '2d 3h', '5h 12m', '8m'."""
    total_seconds = int(total_seconds or 0)
    days, rem = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    parts = []
    if days:
        parts.append(f'{days}d')
    if hours:
        parts.append(f'{hours}h')
    if minutes and not days:
        parts.append(f'{minutes}m')
    return ' '.join(parts) or '0m'


def _diploma_assets(request, ctx):
    """Augment a diploma context with the rendered QR and branding asset URIs."""
    from django.utils.safestring import mark_safe
    from django.conf import settings
    ctx = dict(ctx)
    ctx['qr_svg'] = mark_safe(_qr_svg(ctx['verify_url']))
    ctx['logo_uri'] = _static_file_uri('img/logo-lost.png')
    ctx['ibercivis_logo_uri'] = _static_file_uri('img/ibercivis-logo.svg')
    ctx['iss_uri'] = _static_file_uri('img/iss.svg')
    ctx['flag_uri'] = _static_file_uri('img/Flag_of_Europe.svg')
    # The diploma @font-face rules reference {{ STATIC_URL }}fonts/…; the static
    # context processor isn't enabled, so pass it explicitly. Resolved off disk
    # by _diploma_url_fetcher (no HTTP round-trip).
    ctx['STATIC_URL'] = settings.STATIC_URL
    from django.utils.translation import get_language
    ctx['LANGUAGE_CODE'] = get_language() or settings.LANGUAGE_CODE
    if 'time_spent' in ctx:
        ctx['time_pretty'] = _compact_duration(ctx['time_spent'])
    return ctx


def _diploma_url_fetcher(url):
    """Resolve {{ STATIC_URL }}… references from disk so WeasyPrint loads the
    IBM Plex fonts (and any static asset) without an HTTP round-trip back to
    this server. Anything else falls through to WeasyPrint's default fetcher."""
    from django.conf import settings
    from django.contrib.staticfiles import finders
    from urllib.parse import urlparse, unquote
    from weasyprint import default_url_fetcher
    import os
    static_url = settings.STATIC_URL or '/static/'
    path = urlparse(url).path
    if path.startswith(static_url):
        rel = unquote(path[len(static_url):])
        abs_path = finders.find(rel)
        if not abs_path and settings.STATIC_ROOT:
            cand = os.path.join(settings.STATIC_ROOT, rel)
            abs_path = cand if os.path.exists(cand) else None
        if abs_path:
            return default_url_fetcher('file://' + abs_path)
    return default_url_fetcher(url)


def _render_diploma_pdf(request, template, ctx, filename, inline=False):
    from django.template.loader import render_to_string
    from weasyprint import HTML
    from weasyprint.text.fonts import FontConfiguration
    font_config = FontConfiguration()
    html = render_to_string(template, ctx, request=request)
    pdf = HTML(
        string=html,
        base_url=request.build_absolute_uri('/'),
        url_fetcher=_diploma_url_fetcher,
    ).write_pdf(font_config=font_config)
    resp = HttpResponse(pdf, content_type='application/pdf')
    disposition = 'inline' if inline else 'attachment'
    resp['Content-Disposition'] = f'{disposition}; filename="{filename}"'
    return resp


@login_required
def diploma_general(request):
    """Render the user's all-time diploma as a PDF (download, or ?inline=1)."""
    from georeferencing import diplomas
    from django.utils.text import slugify
    profile, _c = UserProfile.objects.get_or_create(user=request.user)
    inline = request.GET.get('inline') == '1'
    ctx = _diploma_assets(request, diplomas.general_context(request.user, profile, request))
    filename = f'lostatnight-diploma-{slugify(request.user.username) or "user"}.pdf'
    resp = _render_diploma_pdf(request, 'diploma_general.html', ctx, filename, inline=inline)
    DiplomaDownload.objects.create(user=request.user, kind='general', inline=inline)
    return resp


@login_required
def diploma_challenge(request, challenge_id):
    """Render the user's diploma for one challenge (download, or ?inline=1)."""
    from georeferencing import diplomas
    from django.utils.text import slugify
    participant = (ChallengeParticipant.objects
                   .filter(challenge_id=challenge_id, user=request.user)
                   .select_related('challenge', 'user')
                   .first())
    if not participant:
        messages.info(
            request,
            _("You haven't taken part in this challenge, so there's no diploma "
              "to download for it. Here are the badges you've earned so far."),
        )
        return redirect('/user-profile/')
    inline = request.GET.get('inline') == '1'
    ctx = _diploma_assets(request, diplomas.challenge_context(participant, request))
    slug = slugify(participant.challenge.name) or str(challenge_id)
    filename = f'lostatnight-challenge-{slug}.pdf'
    resp = _render_diploma_pdf(request, 'diploma_challenge.html', ctx, filename, inline=inline)
    DiplomaDownload.objects.create(
        user=request.user, kind='challenge',
        challenge=participant.challenge, inline=inline,
    )
    return resp


def diploma_verify(request, code):
    """Public page confirming a diploma is genuine (QR target)."""
    from georeferencing import diplomas
    if not code:
        raise Http404
    participant = (ChallengeParticipant.objects
                   .filter(verify_code=code)
                   .select_related('challenge', 'user')
                   .first())
    if participant:
        ctx = diplomas.challenge_context(participant, request)
        return render(request, 'diploma_verify.html', {'ok': True, 'ctx': ctx})
    profile = (UserProfile.objects
               .filter(diploma_code=code)
               .select_related('user')
               .first())
    if profile:
        ctx = diplomas.general_context(profile.user, profile, request)
        ctx['time_pretty'] = convert_time_spent(ctx['time_spent'])
        return render(request, 'diploma_verify.html', {'ok': True, 'ctx': ctx})
    return render(request, 'diploma_verify.html', {'ok': False}, status=404)
