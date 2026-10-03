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
    path('gettask/<int:pk>', views.gettask, name='gettask_batch'),
    path('contact', views.contact, name='contact'),
    path('manual/', views.manual, name='manual'),
    path('challenges/<int:pk>/', views.challenge_detail, name='challenge_detail'),
    # Staff-only control panel
    path('stats/', views.staff_stats, name='staff_stats'),
    path('stats/export.csv', views.staff_stats_csv, name='staff_stats_csv'),
    # Legal / GDPR pages
    path('privacy/', views.privacy_policy, name='privacy_policy'),
    path('terms/', views.terms_of_use, name='terms_of_use'),
    path('cookies/', views.cookies_policy, name='cookies_policy'),
    path('legal/', views.legal_notice, name='legal_notice'),
]
