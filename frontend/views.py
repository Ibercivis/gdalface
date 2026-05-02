"""
This module contains view functions for rendering templates in the
frontend app.
"""

from django.shortcuts import render, redirect
from georeferencing.models import Batch, GeoAttempt, Image, Challenge, ChallengeParticipant
from django.core.mail import send_mail
from django.contrib import messages
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Count, Sum, Avg, F, ExpressionWrapper, fields, Q
from django.utils import timezone
from django.utils.translation import gettext as _

# Create your views here.

def index(request):
    """
    Renders the index.html template.
    
    If the request method is POST, it processes the contact form data
    and sends an email to the site administrators.

    Args:
        request: The HTTP request object.

    Returns:
        HttpResponse: The rendered index.html template.
    """
    # Get the user
    user = request.user
    # Get all batches to display them on the homepage
    batchs = Batch.objects.all()
    
    # Calculating project statistics
    # Total users — only those who confirmed their email (allauth verified).
    from allauth.account.models import EmailAddress
    total_users = EmailAddress.objects.filter(verified=True).values('user_id').distinct().count()
    
    # Total tasks and completed tasks
    total_tasks = GeoAttempt.objects.count()
    completed_tasks = GeoAttempt.objects.filter(status='DONE').count()
    
    # Total images and images with completed georeferencing
    total_images = Image.objects.count()
    images_with_georeference = Image.objects.filter(
        id__in=GeoAttempt.objects.filter(status='DONE').values('image')
    ).distinct().count()
    
    # Total control points
    total_control_points = 0
    try:
        # Obtenemos los geoattempts completados que tienen puntos de control
        completed_attempts = GeoAttempt.objects.filter(
            status='DONE',
            controlPoints__isnull=False
        )
        
        # Sumamos la cantidad de puntos de control en cada intento
        for attempt in completed_attempts:
            # controlPoints es un JSONField que puede contener una lista de puntos
            if attempt.controlPoints and isinstance(attempt.controlPoints, list):
                total_control_points += len(attempt.controlPoints)
    except Exception as e:
        # Log the error but continue with total_control_points = 0
        print(f"Error calculating total control points: {str(e)}")
    
    # Total minutes spent on tasks
    total_minutes = 0
    try:
        # Calculate total time using the correct fields (finishedDateTime - assignedDateTime)
        finished_attempts = GeoAttempt.objects.filter(
            status='DONE',
            finishedDateTime__isnull=False,
            assignedDateTime__isnull=False
        )
        
        # Create a duration expression
        duration_expr = ExpressionWrapper(
            F('finishedDateTime') - F('assignedDateTime'),
            output_field=fields.DurationField()
        )
        
        # Calculate total duration in seconds
        result = finished_attempts.annotate(
            duration=duration_expr
        ).aggregate(
            total_seconds=Sum('duration')
        )
        
        if result['total_seconds']:
            # Convert to minutes
            total_minutes = int(result['total_seconds'].total_seconds() / 60)
        
    except Exception as e:
        # Log the error but continue with total_minutes = 0
        print(f"Error calculating total minutes: {str(e)}")
    
    # Average tasks per user
    avg_tasks_per_user = 0
    if total_users > 0:
        avg_tasks_per_user = round(completed_tasks / total_users, 1)
    
    # Check if this is a POST request (contact form submission)
    if request.method == 'POST':
        # Get form data
        name = request.POST.get('name')
        email = request.POST.get('email')
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        
        # Construct email message
        email_subject = f"Formulario de contacto: {subject}"
        email_message = f"""
        Nuevo mensaje del formulario de contacto:
        
        Nombre: {name}
        Email: {email}
        Asunto: {subject}
        
        Mensaje:
        {message}
        """
        
        # Send email
        try:
            send_mail(
                email_subject,
                email_message,
                settings.DEFAULT_FROM_EMAIL,  # From email (configured in settings)
                settings.DEFAULT_TO_EMAIL,    # To email - Ahora usando la tupla de settings
                fail_silently=False,
            )
            messages.success(request, _("Your message has been sent successfully!"))
            return redirect('/')  # Redirect to home page after successful submission
        except Exception as e:
            messages.error(request, _("Could not send the message: %(error)s") % {'error': str(e)})
    
    # Human-readable total time. The raw value is in minutes; convert to a
    # compact "Xd Yh" / "Yh Zm" / "Zm" string for display.
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

    # Completion percentage (project-level), used as a headline metric.
    completion_pct = round(
        (completed_tasks / total_tasks) * 100, 1,
    ) if total_tasks else 0

    # Visible challenges on the home page: anything not yet finished, plus
    # finished ones that ended in the last 30 days for transparency.
    now = timezone.now()
    visible_challenges = list(
        Challenge.objects.filter(end_at__gte=now - timezone.timedelta(days=30))
        .select_related('batch')
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
        'batchs': batchs,
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
        context['batch'] = Batch.objects.get(pk=pk)
    return render(request, 'gettask.html', context)

def batchs(request):
    """
    Handle the HTTP request to render the 'batchs.html' template.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        HttpResponse: The rendered 'batchs.html' template.
    """
    batchs = Batch.objects.all()
    context = {
        'batchs': batchs
    }
    return render(request, 'batchs.html', context)

def contact(request):
    """
    Handle the HTTP request to render the 'contact.html' template.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        HttpResponse: The rendered 'contact.html' template.
    """
    return render(request, 'contact.html')


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
        'participants_count': len(participants),
        'my_enrollment': my_enrollment,
        'my_rank': my_rank,
        'total_cp': total_cp,
        'progress_pct': progress_pct,
        'next_milestone': next_milestone,
        'days_left': days_left,
        'time_state': time_state,
    })
