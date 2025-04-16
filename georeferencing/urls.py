from django.urls import path
from .views import (
    ImageView,
    ImageIndividualView,
    GeoAttemptView,
    GeoAttemptIndividualView,
    PendingGeoAttemptView,
    GeoAttemptsCalendarView,)
urlpatterns = [
    # Define your app's URL patterns here
    path('geoattempt/', GeoAttemptView.as_view(), name='geoattempt'),
    path('geoattempt-individual/<int:pk>/', GeoAttemptIndividualView.as_view(), name='geoattempt-individual'),
    path('geoattempt-pending/', PendingGeoAttemptView.as_view(), name='geoattempt-pending'),
    path('geoattempt-pending/<int:pk>/', PendingGeoAttemptView.as_view(), name='geoattempt-pending-batch'),
    path('image/', ImageView.as_view(), name='images'),
    path('image-individual/<int:pk>/', ImageIndividualView.as_view(), name='images-individual'),
    path('geoattempts-calendar/', GeoAttemptsCalendarView.as_view(), name='calendar-geoattempt'),
]