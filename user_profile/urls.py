"""
URL configuration for the user_profile app.

This module defines the URL patterns for the user_profile app,
mapping the root URL to the UserView.

Routes:
    - '' : Maps to UserView and is named 'user'.
    - 'edit/' : Maps to edit_profile view and is named 'edit_profile'.
    - 'delete/' : Maps to delete_account view and is named 'delete_account'.

Imports:
    - path: Function to define URL patterns.
    - UserView: View to handle the user profile.
    - edit_profile: View to handle the user profile editing.
    - delete_account: View to handle the user account deletion.

Usage:
    Include this URL configuration in the project's main urls.py 
    to route requests to the user_profile app.
"""
from django.urls import path
from .views import user_view, edit_profile, delete_account

urlpatterns = [
    path('', user_view, name='user'),
    path('edit/', edit_profile, name='edit_profile'),
    path('delete/', delete_account, name='delete_account'),
]
