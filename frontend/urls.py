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
    path('gettask/<int:pk>', views.gettask, name='getttask'),
    path('batchs', views.batchs, name='batchs'),
    path('contact', views.contact, name='contact')
]
