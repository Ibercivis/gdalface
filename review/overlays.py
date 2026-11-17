"""
Warp one attempt's photo onto the map and describe its footprint.

Pipeline (GDAL command line, no shell, one temp dir per call):
  gdal_translate -of VRT -a_srs EPSG:4326 -gcp ...   (control points → VRT, no copy of the JPEG)
  gdalwarp -tps -t_srs EPSG:3857 -dstalpha -ts 2048 0 (thin-plate-spline warp, transparent outside)
  gdal_translate -of WEBP                            (what the browser downloads)

The source is the full-resolution original (media/original); only the capped WebP
is ever sent to a browser. `render()` touches no database so it can run in threads.
"""
import hashlib
import json
import math
import os
import subprocess
import tempfile

from django.conf import settings
from PIL import Image as PILImage

from georeferencing.export import _clean_points

MAX_WIDTH = 2048
MIN_POINTS = 3
GDAL_TIMEOUT = 180
MAX_HEIGHT = 8192          # a TPS blow-up makes the warped raster absurdly tall
MERCATOR_R = 6378137.0
OUTLINE_GRID = 160         # alpha mask is reduced to ~this many columns for the outline


class OverlayError(Exception):
    def __init__(self, status, detail):
        super().__init__(detail)
        self.status = status       # 'skipped' | 'failed'
        self.detail = detail


def source_path(image_name):
    base = os.path.join(settings.MEDIA_ROOT, 'original')
    for candidate in (image_name, image_name + '.JPG'):   # the first 12 images lack the extension
        path = os.path.join(base, candidate)
        if os.path.isfile(path):
            return path
    return None


def points_hash(points):
    rounded = [[p['id'], round(p['x_px'], 2), round(p['y_px'], 2), round(p['lat'], 6), round(p['lon'], 6)]
               for p in points]
    return hashlib.sha1(json.dumps(rounded).encode()).hexdigest()


def overlay_rel_path(attempt_id, digest):
    return f'overlays/{attempt_id}-{digest[:12]}.webp'


def _run(args):
    try:
        return subprocess.run(args, check=True, capture_output=True, text=True, timeout=GDAL_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise OverlayError('failed', f'{args[0]} timed out after {GDAL_TIMEOUT}s')
    except subprocess.CalledProcessError as e:
        raise OverlayError('failed', f'{args[0]}: {(e.stderr or "").strip()[-250:]}')


def _merc_to_latlon(x, y):
    lon = x / MERCATOR_R * 180 / math.pi
    lat = (2 * math.atan(math.exp(y / MERCATOR_R)) - math.pi / 2) * 180 / math.pi
    return lat, lon


def _rdp(pts, eps):
    """Ramer–Douglas–Peucker on an open polyline."""
    if len(pts) < 3:
        return pts
    (x1, y1), (x2, y2) = pts[0], pts[-1]
    dx, dy = x2 - x1, y2 - y1
    norm = math.hypot(dx, dy) or 1e-12
    idx, dmax = 0, 0.0
    for i in range(1, len(pts) - 1):
        d = abs(dy * pts[i][0] - dx * pts[i][1] + x2 * y1 - y2 * x1) / norm
        if d > dmax:
            idx, dmax = i, d
    if dmax > eps:
        return _rdp(pts[:idx + 1], eps)[:-1] + _rdp(pts[idx:], eps)
    return [pts[0], pts[-1]]


def _outline(webp_path, gt):
    """Polygon (lon, lat ring) of the opaque part of the warped photo."""
    with PILImage.open(webp_path) as im:
        width, height = im.size
        # libwebp drops the alpha channel when nothing is transparent.
        alpha = im.getchannel('A') if 'A' in im.getbands() else PILImage.new('L', im.size, 255)
    factor = max(1, width // OUTLINE_GRID)
    small = alpha.reduce(factor)
    sw, sh = small.size
    px = small.load()
    left, right = [], []
    for y in range(sh):
        xs = [x for x in range(sw) if px[x, y] > 0]
        if xs:
            left.append((xs[0], y))
            right.append((xs[-1] + 1, y + 1))
    if len(left) < 2:
        raise OverlayError('failed', 'warped photo has no visible area')
    ring = _rdp(left, 1.2) + _rdp(right[::-1], 1.2)
    out = []
    for (cx, cy) in ring:
        mx = gt[0] + gt[1] * cx * factor
        my = gt[3] + gt[5] * cy * factor
        lat, lon = _merc_to_latlon(mx, my)
        out.append([round(lon, 5), round(lat, 5)])
    out.append(out[0])
    return out


def _area_km2(ring):
    """Ground area of a lon/lat ring (local equirectangular approximation)."""
    lat0 = sum(p[1] for p in ring) / len(ring)
    kx = 111.32 * math.cos(math.radians(lat0))
    ky = 110.57
    pts = [(p[0] * kx, p[1] * ky) for p in ring]
    s = sum(pts[i][0] * pts[i + 1][1] - pts[i + 1][0] * pts[i][1] for i in range(len(pts) - 1))
    return abs(s) / 2


def render(points, image_name, out_path):
    """Warp and write the WebP to `out_path`. Returns the footprint dict.
    Raises OverlayError('skipped'|'failed', detail)."""
    if len(points) < MIN_POINTS:
        raise OverlayError('skipped', f'needs at least {MIN_POINTS} control points (has {len(points)})')
    lons = [p['lon'] for p in points]
    lats = [p['lat'] for p in points]
    if max(lons) - min(lons) > 180:
        raise OverlayError('skipped', 'control points cross the antimeridian')
    if max(abs(v) for v in lats) > 80:
        raise OverlayError('skipped', 'control points too close to the poles for Web Mercator')
    src = source_path(image_name)
    if not src:
        raise OverlayError('failed', f'original file not found for {image_name}')

    with tempfile.TemporaryDirectory(prefix='overlay-') as tmp:
        vrt = os.path.join(tmp, 'gcp.vrt')
        warped = os.path.join(tmp, 'warped.tif')
        webp = os.path.join(tmp, 'out.webp')
        cmd = ['gdal_translate', '-q', '-of', 'VRT', '-a_srs', 'EPSG:4326']
        for p in points:
            cmd += ['-gcp', f"{p['x_px']:.3f}", f"{p['y_px']:.3f}", f"{p['lon']:.7f}", f"{p['lat']:.7f}"]
        _run(cmd + [src, vrt])
        _run(['gdalwarp', '-q', '-overwrite', '-tps', '-t_srs', 'EPSG:3857', '-dstalpha', '-r', 'average',
              '-ts', str(MAX_WIDTH), '0', '-co', 'COMPRESS=DEFLATE', vrt, warped])
        info = json.loads(_run(['gdalinfo', '-json', warped]).stdout)
        width, height = info['size']
        if height > MAX_HEIGHT:
            raise OverlayError('failed', f'warp is too distorted ({width}x{height})')
        gt = info['geoTransform']
        _run(['gdal_translate', '-q', '-of', 'WEBP', '-co', 'QUALITY=80', warped, webp])
        ring = _outline(webp, gt)
        north, west = _merc_to_latlon(gt[0], gt[3])
        south, east = _merc_to_latlon(gt[0] + gt[1] * width, gt[3] + gt[5] * height)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        _copy(webp, out_path)
        return {
            'south': south, 'west': west, 'north': north, 'east': east,
            'polygon': ring, 'width': width, 'height': height,
            'bytes': os.path.getsize(out_path), 'area_km2': round(_area_km2(ring), 1),
        }


def _copy(src, dst):
    import shutil
    tmp = dst + '.part'
    shutil.copyfile(src, tmp)
    os.replace(tmp, dst)


def attempt_points(geoattempt):
    return _clean_points(geoattempt.controlPoints)
