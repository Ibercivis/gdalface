"""URL patterns for the teams app (mounted at /teams/)."""
from django.urls import path

from . import views

urlpatterns = [
    path('', views.team_list, name='team_list'),
    path('create/', views.create_team, name='team_create'),
    path('join/', views.join_team, name='team_join'),
    path('leave/', views.leave_team, name='team_leave'),
    path('<slug:slug>/', views.team_detail, name='team_detail'),
    path('<slug:slug>/edit/', views.team_edit, name='team_edit'),
    path('<slug:slug>/rotate-code/', views.team_rotate_code, name='team_rotate_code'),
    path('<slug:slug>/remove-member/', views.team_remove_member, name='team_remove_member'),
    path('<slug:slug>/transfer/', views.team_transfer, name='team_transfer'),
    path('<slug:slug>/delete/', views.team_delete, name='team_delete'),
]
