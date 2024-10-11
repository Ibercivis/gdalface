from django.urls import path
from .views import (
    ImageView,
    ImageIndividualView,
    GeoAttemptView,
    GeoAttemptIndividualView,
    PendingGeoAttemptView)
urlpatterns = [
    # Define your app's URL patterns here
    path('geoattempt/', GeoAttemptView.as_view(), name='geoattempt'),
    path('geoattempt-individual/<int:pk>/', GeoAttemptIndividualView.as_view(), name='geoattempt-individual'),
    path('geoattempt-pending/', PendingGeoAttemptView.as_view(), name='geoattempt-pending'),
    path('image/', ImageView.as_view(), name='images'),
    path('image-individual/<int:pk>/', ImageIndividualView.as_view(), name='images-individual'),
]