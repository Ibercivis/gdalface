"""
This module contains view functions for rendering templates in the
frontend app.
"""

from django.shortcuts import render

# Create your views here.

def index(request):
    """
    Renders the index.html template.

    Args:
        request: The HTTP request object.

    Returns:
        HttpResponse: The rendered index.html template.
    """
    return render(request, 'index.html')

def gettask(request):
    """
    Handle the HTTP request to render the 'gettask.html' template.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        HttpResponse: The rendered 'gettask.html' template.
    """
    return render(request, 'gettask.html')
