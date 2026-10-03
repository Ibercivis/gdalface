import os
import re
import requests
from decouple import config
from .models import GeoAttempt, Image, Batch, FailedImage
from datetime import timedelta, datetime
from django.utils import timezone
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.db.models import F, Value
from django.db.models.functions import Concat, Coalesce
from django_rq import job

# Map the 2-character camera code stored in the `frames` table to a human
# description. The `camera` table (used for uncataloged photos) already holds
# free text (make/model/serial), so it is stored as-is.
CAMERA_CODES = {
    'AA': 'Ansco Autoset',
    'C1': 'Canon Digital IXUS 700',
    'DV': 'Sony HDW-700 HDTV',
    'E2': 'Kodak DCS460 Electronic Still Camera',
    'E3': 'Kodak DCS660 Electronic Still Camera',
    'E4': 'Kodak DCS760c Electronic Still Camera',
    'HB': 'Hasselblad',
    'LH': 'Linhof',
    'MA': 'Maurer model 220G',
    'MS': 'Maurer with Xenotar 80mm f/2.8 lens',
    'N1': 'Nikon D1 Electronic Still Camera',
    'N2': 'Nikon D2Xs Electronic Still Camera',
    'N3': 'Nikon D3 Electronic Still Camera',
    'N4': 'Nikon D3X Electronic Still Camera',
    'N5': 'Nikon D3S Electronic Still Camera',
    'N6': 'Nikon D4 Electronic Still Camera',
    'N7': 'Nikon D800E Electronic Still Camera',
    'N8': 'Nikon D5 Electronic Still Camera',
    'N9': 'Nikon D850 Electronic Still Camera',
    'NK': 'Nikon 35mm film camera',
    'RX': 'Rolleiflex',
    'SA': 'Skylab Multispectral (S190A)',
    'SB': 'Skylab Earth Terrain (S190B)',
}


@job('lost_scheduler')  # Specify the queue (default, high, low) here
def update_assigned(*args, **kwargs):
    """
    Reset abandoned tasks back to PENDING.

    Finds GeoAttempts in ASSIGNED state whose `assignedDateTime` is older
    than ABANDON_HOURS hours ago (likely the user closed the tab without
    skip/submit) and flips them to PENDING so other users can pick them.
    """
    ABANDON_HOURS = 6
    try:
        GeoAttempt.objects.filter(
            status='ASSIGNED',
            assignedDateTime__lt=timezone.now() - timedelta(hours=ABANDON_HOURS)
        ).update(status='PENDING', assignedUser=None, assignedDateTime=None,
                 numberTries=0)
    except Exception as e:
        # Log error silently without interrupting the queue
        return None
    # Safety net for the daily cron (seen not firing on 2026-10-02/03): if the
    # public snapshot is older than a day, regenerate it from here.
    try:
        refresh_snapshot_if_stale()
    except Exception:
        pass


def refresh_snapshot_if_stale(max_age_hours=24):
    """Rewrite the public stats snapshot when missing or older than max_age_hours."""
    from .stats import read_snapshot, write_snapshot
    snap = read_snapshot()
    stale = True
    if snap and snap.get('generated_at'):
        try:
            generated = datetime.fromisoformat(snap['generated_at'])
            if timezone.is_naive(generated):
                generated = timezone.make_aware(generated, timezone.utc)
            stale = timezone.now() - generated > timedelta(hours=max_age_hours)
        except ValueError:
            stale = True
    if stale:
        write_snapshot()
        return True
    return False


@job('lost_scheduler')
def reconcile_counters_job():
    """Weekly: measure counter drift (dry run) and log it as a StatsEvent so it
    shows on the staff panel. Applying is a manual decision for now:
    `manage.py reconcile_counters --apply`."""
    from io import StringIO
    from django.core.management import call_command
    from .models import StatsEvent
    out = StringIO()
    call_command('reconcile_counters', '--quiet', stdout=out)
    summary = out.getvalue().strip()
    StatsEvent.objects.create(kind='other', title='Counter drift check (weekly, dry run)', note=summary)
    return summary


@job('lost_scheduler')  # Specify the queue (default, high, low) here
def download_image(image):
    """
    download_image is an RQ task that downloads an image from a given URL and stores it in the 'media/original/' folder.
    Sets image.status to DOWNLOADED, FAILED_DOWNLOADED, or DOWNLOADED_GENERATED accordingly.
    """
    try:
        file_name = os.path.basename(image.largeImageURL)
        large_ok = False
        small_ok = False

        # Download large image
        try:
            response = requests.get(image.largeImageURL, timeout=20)
            response.raise_for_status()
            saved_path = default_storage.save(os.path.join('original', file_name), ContentFile(response.content))
            large_ok = True
        except requests.exceptions.RequestException:
            pass

        # Download small image
        try:
            response = requests.get(image.smallImageURL, timeout=20)
            response.raise_for_status()
            saved_path = default_storage.save(os.path.join('small', file_name), ContentFile(response.content))
            small_ok = True
        except requests.exceptions.RequestException:
            pass

        if not large_ok and not small_ok:
            # Both downloads failed — mark image as failed, do not create GeoAttempts
            image.status = 'FAILED_DOWNLOADED'
            image.save(update_fields=['status'])
            return None

        # At least one download succeeded — create GeoAttempts
        image.status = 'DOWNLOADED'
        image.save(update_fields=['status'])

        for _ in range(image.replicas):
            GeoAttempt.objects.create(image=image, status='PENDING')

        image.status = 'DOWNLOADED_GENERATED'
        image.save(update_fields=['status'])

    except Exception as e:
        # Catch any other unexpected errors
        try:
            image.status = 'FAILED_DOWNLOADED'
            image.save(update_fields=['status'])
        except Exception:
            pass
        return None

def _add_log(batch_id, level, message):
    """Append a log line to the batch log atomically (null-safe)."""
    timestamp = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"\n[{level}] {timestamp} - {message}"
    Batch.objects.filter(pk=batch_id).update(
        log=Concat(Coalesce(F('log'), Value('')), Value(line))
    )


def _flush_log(batch_id, lines):
    """Write a list of log lines to the batch log in a single atomic update."""
    if not lines:
        return
    block = ''.join(lines)
    Batch.objects.filter(pk=batch_id).update(
        log=Concat(Coalesce(F('log'), Value('')), Value(block))
    )


@job('lost_scheduler', timeout=300)
def generate_from_list(batch):
    """
    Dispatcher: splits the image list and enqueues one process_single_image job per entry.
    Finishes in seconds regardless of list size.
    """
    image_list = [img.strip() for img in re.split(r'[,\n\r]+', batch.originalImages) if img.strip()]
    total = len(image_list)

    # Initialise batch state, clearing the previous log and counters
    Batch.objects.filter(pk=batch.pk).update(
        processing_status='PROCESSING',
        processing_start_time=timezone.now(),
        processing_end_time=None,
        total_images_in_queue=total,
        processed_images_in_queue=0,
        numberImages=0,
        log=f"[II] {timezone.now().strftime('%Y-%m-%d %H:%M:%S')} - ====== INICIO DEL PROCESAMIENTO DEL BATCH ===="
    )
    _add_log(batch.pk, 'II', f"Batch '{batch.name}' — Total de imágenes a procesar: {total}")

    # Clear previous failure records for this batch so a re-run starts clean
    FailedImage.objects.filter(batch_id=batch.pk).delete()

    for idx, image_name in enumerate(image_list, start=1):
        process_single_image.delay(batch.pk, image_name, idx, total)

    _add_log(batch.pk, 'II', f"Todos los jobs encolados ({total}). El batch se marcará COMPLETED cuando terminen.")
    return True


@job('lost_scheduler', timeout=600)
def process_single_image(batch_id, image_name, idx, total):
    """
    Resolve a single image name end-to-end by exact mission/roll/frame match:

      1. images  → directory + filename of the large file (skip if none).
      2. nadir   → if present, photo is UNCATALOGED:
                     spacecraftNadirPoint = nadir.lat/lon, plus the `camera`
                     table (camera/focal) and `mlcoord` (ML centre, if any).
                   else frames → CATALOGED:
                     photoCenterPoint = frames.lat/lon, spacecraftNadirPoint =
                     frames.nlat/nlon, camera code → description, focal.
      3. download large + small, create GeoAttempts.

    Querying each table by mission|roll|frame with `eq` avoids the old
    `filename|like|*name*` bug (e.g. *7033* matching 70331..70339) and the
    implicit INNER JOIN that dropped uncataloged photos (frames in the return).

    Names that cannot be resolved are written to FailedImage (one row per
    batch+name); a later successful run removes that row. Log lines are
    buffered and flushed in a single write at the end.
    """
    log_buffer = []
    images_ready = 0

    def log_info(msg):
        timestamp = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
        log_buffer.append(f"\n[II] {timestamp} - {msg}")

    def log_error(msg):
        timestamp = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
        log_buffer.append(f"\n[EE] {timestamp} - {msg}")

    def record_failure(reason, detail=''):
        try:
            FailedImage.objects.update_or_create(
                batch_id=batch_id, name=image_name,
                defaults={'reason': reason, 'detail': (detail or '')[:2000]},
            )
        except Exception:
            pass

    try:
        batch = Batch.objects.get(pk=batch_id)
    except Batch.DoesNotExist:
        return None

    key = config('NASA_API_KEY')
    base_url = 'https://eol.jsc.nasa.gov/SearchPhotos/PhotosDatabaseAPI/PhotosDatabaseAPI.pl'

    log_info("=================================")
    log_info(f"[{idx}/{total}] Procesando imagen: {image_name}")

    # --- helpers -------------------------------------------------------------
    def api_query(table, return_fields, extra=''):
        """Query one table by mission/roll/frame (exact). Returns a list of dict rows ([] if none)."""
        query = (f'{table}|mission|eq|{mission}|{table}|roll|eq|{roll}'
                 f'|{table}|frame|eq|{frame}{extra}')
        params = {'query': query, 'return': return_fields, 'key': key}
        url = f"{base_url}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []

    def to_int(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    def parse_dt(pdate, ptime, default):
        if pdate and ptime:
            try:
                return datetime.strptime(f"{pdate} {ptime}", '%Y%m%d %H%M%S')
            except (ValueError, TypeError):
                pass
        return default

    # --- parse name into mission / roll / frame (e.g. ISS046-E-21509) --------
    parts = image_name.strip().split('-')
    if len(parts) < 3:
        log_error(f"[{idx}/{total}] Nombre con formato inesperado: {image_name}")
        record_failure('PARSE_ERROR', f'No se pudo separar mission/roll/frame de "{image_name}"')
        _flush_log(batch_id, log_buffer)
        return _finalize_if_last(batch_id, idx, total, 0)
    mission, roll, frame = '-'.join(parts[:-2]), parts[-2], parts[-1]

    # --- 1. images: locate the large file (skip if it does not exist) --------
    try:
        img_rows = api_query('images', 'images|directory|images|filename',
                             extra='|images|directory|like|*large*')
    except (requests.RequestException, ValueError) as e:
        log_error(f"[{idx}/{total}] Error consultando 'images': {e}")
        record_failure('API_ERROR', f'images: {e}')
        _flush_log(batch_id, log_buffer)
        return _finalize_if_last(batch_id, idx, total, 0)

    if not img_rows:
        log_error(f"[{idx}/{total}] Sin fichero grande en 'images' para {image_name}")
        record_failure('NOT_FOUND', 'No hay registro en la tabla images (sin fichero grande)')
        _flush_log(batch_id, log_buffer)
        return _finalize_if_last(batch_id, idx, total, 0)

    directory = img_rows[0].get('images.directory')
    filename = img_rows[0].get('images.filename')
    largeImageURL = f"https://eol.jsc.nasa.gov/DatabaseImages/{directory}/{filename}"
    smallImageURL = largeImageURL.replace('large', 'small')

    # --- 2. coordinates / metadata: nadir first (most photos are uncataloged)
    photo_center = None
    nadir_point = None
    ml_coords = None
    camera_val = None
    focal = None
    taken_dt = timezone.now()

    try:
        nadir_rows = api_query('nadir', 'nadir|lat|nadir|lon|nadir|pdate|nadir|ptime')
    except (requests.RequestException, ValueError):
        nadir_rows = []

    if nadir_rows:
        # UNCATALOGED — nadir point only; enrich with camera + mlcoord
        nd = nadir_rows[0]
        nlat, nlon = nd.get('nadir.lat'), nd.get('nadir.lon')
        if nlat is not None and nlon is not None:
            nadir_point = f"{nlat}, {nlon}"
        taken_dt = parse_dt(nd.get('nadir.pdate'), nd.get('nadir.ptime'), taken_dt)

        # camera table: free-text make/model + focal length
        try:
            cam_rows = api_query('camera', 'camera|camera|camera|fclt')
            if cam_rows:
                camera_val = cam_rows[0].get('camera.camera')
                focal = to_int(cam_rows[0].get('camera.fclt'))
        except (requests.RequestException, ValueError):
            pass

        # mlcoord: ML centre (sparse, but better than nadir for the game)
        try:
            ml_rows = api_query('mlcoord', 'mlcoord|lat|mlcoord|lon')
            if ml_rows:
                mlat, mlon = ml_rows[0].get('mlcoord.lat'), ml_rows[0].get('mlcoord.lon')
                if mlat is not None and mlon is not None:
                    ml_coords = f"{mlat}, {mlon}"
        except (requests.RequestException, ValueError):
            pass
    else:
        # CATALOGED → frames (centre + nadir + camera code + focal)
        try:
            fr_rows = api_query(
                'frames',
                'frames|lat|frames|lon|frames|nlat|frames|nlon|'
                'frames|camera|frames|fclt|frames|pdate|frames|ptime',
            )
        except (requests.RequestException, ValueError):
            fr_rows = []
        if fr_rows:
            fr = fr_rows[0]
            flat, flon = fr.get('frames.lat'), fr.get('frames.lon')
            if flat is not None and flon is not None:
                photo_center = f"{flat}, {flon}"
            fnlat, fnlon = fr.get('frames.nlat'), fr.get('frames.nlon')
            if fnlat is not None and fnlon is not None:
                nadir_point = f"{fnlat}, {fnlon}"
            code = fr.get('frames.camera')
            camera_val = CAMERA_CODES.get(code, code) if code else None
            focal = to_int(fr.get('frames.fclt'))
            taken_dt = parse_dt(fr.get('frames.pdate'), fr.get('frames.ptime'), taken_dt)

    # --- 3. create Image, download files, generate GeoAttempts ---------------
    try:
        img = Image.objects.create(
            name=filename,
            taken=taken_dt,
            focalLength=focal or 0,
            camera=camera_val[:100] if camera_val else None,
            spacecraftNadirPoint=nadir_point,
            photoCenterPoint=photo_center,
            photoCenterByMachineLearning=ml_coords,
            largeImageURL=largeImageURL,
            smallImageURL=smallImageURL,
            batch=batch,
            replicas=batch.replicas,
            status='PENDING',
        )

        file_name = os.path.basename(largeImageURL)
        large_ok = small_ok = False
        try:
            resp = requests.get(largeImageURL, timeout=30)
            resp.raise_for_status()
            default_storage.save(os.path.join('original', file_name), ContentFile(resp.content))
            large_ok = True
        except requests.exceptions.RequestException:
            pass
        try:
            resp = requests.get(smallImageURL, timeout=30)
            resp.raise_for_status()
            default_storage.save(os.path.join('small', file_name), ContentFile(resp.content))
            small_ok = True
        except requests.exceptions.RequestException:
            pass

        if not large_ok and not small_ok:
            img.status = 'FAILED_DOWNLOADED'
            img.save(update_fields=['status'])
            log_error(f"[{idx}/{total}] Descarga fallida para {filename}")
            record_failure('DOWNLOAD_FAILED', f'No se pudo descargar {filename}')
            _flush_log(batch_id, log_buffer)
            return _finalize_if_last(batch_id, idx, total, 0)

        img.status = 'DOWNLOADED'
        img.save(update_fields=['status'])
        for _ in range(img.replicas):
            GeoAttempt.objects.create(image=img, status='PENDING')
        img.status = 'DOWNLOADED_GENERATED'
        img.save(update_fields=['status'])
        images_ready = 1

    except Exception as e:
        log_error(f"[{idx}/{total}] Error creando/descargando {filename}: {e}")
        record_failure('ERROR', str(e))
        _flush_log(batch_id, log_buffer)
        return _finalize_if_last(batch_id, idx, total, 0)

    # Success — drop any previous failure record for this name in this batch
    try:
        FailedImage.objects.filter(batch_id=batch_id, name=image_name).delete()
    except Exception:
        pass

    cataloged = 'catalogada' if photo_center else 'no catalogada'
    log_info(f"[{idx}/{total}] '{image_name}' OK ({cataloged}) → {filename}")
    _flush_log(batch_id, log_buffer)
    return _finalize_if_last(batch_id, idx, total, images_ready)


def _finalize_if_last(batch_id, idx, total, images_created):
    """
    Atomically increments processed_images_in_queue and numberImages.
    If this is the last job, marks the batch as COMPLETED (exactly once).
    """
    Batch.objects.filter(pk=batch_id).update(
        processed_images_in_queue=F('processed_images_in_queue') + 1,
        numberImages=F('numberImages') + images_created,
    )
    batch = Batch.objects.get(pk=batch_id)

    if batch.processed_images_in_queue >= total:
        # Conditional update prevents double-completion in parallel workers
        updated = Batch.objects.filter(pk=batch_id, processing_status='PROCESSING').update(
            processing_status='COMPLETED',
            processing_end_time=timezone.now(),
        )
        if updated:
            batch.refresh_from_db()
            _add_log(batch_id, 'II', f"====== BATCH COMPLETADO. Total imágenes: {batch.numberImages} / {total} procesadas ======")

    return True


@job('lost_scheduler')
def write_stats_snapshot():
    """Daily: refresh the public project-stats snapshot (/.well-known/stats.json)."""
    from .stats import write_snapshot
    return write_snapshot()
