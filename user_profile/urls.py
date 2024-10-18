"""
URL configuration for the user_profile app.

This module defines the URL patterns for the user_profile app,
mapping the root URL to the UserView.

Routes:
    - '' : Maps to UserView and is named 'user'.

Imports:
    - path: Function to define URL patterns.
    - UserView: View to handle the user profile.

Usage:
    Include this URL configuration in the project's main urls.py 
    to route requests to the user_profile app.
"""
from django.urls import path
from .views import user_view

urlpatterns = [
    path('', user_view, name='user'),
]
