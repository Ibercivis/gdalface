from django.urls import path
from .views import (
    ImageView,
    ImageIndividualView,
    GeoAttemptView,
    GeoAttemptIndividualView,
    PendingGeoAttemptView,
    GeoAttemptsCalendarView,
    TutorialEventView,
    ChallengeListView,
    ChallengeDetailView,
    ChallengeJoinView,
    ChallengeLeaveView,
    ChallengeLeaderboardView,
    MyChallengeView,
)
from .export import ExportImageView, ExportImageListView

urlpatterns = [
    # Define your app's URL patterns here
    path('geoattempt/', GeoAttemptView.as_view(), name='geoattempt'),
    path('geoattempt-individual/<int:pk>/', GeoAttemptIndividualView.as_view(), name='geoattempt-individual'),
    path('geoattempt-pending/', PendingGeoAttemptView.as_view(), name='geoattempt-pending'),
    path('geoattempt-pending/<int:pk>/', PendingGeoAttemptView.as_view(), name='geoattempt-pending-batch'),
    path('image/', ImageView.as_view(), name='images'),
    path('image-individual/<int:pk>/', ImageIndividualView.as_view(), name='images-individual'),
    path('geoattempts-calendar/', GeoAttemptsCalendarView.as_view(), name='calendar-geoattempt'),
    path('tutorial-event/', TutorialEventView.as_view(), name='tutorial-event'),
    path('export/images/', ExportImageListView.as_view(), name='export-images'),
    path('export/images/<int:pk>/', ExportImageView.as_view(), name='export-image'),
    path('challenges/', ChallengeListView.as_view(), name='challenges'),
    path('challenges/mine/', MyChallengeView.as_view(), name='challenge-mine'),
    path('challenges/<int:pk>/', ChallengeDetailView.as_view(), name='challenge-detail'),
    path('challenges/<int:pk>/leaderboard/', ChallengeLeaderboardView.as_view(), name='challenge-leaderboard'),
    path('challenges/<int:pk>/join/', ChallengeJoinView.as_view(), name='challenge-join'),
    path('challenges/<int:pk>/leave/', ChallengeLeaveView.as_view(), name='challenge-leave'),
]