"""
This module contains view functions for rendering templates in the
frontend app.
"""

from django.shortcuts import render, redirect
from georeferencing.models import Batch
from django.core.mail import send_mail
from django.contrib import messages
from django.conf import settings

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
        'batchs': batchs
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
