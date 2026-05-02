import os
import re
import requests
from decouple import config
from .models import GeoAttempt, Image, Batch
from datetime import timedelta, datetime
from django.utils import timezone
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.db.models import F, Value
from django.db.models.functions import Concat, Coalesce
from django_rq import job

@job('lost_scheduler')  # Specify the queue (default, high, low) here
def update_assigned(*args, **kwargs):
    """
    update_assigned is an RQ task that updates the status of GeoAttempts that have been assigned but not finished.
    It checks assigned GeoAttempts that have `assignedDateTime` more than 24 hours ago and updates their status to 'PENDING'.
    """
    try:
        GeoAttempt.objects.filter(
            status='ASSIGNED', 
            assignedDateTime__lt=timezone.now() - timedelta(hours=6)
        ).update(status='PENDING')
    except Exception as e:
        # Log error silently without interrupting the queue
        return None


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

    for idx, image_name in enumerate(image_list, start=1):
        process_single_image.delay(batch.pk, image_name, idx, total)

    _add_log(batch.pk, 'II', f"Todos los jobs encolados ({total}). El batch se marcará COMPLETED cuando terminen.")
    return True


@job('lost_scheduler', timeout=600)
def process_single_image(batch_id, image_name, idx, total):
    """
    Processes a single image name end-to-end: queries NASA API, creates Image objects,
    downloads the files, creates GeoAttempts, then writes a single log entry and marks
    the batch COMPLETED when it is the last job.
    Log lines are buffered in memory and flushed in a single write at the end.
    """
    log_buffer = []
    images_ready = 0  # images fully downloaded with GeoAttempts created

    def log_info(msg):
        timestamp = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
        log_buffer.append(f"\n[II] {timestamp} - {msg}")

    def log_error(msg):
        timestamp = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
        log_buffer.append(f"\n[EE] {timestamp} - {msg}")

    try:
        batch = Batch.objects.get(pk=batch_id)
    except Batch.DoesNotExist:
        return None

    key = config('NASA_API_KEY')
    base_url = 'https://eol.jsc.nasa.gov/SearchPhotos/PhotosDatabaseAPI/PhotosDatabaseAPI.pl'

    log_info(f"=================================")
    log_info(f"[{idx}/{total}] Procesando imagen: {image_name}")

    errors = []

    try:
        params = {
            'query': f'images|directory|like|*large*|images|filename|like|*{image_name}*',
            'return': 'images|directory|images|filename|frames|lat|frames|lon|frames|elev|frames|azi|frames|pdate|frames|ptime|frames|fclt|',
            'key': key
        }
        url_request = f"{base_url}?{'&'.join(f'{k}={v}' for k, v in params.items())}"

        try:
            response = requests.get(url_request, timeout=10)
        except requests.exceptions.RequestException as e:
            log_error(f"[{idx}/{total}] Error de conexión con la API: {str(e)}")
            _flush_log(batch_id, log_buffer)
            return _finalize_if_last(batch_id, idx, total, 0)

        if response.status_code != 200:
            log_error(f"[{idx}/{total}] La API respondió con código de error: {response.status_code}")
            _flush_log(batch_id, log_buffer)
            return _finalize_if_last(batch_id, idx, total, 0)

        data = response.json()

        if isinstance(data, dict) and data.get('result') == 'SQL found no records that match the specified criteria':
            log_error(f"[{idx}/{total}] No se encontraron registros para {image_name}")
            _flush_log(batch_id, log_buffer)
            return _finalize_if_last(batch_id, idx, total, 0)

        if isinstance(data, list) and len(data) == 0:
            log_error(f"[{idx}/{total}] Lista de resultados vacía para {image_name}")
            _flush_log(batch_id, log_buffer)
            return _finalize_if_last(batch_id, idx, total, 0)

        log_info(f"[{idx}/{total}] API devolvió {len(data)} registro(s)")

        for d in data:
            try:
                filename = d['images.filename']
                largeImageURL = f"https://eol.jsc.nasa.gov/DatabaseImages/{d['images.directory']}/{filename}"

                url_request2 = (
                    f'{base_url}?query=images|directory|like|*large*|images|filename|like|*{filename}*'
                    f'&return=frames|lat|frames|lon&key={key}'
                )
                url_request3 = (
                    f'{base_url}?query=images|directory|like|*large*|images|filename|like|*{filename}*'
                    f'&return=mlcoord|lat|mlcoord|lon&key={key}'
                )

                # frames center
                frames_center = None
                try:
                    r2 = requests.get(url_request2, timeout=10)
                    if r2.status_code == 200:
                        fd = r2.json()
                        if isinstance(fd, list) and fd:
                            flat, flon = fd[0].get('frames.lat'), fd[0].get('frames.lon')
                            if flat is not None and flon is not None:
                                frames_center = f"{flat}, {flon}"
                except requests.exceptions.RequestException:
                    pass

                # ML coords
                ml_coords = None
                try:
                    r3 = requests.get(url_request3, timeout=10)
                    if r3.status_code == 200:
                        md = r3.json()
                        if isinstance(md, list) and md:
                            mlat, mlon = md[0].get('mlcoord.lat'), md[0].get('mlcoord.lon')
                            if mlat is not None and mlon is not None:
                                ml_coords = f"{mlat}, {mlon}"
                except requests.exceptions.RequestException:
                    pass

                # Date
                taken_datetime = timezone.now()
                pdate, ptime = d.get('frames.pdate'), d.get('frames.ptime')
                if pdate and ptime:
                    try:
                        taken_datetime = datetime.strptime(f"{pdate} {ptime}", '%Y%m%d %H%M%S')
                    except (ValueError, TypeError):
                        pass

                nadir_lat, nadir_lon = d.get('nadir.lat'), d.get('nadir.lon')
                spacecraft_nadir_point = f"{nadir_lat}, {nadir_lon}" if nadir_lat is not None and nadir_lon is not None else None

                img = Image.objects.create(
                    name=filename,
                    taken=taken_datetime,
                    focalLength=d.get('frames.fclt', 0),
                    spacecraftNadirPoint=spacecraft_nadir_point,
                    spaceCraftAltitude=d.get('frames.elev', 0),
                    photoCenterPoint=frames_center,
                    photoCenterByMachineLearning=ml_coords,
                    largeImageURL=largeImageURL,
                    smallImageURL=largeImageURL.replace('large', 'small'),
                    batch=batch,
                    replicas=batch.replicas,
                    status='PENDING',
                )

                # --- Inline download (large + small) ---
                file_name = os.path.basename(largeImageURL)
                large_ok = False
                small_ok = False

                try:
                    resp = requests.get(largeImageURL, timeout=20)
                    resp.raise_for_status()
                    default_storage.save(os.path.join('original', file_name), ContentFile(resp.content))
                    large_ok = True
                except requests.exceptions.RequestException:
                    pass

                try:
                    resp = requests.get(img.smallImageURL, timeout=20)
                    resp.raise_for_status()
                    default_storage.save(os.path.join('small', file_name), ContentFile(resp.content))
                    small_ok = True
                except requests.exceptions.RequestException:
                    pass

                if not large_ok and not small_ok:
                    img.status = 'FAILED_DOWNLOADED'
                    img.save(update_fields=['status'])
                    errors.append(f"Descarga fallida para {filename}")
                    continue

                img.status = 'DOWNLOADED'
                img.save(update_fields=['status'])

                for _ in range(img.replicas):
                    GeoAttempt.objects.create(image=img, status='PENDING')

                img.status = 'DOWNLOADED_GENERATED'
                img.save(update_fields=['status'])
                images_ready += 1

            except Exception as e:
                errors.append(f"{filename if 'filename' in dir() else '?'}: {str(e)}")
                continue

    except Exception as e:
        log_error(f"[{idx}/{total}] Error general procesando {image_name}: {str(e)}")

    # Single summary log entry written after everything (API + download + GeoAttempts) is done
    status = 'OK' if images_ready > 0 else 'SIN RESULTADOS'
    log_info(f"[{idx}/{total}] '{image_name}': {images_ready} imagen(es) lista(s) — {status}")
    for err in errors:
        log_error(f"[{idx}/{total}] {err}")

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


