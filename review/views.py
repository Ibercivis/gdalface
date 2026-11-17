"""Staff-only review of georeferencing attempts: footprints, vote, and the map page."""
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Count, OuterRef, Q, Subquery
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from georeferencing.models import GeoAttempt
from teams.models import Team

from .models import AttemptOverlay, AttemptReview


def _team_attempts_q(team):
    """Attempts done by the team's members while they were members (same rule as the
    team's score: each membership counts from joined_at until left_at, if any)."""
    q = Q(pk__in=[])
    for m in team.memberships.all():
        window = Q(geoattempt__assignedUser_id=m.user_id, geoattempt__finishedDateTime__gte=m.joined_at)
        if m.left_at:
            window &= Q(geoattempt__finishedDateTime__lte=m.left_at)
        q |= window
    return q


class FootprintsView(APIView):
    """GeoJSON of every attempt that has an overlay: one polygon each.
    `?team=<id>` keeps only what that team's members did while in the team."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        mine = AttemptReview.objects.filter(geoattempt=OuterRef('geoattempt_id'), user=request.user)
        rows = (AttemptOverlay.objects.filter(status=AttemptOverlay.OK, polygon__isnull=False)
                .select_related('geoattempt__image')
                .annotate(n_ok=Count('geoattempt__reviews', filter=Q(geoattempt__reviews__verdict='ok')),
                          n_not_ok=Count('geoattempt__reviews', filter=Q(geoattempt__reviews__verdict='not_ok')),
                          my_vote=Subquery(mine.values('verdict')[:1]))
                .order_by('geoattempt_id'))
        team_id = request.query_params.get('team')
        if team_id:
            team = get_object_or_404(Team, pk=team_id)
            rows = rows.filter(_team_attempts_q(team))
        features = []
        for o in rows:
            ga, image = o.geoattempt, o.geoattempt.image
            features.append({
                'type': 'Feature',
                'geometry': {'type': 'Polygon', 'coordinates': [o.polygon]},
                'properties': {
                    'id': ga.id,
                    'image_id': image.id,
                    'name': (image.name or '').replace('.JPG', '').replace('.jpg', ''),
                    'taken': image.taken.date().isoformat() if image.taken else None,
                    'points': o.n_points,
                    'area_km2': o.area_km2,
                    'bounds': [[o.south, o.west], [o.north, o.east]],
                    'overlay': f'{settings.MEDIA_URL}{o.file}',
                    'user_id': ga.assignedUser_id,
                    'own': ga.assignedUser_id == request.user.id,
                    'ok': o.n_ok, 'not_ok': o.n_not_ok, 'mine': o.my_vote,
                },
            })
        resp = Response({'type': 'FeatureCollection', 'features': features})
        resp['Cache-Control'] = 'no-store'
        return resp


class VoteView(APIView):
    """POST {geoattempt, verdict: 'ok' | 'not_ok'}. One vote per user and attempt;
    sending again changes it. You cannot review your own attempt."""
    permission_classes = [IsAdminUser]

    def post(self, request):
        verdict = request.data.get('verdict')
        if verdict not in (AttemptReview.OK, AttemptReview.NOT_OK):
            return Response({'error': "verdict must be 'ok' or 'not_ok'."}, status=400)
        try:
            attempt_id = int(request.data.get('geoattempt'))
        except (TypeError, ValueError):
            return Response({'error': 'geoattempt must be an integer id.'}, status=400)
        attempt = GeoAttempt.objects.filter(pk=attempt_id, status='DONE',
                                            overlay__status=AttemptOverlay.OK).first()
        if attempt is None:
            return Response({'error': 'No reviewable attempt with that id.'}, status=404)
        if attempt.assignedUser_id == request.user.id:
            return Response({'error': 'You cannot review your own attempt.'}, status=403)
        AttemptReview.objects.update_or_create(geoattempt=attempt, user=request.user,
                                               defaults={'verdict': verdict})
        counts = AttemptReview.objects.filter(geoattempt=attempt).aggregate(
            ok=Count('id', filter=Q(verdict='ok')), not_ok=Count('id', filter=Q(verdict='not_ok')))
        return Response({'geoattempt': attempt.id, 'mine': verdict, **counts})


@never_cache
@ensure_csrf_cookie
@login_required
def review_map(request):
    if not request.user.is_staff:
        raise Http404
    return render(request, 'review/map.html')


@never_cache
@ensure_csrf_cookie
@login_required
def review_team(request, team_id):
    """The review map restricted to one team's work. Staff only."""
    if not request.user.is_staff:
        raise Http404
    team = get_object_or_404(Team, pk=team_id)
    return render(request, 'review/map.html', {'team': team})
