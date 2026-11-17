"""
Staff-only read API: control points per image.

    GET /api/v1/export/images/            paginated (?after=<image id>&limit=&updated_since=)
    GET /api/v1/export/images/<id>/       one image

Auth: `Authorization: Bearer <token>` (see user_profile.api_auth). Each item is
an image with its finished geoattempts. Control point pixels (`x_px`, `y_px`) are
in the original file (top-left origin), which is byte-identical to NASA's
`nasa_image_url`.
"""
import os

from django.conf import settings
from django.db.models import Prefetch, Q
from django.http import Http404
from django.utils.dateparse import parse_datetime
from rest_framework.response import Response
from rest_framework.views import APIView

from user_profile.api_auth import ApiTokenAuthentication, ApiTokenThrottle, IsStaffToken

from .mapdata import _nasa_link
from .models import GeoAttempt, Image

DEFAULT_LIMIT = 100
MAX_LIMIT = 500


def _clean_points(raw):
    """Normalise the stored JSON; drop points without usable coordinates."""
    if not isinstance(raw, list):
        return []
    out = []
    for p in raw:
        if not isinstance(p, dict):
            continue
        x, y, lat, lon = p.get('actualPx'), p.get('actualPy'), p.get('lat'), p.get('lon')
        if None in (x, y, lat, lon):
            continue
        out.append({'id': p.get('id'), 'x_px': x, 'y_px': y, 'lat': lat, 'lon': lon})
    return out


def _dimensions(name):
    """Size of media/original/<name>; the first 12 images are named without the
    extension, but their file has it."""
    from PIL import Image as PILImage
    for candidate in (name, name + '.JPG'):
        path = os.path.join(settings.BASE_DIR, 'media', 'original', candidate)
        try:
            with PILImage.open(path) as im:
                return im.size
        except Exception:
            continue
    return (None, None)


def serialize_image(image):
    """`image.done_attempts` must be prefetched (status DONE)."""
    attempts = []
    for ga in image.done_attempts:
        points = _clean_points(ga.controlPoints)
        if not points:
            continue
        attempts.append({
            'id': ga.id,
            'user_id': ga.assignedUser_id,
            'status': ga.status,
            'finished': ga.finishedDateTime.isoformat() if ga.finishedDateTime else None,
            'control_points': points,
        })
    if not attempts:
        return None
    width, height = _dimensions(image.name)
    return {
        'image': {
            'id': image.id,
            'name': image.name,
            'taken': image.taken.isoformat() if image.taken else None,
            'width': width,
            'height': height,
            'nasa_page_url': _nasa_link(image),
            'nasa_image_url': image.largeImageURL or None,
            'nasa_thumbnail_url': image.smallImageURL or None,
        },
        'geoattempts': attempts,
    }


def _with_done_attempts(qs):
    done = GeoAttempt.objects.filter(status='DONE').order_by('id')
    return qs.prefetch_related(Prefetch('geoattempt_set', queryset=done, to_attr='done_attempts'))


class ExportBase(APIView):
    authentication_classes = [ApiTokenAuthentication]
    permission_classes = [IsStaffToken]
    throttle_classes = [ApiTokenThrottle]


class ExportImageView(ExportBase):
    def get(self, request, pk):
        try:
            image = _with_done_attempts(Image.objects.filter(pk=pk)).get()
        except Image.DoesNotExist:
            raise Http404
        data = serialize_image(image)
        if data is None:
            raise Http404
        return Response(data)


class ExportImageListView(ExportBase):
    def get(self, request):
        try:
            limit = min(max(int(request.query_params.get('limit', DEFAULT_LIMIT)), 1), MAX_LIMIT)
            after = int(request.query_params.get('after', 0))
        except ValueError:
            return Response({'error': 'limit and after must be integers.'}, status=400)

        since_raw = request.query_params.get('updated_since')
        since = None
        if since_raw:
            since = parse_datetime(since_raw)
            if since is None:
                return Response({'error': 'updated_since must be an ISO 8601 datetime.'}, status=400)

        done = Q(geoattempt__status='DONE')
        if since:
            done &= Q(geoattempt__finishedDateTime__gte=since)
        ids = list(Image.objects.filter(done, id__gt=after).order_by('id')
                   .values_list('id', flat=True).distinct()[:limit + 1])
        has_more = len(ids) > limit
        ids = ids[:limit]

        images = _with_done_attempts(Image.objects.filter(id__in=ids)).order_by('id')
        results = [d for d in map(serialize_image, images) if d]
        next_url = None
        if has_more and ids:
            params = request.query_params.copy()
            params['after'] = ids[-1]
            params['limit'] = limit
            next_url = request.build_absolute_uri(request.path) + '?' + params.urlencode()
        return Response({'results': results, 'next': next_url})
