"""
This module contains view functions for rendering templates in the
frontend app.
"""

from django.shortcuts import render, redirect
from georeferencing.models import Batch, GeoAttempt, Image
from django.core.mail import send_mail
from django.contrib import messages
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Count, Sum, Avg, F, ExpressionWrapper, fields, Q
from django.utils import timezone

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
    # Total users
    total_users = User.objects.count()
    
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
            messages.success(request, "¡Tu mensaje ha sido enviado correctamente!")
            return redirect('/')  # Redirect to home page after successful submission
        except Exception as e:
            messages.error(request, f"No se pudo enviar el mensaje: {str(e)}")
    
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
        'total_control_points': total_control_points
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
    if pk is not None:
        batch = Batch.objects.get(pk=pk)
        context = {
            'batch': batch
        }
        return render(request, 'gettask.html', context)
    return render(request, 'gettask.html')

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
