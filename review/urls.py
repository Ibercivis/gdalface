from django.urls import path

from .views import FootprintsView, VoteView, review_map, review_team

urlpatterns = [
    path('review/', review_map, name='review_map'),
    path('review/team/<int:team_id>/', review_team, name='review_team'),
    path('api/v1/review/footprints/', FootprintsView.as_view(), name='review-footprints'),
    path('api/v1/review/vote/', VoteView.as_view(), name='review-vote'),
]
