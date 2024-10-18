"""
URL configuration for the frontend application.

This module defines the URL patterns for the frontend application, mapping
URLs to their corresponding view functions.
"""
from django.urls import path

from . import views

urlpatterns = [
    # index path
    path('', views.index, name='index'),
    path('gettask', views.gettask, name='gettask'),
]
