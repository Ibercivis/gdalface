from django.urls import path
from . import views

urlpatterns = [
    # index path
    path('', views.index, name='index'),
    path('task/', views.task, name='task'),
    path('task2', views.task2, name='task2'),
    path('gettask', views.gettask, name='gettask'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('login/', views.login, name='login'),
    path('register/', views.register, name='register'),
    path('logout/', views.logout, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/', views.profile, name='profile'),
]