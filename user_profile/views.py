"""
This module contains the views for the user_profile app
"""
from django.shortcuts import render

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
        time = user.userprofile.time_spent
        geo = user.userprofile.geoattempts_done
        cp = user.userprofile.controlPointsDone
        che = user.userprofile.cheating
        context = {
            'user': user,
            'time': time,
            'geo': geo,
            'cp': cp,
            'che': che,
        }
        return render(request, 'user.html', context)
    return render(request, 'user.html')
