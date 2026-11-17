"""Database side of overlay generation: decide what needs (re)building and store results."""
import os

from django.conf import settings

from . import overlays
from .models import AttemptOverlay


def plan(attempt, force=False, retry_failed=False):
    """Return (points, digest, out_rel_path) if `attempt` needs (re)building, else None.
    `attempt` must have `image` loaded."""
    points = overlays.attempt_points(attempt)
    digest = overlays.points_hash(points)
    current = getattr(attempt, 'overlay', None)
    if current and not force and current.points_hash == digest:
        if current.status == AttemptOverlay.OK and current.file and \
                os.path.isfile(os.path.join(settings.MEDIA_ROOT, current.file)):
            return None
        if current.status == AttemptOverlay.SKIPPED:
            return None
        if current.status == AttemptOverlay.FAILED and not retry_failed:
            return None
    return points, digest, overlays.overlay_rel_path(attempt.pk, digest)


def run(attempt, points, rel_path):
    """Render (no DB). Returns ('ok', footprint) or (status, detail)."""
    try:
        fp = overlays.render(points, attempt.image.name, os.path.join(settings.MEDIA_ROOT, rel_path))
        return AttemptOverlay.OK, fp
    except overlays.OverlayError as e:
        return e.status, e.detail
    except Exception as e:      # never let one bad photo stop a batch
        return AttemptOverlay.FAILED, f'{type(e).__name__}: {e}'[:300]


def store(attempt, points, digest, rel_path, status, payload):
    """Persist the outcome and drop the superseded file."""
    old = AttemptOverlay.objects.filter(geoattempt=attempt).first()
    fields = dict(points_hash=digest, status=status, n_points=len(points), detail='', file='',
                  south=None, west=None, north=None, east=None, polygon=None,
                  width=None, height=None, bytes=0, area_km2=None)
    if status == AttemptOverlay.OK:
        fields.update(file=rel_path, **payload)
    else:
        fields['detail'] = str(payload)[:300]
    obj, _ = AttemptOverlay.objects.update_or_create(geoattempt=attempt, defaults=fields)
    if old and old.file and old.file != obj.file:
        try:
            os.remove(os.path.join(settings.MEDIA_ROOT, old.file))
        except OSError:
            pass
    return obj
