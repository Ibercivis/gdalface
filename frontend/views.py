"""
This module contains view functions for rendering templates in the
frontend app.
"""

import logging
import re
import time

from django.core import signing
from django.core.cache import cache
from django.core.mail import EmailMessage
from django.shortcuts import render, redirect
from georeferencing.models import Batch, GeoAttempt, Image, Challenge, ChallengeParticipant
from django.http import HttpResponseNotAllowed
from django.contrib import messages
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Count, Sum, Avg, F, ExpressionWrapper, fields, Q
from django.utils import timezone
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)


def index(request):
    """
    Renders the index.html template.

    The contact form used to live on this page and this view used to email
    its POSTs. The form moved to /contact but spam bots kept posting here
    (hundreds/day, all with valid CSRF), so POST is now rejected outright.

    Args:
        request: The HTTP request object.

    Returns:
        HttpResponse: The rendered index.html template.
    """
    if request.method != 'GET':
        return HttpResponseNotAllowed(['GET'])
    # Get the user
    user = request.user
    # Project statistics — single definitions live in georeferencing.metrics.
    from georeferencing import metrics
    totals = metrics.project_totals()
    total_users = totals['participants']
    total_tasks = totals['tasks_total']
    completed_tasks = totals['tasks_done']
    total_images = totals['images_total']
    images_with_georeference = totals['images_georeferenced']
    total_control_points = totals['control_points']
    total_minutes = totals['seconds'] // 60
    avg_tasks_per_user = totals['avg_tasks_per_participant']
    completion_pct = totals['completion_pct']

    # Human-readable total time: compact "Xd Yh" / "Yh Zm" / "Zm".
    def _format_minutes(mins):
        if not mins:
            return '0m'
        days, rem = divmod(int(mins), 1440)
        hours, m = divmod(rem, 60)
        parts = []
        if days:  parts.append(f'{days}d')
        if hours: parts.append(f'{hours}h')
        if m and not days: parts.append(f'{m}m')
        return ' '.join(parts) or '<1m'
    total_time_formatted = _format_minutes(total_minutes)
    weekly = metrics.weekly_contributions(12)

    # Visible challenges on the home page: anything not yet finished, plus
    # finished ones that ended in the last 30 days for transparency.
    # Annotate participants_count + total_cp once per challenge so the
    # card template doesn't run an aggregate per row (was N+1).
    now = timezone.now()
    visible_challenges = list(
        Challenge.objects.filter(end_at__gte=now - timezone.timedelta(days=30))
        .select_related('batch')
        .annotate(
            participants_count=Count('participants', distinct=True,
                                     filter=Q(participants__left_at__isnull=True)),
            total_cp_annot=Sum('participants__cached_cp_count'),
        )
        .order_by('-start_at')
    )
    enrolled_challenge_id = None
    if user.is_authenticated:
        active_enrollment = ChallengeParticipant.objects.filter(
            user=user, left_at__isnull=True,
        ).first()
        if active_enrollment:
            enrolled_challenge_id = active_enrollment.challenge_id

    # Prepare context
    context = {
        'user': user,
        # Adding statistics to the context
        'total_users': total_users,
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'total_minutes': total_minutes,
        'avg_tasks_per_user': avg_tasks_per_user,
        'total_images': total_images,
        'images_with_georeference': images_with_georeference,
        'total_control_points': total_control_points,
        'total_time_formatted': total_time_formatted,
        'completion_pct': completion_pct,
        'visible_challenges': visible_challenges,
        'open_challenges': sum(1 for ch in visible_challenges if ch.status in ('active', 'upcoming', 'paused')),
        'weekly': weekly,
        'weekly_max': max([w['n'] for w in weekly] + [1]),
        'enrolled_challenge_id': enrolled_challenge_id,
    }
    return render(request, 'index.html', context)

def gettask(request, pk=None):
    """
    Handle the HTTP request to render the 'gettask.html' template.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        HttpResponse: The rendered 'gettask.html' template.
    """
    # Server-side hint for the tutorial: anonymous users always qualify;
    # authenticated users qualify only if they have not completed any task yet.
    if request.user.is_authenticated:
        try:
            show_tutorial = request.user.userprofile.geoattempts_done == 0
        except Exception:
            show_tutorial = True
    else:
        show_tutorial = True

    context = {'show_tutorial': show_tutorial}
    if pk is not None:
        from django.shortcuts import get_object_or_404
        context['batch'] = get_object_or_404(Batch, pk=pk)
    return render(request, 'gettask.html', context)

# ── Contact form ──────────────────────────────────────────────────────

_URL_RE = re.compile(r'(https?://|www\.)', re.I)
_CONTACT_SALT = 'frontend.contact'
_CONTACT_JS_SALT = 'frontend.contact.js'
_CONTACT_TOKEN_MAX_AGE = 6 * 3600  # form left open longer than this → reload


def _client_ip(request):
    """Real client IP. nginx sets X-Forwarded-For; gunicorn on a unix socket
    sees no REMOTE_ADDR, so fall back through the headers in order."""
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('HTTP_X_REAL_IP') or request.META.get('REMOTE_ADDR') or '0.0.0.0'


def _contact_tokens():
    """Signed timestamp pair rendered into the form.

    ``started_at`` goes in a hidden input; ``js_key`` goes in a data attribute
    that a tiny inline script copies into the ``form_token`` input. Bots that
    scrape+POST without executing JS never populate ``form_token``.
    """
    now = time.time()
    return {
        'started_at_value': signing.dumps(now, salt=_CONTACT_SALT),
        'js_key': signing.dumps(now, salt=_CONTACT_JS_SALT),
    }


def _contact_ctx(**extra):
    ctx = _contact_tokens()
    ctx['turnstile_site_key'] = settings.TURNSTILE_SITE_KEY
    ctx.update(extra)
    return ctx


def _verify_turnstile(token, ip):
    """Server-side check of a Cloudflare Turnstile response token."""
    if not token:
        return False
    try:
        import requests
        r = requests.post(
            'https://challenges.cloudflare.com/turnstile/v0/siteverify',
            data={'secret': settings.TURNSTILE_SECRET_KEY,
                  'response': token, 'remoteip': ip},
            timeout=5,
        )
        return bool(r.json().get('success'))
    except Exception as exc:  # network / JSON errors → treat as failed
        logger.warning('turnstile verify error: %s', exc)
        return False


def _contact_rate_limited(ip):
    """True if ``ip`` has exceeded CONTACT_RATE_LIMIT submissions this hour.
    Fails open if the cache is unreachable — a broken Redis must not take
    the contact form down."""
    key = f'contact:rl:{ip}'
    try:
        if cache.add(key, 1, timeout=3600):
            return False
        return cache.incr(key) > settings.CONTACT_RATE_LIMIT
    except Exception as exc:
        logger.warning('contact rate-limit cache error: %s', exc)
        return False


def _contact_spam_reason(request, fields):
    """Return a short reason string if the submission looks automated, else
    None. Every check here fails *silently* (fake "thanks" page) so bots get
    no feedback about which heuristic caught them."""
    post = request.POST

    if (post.get('website') or '').strip():
        return 'honeypot'

    # Signed timestamp: must exist, be ours, be ≥ CONTACT_MIN_SECONDS old
    # and not stale. Unsigned / forged / replayed-old values all fail.
    try:
        started = signing.loads(post.get('started_at', ''), salt=_CONTACT_SALT,
                                max_age=_CONTACT_TOKEN_MAX_AGE)
    except (signing.BadSignature, signing.SignatureExpired):
        return 'bad-timestamp'
    age = time.time() - float(started)
    if age < settings.CONTACT_MIN_SECONDS:
        return 'too-fast'
    if age > _CONTACT_TOKEN_MAX_AGE:  # value check too, not just signature age
        return 'stale'

    # JS token: copied from data-k by inline JS; must match the same issue.
    try:
        js_started = signing.loads(post.get('form_token', ''), salt=_CONTACT_JS_SALT,
                                   max_age=_CONTACT_TOKEN_MAX_AGE)
    except (signing.BadSignature, signing.SignatureExpired):
        return 'bad-js-token'
    if abs(float(js_started) - float(started)) > 1:
        return 'token-mismatch'

    text = ' '.join(fields.values())
    if len(_URL_RE.findall(text)) >= settings.CONTACT_MAX_URLS:
        return 'too-many-urls'
    if _URL_RE.search(fields['name']) or _URL_RE.search(fields['subject']):
        return 'url-in-name-or-subject'

    if _contact_rate_limited(_client_ip(request)):
        return 'rate-limited'

    return None


def contact(request):
    """
    Render the contact form (GET) or process a submission (POST).

    Anti-spam layers (see ``_contact_spam_reason``):
      1. Honeypot field ``website`` must stay empty.
      2. Signed ``started_at`` timestamp: ≥ CONTACT_MIN_SECONDS old, < 6h.
      3. ``form_token`` filled in by inline JavaScript (bots don't run JS).
      4. URL-count heuristic on the text.
      5. Per-IP rate limit (shared Redis cache).
      6. Optional Cloudflare Turnstile when TURNSTILE_* keys are configured.
    1-5 fail silently with a fake success message; 6 shows an error so a
    human can retry. Missing ``form_token`` with everything else fine gets
    an explicit "enable JavaScript" hint.
    """
    if request.method != 'POST':
        return render(request, 'contact.html', _contact_ctx())

    fields = {
        'name': (request.POST.get('name') or '').strip()[:120],
        'email': (request.POST.get('email') or '').strip()[:200],
        'subject': (request.POST.get('subject') or '').strip()[:200],
        'message': (request.POST.get('message') or '').strip()[:5000],
    }
    ip = _client_ip(request)

    # A real browser with JS disabled: everything present except form_token.
    if not request.POST.get('form_token') and not (request.POST.get('website') or '').strip():
        messages.error(request, _('Please enable JavaScript to send the form.'))
        return render(request, 'contact.html', _contact_ctx(form_data=fields))

    reason = _contact_spam_reason(request, fields)
    if reason:
        logger.info('contact spam dropped: reason=%s ip=%s email=%r', reason, ip, fields['email'])
        messages.success(request, _("Your message has been sent. We'll be in touch soon."))
        return redirect(request.path)

    if settings.TURNSTILE_SECRET_KEY:
        if not _verify_turnstile(request.POST.get('cf-turnstile-response'), ip):
            logger.info('contact turnstile failed: ip=%s', ip)
            messages.error(request, _('Captcha verification failed. Please try again.'))
            return render(request, 'contact.html', _contact_ctx(form_data=fields))

    if not all(fields.values()):
        messages.error(request, _('Please fill all required fields.'))
        return render(request, 'contact.html', _contact_ctx(form_data=fields))

    try:
        mail = EmailMessage(
            subject=f"[Lost at Night] {fields['subject']}",
            body=f"From: {fields['name']} <{fields['email']}>\nIP: {ip}\n\n{fields['message']}",
            from_email=settings.DEFAULT_FROM_EMAIL or fields['email'],
            to=list(settings.DEFAULT_TO_EMAIL),
            reply_to=[fields['email']],
        )
        mail.send(fail_silently=False)
    except Exception as exc:
        logger.exception('contact mail send failed')
        messages.error(request, _('Could not send the message: %(error)s') % {'error': str(exc)})
        return render(request, 'contact.html', _contact_ctx(form_data=fields))

    logger.info('contact mail sent: ip=%s email=%r', ip, fields['email'])
    messages.success(request, _('Your message has been sent successfully!'))
    return redirect(request.path)


def challenge_detail(request, pk):
    """Public detail page with progress + leaderboard."""
    from django.shortcuts import get_object_or_404
    ch = get_object_or_404(Challenge.objects.select_related('batch'), pk=pk)
    participants = list(
        ch.participants.select_related('user', 'user__userprofile')
        .order_by('-cached_cp_count', 'joined_at')
    )
    my_enrollment = None
    my_rank = None
    my_gap = None
    if request.user.is_authenticated:
        my_enrollment = next(
            (p for p in participants if p.user_id == request.user.id), None,
        )
        if my_enrollment:
            my_rank = next(
                (i + 1 for i, p in enumerate(participants)
                 if p.user_id == request.user.id),
                None,
            )
            # Closest participant with strictly more CP — the one to overtake.
            if my_rank and my_rank > 1:
                ahead = min(
                    (p for p in participants
                     if p.cached_cp_count > my_enrollment.cached_cp_count),
                    key=lambda p: p.cached_cp_count,
                    default=None,
                )
                if ahead:
                    try:
                        ahead_visible = bool(ahead.user.userprofile.visible)
                    except Exception:
                        ahead_visible = True
                    my_gap = {
                        'cp_needed': ahead.cached_cp_count - my_enrollment.cached_cp_count + 1,
                        'username': ahead.user.username if ahead_visible else None,
                    }

    total_cp = ch.total_cp()
    progress_pct = round(
        min(100, (total_cp / ch.target_gold) * 100), 1,
    ) if ch.target_gold else 0

    # Next milestone (the closest target ahead of current total).
    next_milestone = None
    for tier_label, tier_value, tier_emoji in (
        ('bronze', ch.target_bronze, '🥉'),
        ('silver', ch.target_silver, '🥈'),
        ('gold',   ch.target_gold,   '🥇'),
    ):
        if total_cp < tier_value:
            next_milestone = {
                'label': tier_label, 'value': tier_value,
                'emoji': tier_emoji, 'remaining': tier_value - total_cp,
            }
            break

    # Time remaining: days until end_at (or "ended").
    now = timezone.now()
    if now >= ch.end_at:
        days_left = 0
        time_state = 'ended'
    elif now < ch.start_at:
        days_left = (ch.start_at - now).days
        time_state = 'upcoming'
    else:
        days_left = (ch.end_at - now).days
        time_state = 'running'

    return render(request, 'challenge_detail.html', {
        'challenge': ch,
        'participants': participants,
        'participants_count': sum(1 for p in participants if p.left_at is None),
        'my_enrollment': my_enrollment,
        'my_rank': my_rank,
        'my_gap': my_gap,
        'total_cp': total_cp,
        'progress_pct': progress_pct,
        'next_milestone': next_milestone,
        'days_left': days_left,
        'time_state': time_state,
    })


# ── Manual ────────────────────────────────────────────────────────────
def manual(request):
    return render(request, 'manual.html')


# ── Legal / GDPR pages ────────────────────────────────────────────────
def privacy_policy(request):
    from django.conf import settings as _s
    return render(request, 'legal/privacy.html', {
        'policy_version': getattr(_s, 'PRIVACY_POLICY_VERSION', ''),
    })


def terms_of_use(request):
    return render(request, 'legal/terms.html')


def cookies_policy(request):
    return render(request, 'legal/cookies.html')


def legal_notice(request):
    return render(request, 'legal/legal.html')


def project_stats(request):
    """Public, uniform stats contract for external dashboards.

    Serves the daily snapshot (georeferencing.stats), falling back to a live
    compute if the scheduler hasn't written the file yet. CORS-open and
    cacheable so any dashboard can pull it directly.
    """
    from django.http import JsonResponse
    from georeferencing.stats import read_snapshot, build_stats

    data = read_snapshot() or build_stats()
    response = JsonResponse(data, json_dumps_params={'ensure_ascii': False})
    response['Access-Control-Allow-Origin'] = '*'
    response['Cache-Control'] = 'public, max-age=3600'
    return response


# ── Staff statistics dashboard ────────────────────────────────────────
def _staff_only(view):
    from django.contrib.admin.views.decorators import staff_member_required
    return staff_member_required(view, login_url='/accounts/login')


@_staff_only
def staff_stats(request):
    """Internal control panel: people, contributions, queue, challenges,
    health, onboarding, plus dated events staff can pin on the charts."""
    import json
    from django.http import HttpResponseBadRequest
    from georeferencing.models import StatsEvent
    from georeferencing.stats import cached_staff_stats, STAFF_STATS_CACHE_KEY

    if request.method == 'POST':
        action = request.POST.get('action', 'add')
        if action == 'delete':
            StatsEvent.objects.filter(pk=request.POST.get('id')).delete()
            messages.success(request, 'Event deleted.')
        else:
            title = (request.POST.get('title') or '').strip()
            if not title:
                return HttpResponseBadRequest('title is required')
            happened = request.POST.get('happened_at') or ''
            try:
                from datetime import datetime, time as _time
                day = datetime.strptime(happened, '%Y-%m-%d').date()
                happened_at = timezone.make_aware(datetime.combine(day, _time(12, 0)))
            except ValueError:
                happened_at = timezone.now()
            kind = request.POST.get('kind') or 'other'
            if kind not in dict(StatsEvent.KIND_CHOICES):
                kind = 'other'
            StatsEvent.objects.create(
                happened_at=happened_at, kind=kind, title=title[:140],
                note=(request.POST.get('note') or '').strip(),
                url=(request.POST.get('url') or '').strip()[:200],
                created_by=request.user,
            )
            messages.success(request, 'Event added.')
        cache.delete_many([f'{STAFF_STATS_CACHE_KEY}:{d}' for d in (7, 30, 365, 1460)])
        return redirect(request.path + (f'?range={request.GET["range"]}' if 'range' in request.GET else ''))

    from georeferencing.timeseries import RANGES, DEFAULT_RANGE
    rng = request.GET.get('range', DEFAULT_RANGE)
    if rng not in RANGES:
        rng = DEFAULT_RANGE
    days = RANGES[rng]['days']
    data = cached_staff_stats(days, refresh='refresh' in request.GET)
    return render(request, 'staff_stats.html', {
        'd': data,
        'range': rng,
        'range_options': [(k, v['label']) for k, v in RANGES.items()],
        'days': days,
        'kind_choices': StatsEvent.KIND_CHOICES,
        'today': timezone.now().date().isoformat(),
    })


@_staff_only
def staff_stats_series(request):
    """JSON time series for the control panel charts: ?range=7d|30d|1y|4y."""
    from django.http import JsonResponse
    from georeferencing.timeseries import RANGES, DEFAULT_RANGE, series
    rng = request.GET.get('range', DEFAULT_RANGE)
    if rng not in RANGES:
        rng = DEFAULT_RANGE
    key = f'staff_series:v1:{rng}'
    data = None if 'refresh' in request.GET else cache.get(key)
    if data is None:
        data = series(rng)
        cache.set(key, data, 300)
    return JsonResponse(data)


@_staff_only
def staff_stats_csv(request):
    """Daily series as CSV: date, contributions, registered, anonymous, sign-ups."""
    import csv
    from django.http import HttpResponse
    from georeferencing.stats import cached_staff_stats
    from georeferencing.timeseries import RANGES, DEFAULT_RANGE
    rng = request.GET.get('range', DEFAULT_RANGE)
    d = cached_staff_stats(RANGES.get(rng, RANGES[DEFAULT_RANGE])['days'])
    resp = HttpResponse(content_type='text/csv; charset=utf-8')
    resp['Content-Disposition'] = f'attachment; filename="lostatnight-daily-{d["start"]}-{d["end"]}.csv"'
    w = csv.writer(resp)
    w.writerow(['date', 'contributions', 'contributions_registered',
                'contributions_anonymous', 'signups'])
    c = d['contributions']
    signups = {r['date']: r['n'] for r in d['people']['signups_series']}
    for tot, reg, anon in zip(c['series'], c['series_registered'], c['series_anonymous']):
        w.writerow([tot['date'], tot['n'], reg['n'], anon['n'], signups.get(tot['date'], 0)])
    return resp


# ── Public ranking page ───────────────────────────────────────────────
RANKING_SCOPES = ('users', 'teams', 'countries')


def ranking(request, scope='users'):
    """Public leaderboard: people / teams / countries with a shared period
    selector. Data comes from the existing ranking APIs; the header totals
    from georeferencing.metrics. URL state: /ranking/<scope>/?period=&ordering=
    and ?focus=me to land on the viewer's own row."""
    from django.http import Http404
    from georeferencing import metrics
    if scope not in RANKING_SCOPES:
        raise Http404
    period = request.GET.get('period', 'all')
    if period not in ('all', 'month', 'week'):
        period = 'all'
    ordering = request.GET.get('ordering', 'cp')
    if ordering not in ('cp', 'tasks', 'time', 'cp_per_user'):
        ordering = 'cp'
    return render(request, 'ranking.html', {
        'scope': scope,
        'period': period,
        'ordering': ordering,
        'focus_me': request.GET.get('focus') == 'me',
        'totals': metrics.project_totals(),
        'active_30': metrics.active_users(30),
    })


# ── Located-photos map ────────────────────────────────────────────────
def located_map(request):
    """Public map of every photo the community has located."""
    from georeferencing.mapdata import located_geojson
    challenge = None
    if request.GET.get('challenge'):
        challenge = Challenge.objects.filter(pk=request.GET['challenge']).first()
    data = located_geojson(challenge)
    return render(request, 'map.html', {
        'meta': data['meta'],
        'challenge': challenge,
        'data_url': '/map/data.geojson' + (f'?challenge={challenge.id}' if challenge else ''),
    })


def located_map_data(request):
    """GeoJSON for the map component. ?challenge=<id> filters; ?mine=1 marks
    the viewer's own photos (requires login)."""
    from django.http import JsonResponse
    from georeferencing.mapdata import located_geojson
    challenge = None
    if request.GET.get('challenge'):
        challenge = Challenge.objects.filter(pk=request.GET['challenge']).first()
    user = request.user if request.GET.get('mine') == '1' else None
    data = located_geojson(challenge, user=user)
    resp = JsonResponse(data)
    if user is None:
        resp['Cache-Control'] = 'public, max-age=600'
    return resp
