"""
GeoJSON of the photos the community has located: one point per image, at the
centroid of every control point placed on it, with the thumbnail and how many
contributions back it. Public data only (no usernames).
"""
import re
from collections import defaultdict

from django.core.cache import cache

CACHE_TTL = 600
ID_RE = re.compile(r'(ISS\d{3})-([A-Z])-(\d+)')


def _nasa_link(image):
    if image.link:
        return image.link
    m = ID_RE.search(image.name or '')
    if not m:
        return None
    return f'https://eol.jsc.nasa.gov/SearchPhotos/photo.pl?mission={m.group(1)}&roll={m.group(2)}&frame={m.group(3)}'


def located_geojson(challenge=None, user=None, use_cache=True):
    """FeatureCollection of located images. `challenge` restricts to the images
    matching it (batch ∩ bbox); `user` marks the viewer's own images with
    `mine: true` (that part is never cached)."""
    from .models import GeoAttempt, Image
    key = f'map:located:v1:{challenge.id if challenge else "all"}'
    data = cache.get(key) if use_cache else None
    if data is None:
        done = GeoAttempt.objects.filter(status='DONE')
        if challenge is not None:
            done = done.filter(image__in=challenge.matching_images())
        acc = defaultdict(lambda: {'lat': 0.0, 'lon': 0.0, 'pts': 0, 'n': 0})
        for ga in done.only('image_id', 'controlPoints').iterator(chunk_size=2000):
            pts = ga.controlPoints if isinstance(ga.controlPoints, list) else []
            got = 0
            for p in pts:
                try:
                    lat, lon = float(p['lat']), float(p['lon'])
                except (KeyError, TypeError, ValueError):
                    continue
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    a = acc[ga.image_id]; a['lat'] += lat; a['lon'] += lon; a['pts'] += 1; got += 1
            if got:
                acc[ga.image_id]['n'] += 1
        images = {i.id: i for i in Image.objects.filter(id__in=list(acc)).only(
            'id', 'name', 'taken', 'smallImageURL', 'link', 'batch_id')}
        pending = set(GeoAttempt.objects.filter(status='PENDING', image_id__in=list(acc))
                      .values_list('image_id', flat=True).distinct())
        try:
            import os
            from django.conf import settings
            small_files = set(os.listdir(os.path.join(settings.MEDIA_ROOT, 'small')))
        except OSError:
            small_files = set()

        def thumb_for(img):
            # Local thumbnail when we have it (a few old rows lack the extension or
            # the file); otherwise NASA's own small version.
            for cand in (img.name, f'{img.name}.JPG'):
                if cand in small_files:
                    return f'/media/small/{cand}'
            if img.smallImageURL:
                return img.smallImageURL
            m = ID_RE.search(img.name or '')
            return f'https://eol.jsc.nasa.gov/DatabaseImages/ESC/small/{m.group(1)}/{m.group(0)}.JPG' if m else None
        features = []
        for iid, a in acc.items():
            img = images.get(iid)
            if not img or not a['pts']:
                continue
            features.append({
                'type': 'Feature',
                'geometry': {'type': 'Point', 'coordinates': [round(a['lon'] / a['pts'], 4), round(a['lat'] / a['pts'], 4)]},
                'properties': {
                    'id': iid,
                    'name': (img.name or '').replace('.JPG', '').replace('.jpg', ''),
                    'taken': img.taken.date().isoformat() if img.taken else None,
                    'contributions': a['n'],
                    'points': a['pts'],
                    'thumb': thumb_for(img),
                    'nasa': _nasa_link(img),
                    'pending': iid in pending,
                },
            })
        data = {'type': 'FeatureCollection', 'features': features,
                'meta': {'images': len(features), 'contributions': sum(f['properties']['contributions'] for f in features),
                         'points': sum(f['properties']['points'] for f in features)}}
        if use_cache:
            cache.set(key, data, CACHE_TTL)
    if user is not None and getattr(user, 'is_authenticated', False):
        mine = set(GeoAttempt.objects.filter(status='DONE', assignedUser=user).values_list('image_id', flat=True))
        if mine:
            data = {**data, 'features': [
                {**f, 'properties': {**f['properties'], 'mine': f['properties']['id'] in mine}} for f in data['features']]}
    return data
