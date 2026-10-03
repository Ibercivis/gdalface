"""URL patterns for the teams app (mounted at /teams/)."""
from django.urls import path

from .views import create_team, join_team, leave_team, team_detail

urlpatterns = [
    path('create/', create_team, name='team_create'),
    path('join/', join_team, name='team_join'),
    path('leave/', leave_team, name='team_leave'),
    path('<slug:slug>/', team_detail, name='team_detail'),
]
