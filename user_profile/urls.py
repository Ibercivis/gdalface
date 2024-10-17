from django.urls import path
from .views import UserView

urlpatterns = [
    path('', UserView, name='user'),
]