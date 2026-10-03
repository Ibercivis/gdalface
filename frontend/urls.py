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
    # Map of located photos
    path('map/data.geojson', views.located_map_data, name='located_map_data'),
    # Public ranking (people / teams / countries)
    path('ranking/', views.ranking, name='ranking'),
    path('ranking/<str:scope>/', views.ranking, name='ranking_scope'),
    # Staff-only control panel
    path('stats/', views.staff_stats, name='staff_stats'),
    path('stats/export.csv', views.staff_stats_csv, name='staff_stats_csv'),
    path('stats/series.json', views.staff_stats_series, name='staff_stats_series'),
    # Legal / GDPR pages
    path('privacy/', views.privacy_policy, name='privacy_policy'),
    path('terms/', views.terms_of_use, name='terms_of_use'),
    path('cookies/', views.cookies_policy, name='cookies_policy'),
    path('legal/', views.legal_notice, name='legal_notice'),
]
