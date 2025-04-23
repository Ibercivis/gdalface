import os
import requests
from decouple import config
from .models import GeoAttempt, Image
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django_rq import job

@job('default')  # Specify the queue (default, high, low) here
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


@job('default')  # Specify the queue (default, high, low) here
def download_image(image):
    """
    download_image is an RQ task that downloads an image from a given URL and stores it in the 'media/original/' folder.
    """
    try:
        url = image.largeImageURL
        file_name = os.path.basename(image.largeImageURL)

        # Send an HTTP GET request to download the large image
        try:
            response = requests.get(image.largeImageURL, timeout=20)
            response.raise_for_status()  # Raise an exception for any HTTP errors
        
            # Create the path where the image will be saved
            file_path = os.path.join('original', file_name)

            # Save the image to the media/original/ folder
            saved_path = default_storage.save(file_path, ContentFile(response.content))
            full_saved_path = os.path.join(settings.MEDIA_ROOT, saved_path)
        except requests.exceptions.RequestException as e:
            # Continue with small image even if large image fails
            pass

        # Send an HTTP GET request to download the small image
        try:
            response = requests.get(image.smallImageURL, timeout=20)
            response.raise_for_status()  # Raise an exception for any HTTP errors
        
            # Create the path where the image will be saved
            file_path = os.path.join('small', file_name)

            # Save the image to the media/original/ folder
            saved_path = default_storage.save(file_path, ContentFile(response.content))
            full_saved_path = os.path.join(settings.MEDIA_ROOT, saved_path)
        except requests.exceptions.RequestException as e:
            # Continue even if small image fails
            pass
        
        # Create GeoAttempts regardless of download success
        try:
            # It downloaded the image successfully, so we can create the geoattempts
            # as many as the number of replicas of the image
            for _ in range(image.replicas):
                geoattemp = GeoAttempt.objects.create(
                    image = image,
                    status = 'PENDING'
                )
            geoattemp.save()
        except Exception as e:
            # Fail silently if there's a problem creating GeoAttempts
            pass
            
    except Exception as e:
        # Catch any other unexpected errors
        return None

@job('default')  # Specify the queue (default, high, low) here
def generate_from_list(batch):
    """
    generate_from_list is a function that takes a list of Image objects and generates GeoAttempts for each image.
    """
    # Actualizar el estado del batch a 'PROCESSING' y guardar la hora de inicio
    batch.processing_status = 'PROCESSING'
    batch.processing_start_time = timezone.now()
    batch.save(update_fields=['processing_status', 'processing_start_time'])
    
    # Función auxiliar para registrar información en el log del batch
    def add_log_info(message):
        timestamp = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
        batch.log = (batch.log or "") + f"\n[II] {timestamp} - {message}"
        batch.save(update_fields=['log'])
    
    # Función auxiliar para registrar errores en el log del batch
    def add_log_error(message):
        timestamp = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
        batch.log = (batch.log or "") + f"\n[EE] {timestamp} - {message}"
        batch.save(update_fields=['log'])
    
    # Contador de imágenes creadas
    total_images_created = 0
    
    try:
        key = config('NASA_API_KEY')
        add_log_info(f"====== INICIO DEL PROCESAMIENTO DEL BATCH ====")
        add_log_info(f"Iniciando procesamiento del batch '{batch.name}' con {len(batch.originalImages.split(','))} imágenes")
        
        # We iterate over the list of images, separated by commas
        for image in batch.originalImages.split(','):
            try:
                add_log_info(f"Procesando imagen: {image}")
                
                # Construir URL para la consulta a la API de la NASA
                base_url = 'https://eol.jsc.nasa.gov/SearchPhotos/PhotosDatabaseAPI/PhotosDatabaseAPI.pl'
                params = {
                    'query': f'images|directory|like|*large*|images|filename|like|*{image}*',
                    'return': 'images|directory|images|filename|nadir|lat|nadir|lon|nadir|elev|nadir|azi|camera|fclt|',
                    'key': key
                }
                url_request = f"{base_url}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
                add_log_info(f"Consultando API para {image}")

                try:
                    response = requests.get(url_request, timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        add_log_info(f"Respuesta API exitosa. Datos recibidos: {len(data) if isinstance(data, list) else 'Object'}")
                        
                        # Check if the query returned no records
                        if isinstance(data, dict) and data.get('result') == 'SQL found no records that match the specified criteria':
                            add_log_error(f"No se encontraron registros para {image}")
                            continue
                        # También verificamos si la lista está vacía
                        if isinstance(data, list) and len(data) == 0:
                            add_log_error(f"Lista de resultados vacía para {image}")
                            continue
                        
                        # Variable para almacenar todas las imágenes creadas en este batch
                        created_images = []
                        
                        for d in data:
                            try:
                                filename = d['images.filename']
                                add_log_info(f"Procesando imagen encontrada: {filename}")
                                
                                largeImageURL = (
                                    f"https://eol.jsc.nasa.gov/DatabaseImages/"
                                    f"{d['images.directory']}/{filename}"
                                )
                                
                                # Creamos url_request2 para obtener frames|lat y frames|lon para el PhotoCenterPoint
                                url_request2 = (
                                    f'{base_url}?query=images|directory|like|*large*|images|filename|like|*{filename}*'
                                    f'&return=frames|lat|frames|lon&key={key}'
                                )
                                
                                url_request3 = (
                                    f'{base_url}?query=images|directory|like|*large*|images|filename|like|*{filename}*'
                                    f'&return=mlcoord|lat|mlcoord|lon&key={key}'
                                )
                                
                                # Consultar frames|lat y frames|lon para PhotoCenterPoint
                                try:
                                    add_log_info(f"Consultando coordenadas del centro (frames) para {filename}")
                                    response2 = requests.get(url_request2, timeout=10)
                                    frames_center = None
                                    if response2.status_code == 200:
                                        frames_center_data = response2.json()
                                        
                                        # Verificar si hay datos válidos
                                        if isinstance(frames_center_data, list) and len(frames_center_data) > 0:
                                            # Obtener las coordenadas del centro desde la tabla frames
                                            frames_lat = frames_center_data[0].get('frames.lat')
                                            frames_lon = frames_center_data[0].get('frames.lon')
                                            
                                            if frames_lat is not None and frames_lon is not None:
                                                frames_center = f"{frames_lat}, {frames_lon}"
                                                add_log_info(f"Coordenadas centro (frames) encontradas: {frames_center}")
                                            else:
                                                add_log_error(f"Coordenadas centro (frames) incompletas para {filename}")
                                        else:
                                            add_log_error(f"No se encontraron datos de centro (frames) para {filename}")
                                    else:
                                        add_log_error(f"Error consultando coordenadas centro (código: {response2.status_code})")
                                    
                                except requests.exceptions.RequestException as e:
                                    add_log_error(f"Error de red consultando centro (frames): {str(e)}")
                                    frames_center = None
                                
                                # Consultar las coordenadas del center point by machine learning mlcoord|lat y mlcoord|lon de la API
                                try:
                                    add_log_info(f"Consultando coordenadas ML para {filename}")
                                    response3 = requests.get(url_request3, timeout=10)
                                    ml_coords = None
                                    if response3.status_code == 200:
                                        ml_data = response3.json()
                                        
                                        # Verificar si hay datos válidos
                                        if isinstance(ml_data, list) and len(ml_data) > 0:
                                            # Obtener las coordenadas de machine learning
                                            ml_lat = ml_data[0].get('mlcoord.lat')
                                            ml_lon = ml_data[0].get('mlcoord.lon')
                                            
                                            if ml_lat is not None and ml_lon is not None:
                                                ml_coords = f"{ml_lat}, {ml_lon}"
                                                add_log_info(f"Coordenadas ML encontradas: {ml_coords}")
                                            else:
                                                add_log_error(f"Coordenadas ML incompletas para {filename}")
                                        else:
                                            add_log_error(f"No se encontraron datos de ML para {filename}")
                                    else:
                                        add_log_error(f"Error consultando coordenadas ML (código: {response3.status_code})")
                                except requests.exceptions.RequestException as e:
                                    add_log_error(f"Error de red consultando ML: {str(e)}")
                                    ml_coords = None
                                
                                # We create the image object
                                try:
                                    img = Image.objects.create(
                                        name = filename,
                                        taken = timezone.now(),
                                        focalLength = d.get('camera.fclt', 0),  # Proporcionar valor predeterminado
                                        spacecraftNadirPoint = f"{d.get('nadir.lat', 0)}, {d.get('nadir.lon', 0)}",  # Valores predeterminados
                                        spaceCraftAltitude = d.get('nadir.elev', 0),  # Valor predeterminado
                                        # Usar frames_center para photoCenterPoint si está disponible
                                        photoCenterPoint = frames_center,
                                        photoCenterByMachineLearning = ml_coords,  # Añadir las coordenadas ML
                                        largeImageURL = largeImageURL,
                                        # SmallImageURL  is the same as largeImageURL, but small instead of large
                                        smallImageURL = largeImageURL.replace('large', 'small'),
                                        batch = batch,
                                        replicas = batch.replicas
                                    )
                                    
                                    created_images.append(img)
                                    total_images_created += 1  # Incrementar contador de imágenes
                                    add_log_info(f"Imagen creada: {filename}")
                                except Exception as e:
                                    add_log_error(f"Error creando objeto Image para {filename}: {str(e)}")
                                    # Si falla la creación de una imagen, continuamos con la siguiente
                                    continue
                            except Exception as e:
                                add_log_error(f"Error procesando datos: {str(e)}")
                                # Si falla el procesamiento de un dato, continuamos con el siguiente
                                continue

                        # Procesar la descarga de cada imagen creada
                        add_log_info(f"Programando descarga para {len(created_images)} imágenes")
                        for img in created_images:
                            try:
                                # We download the image
                                download_image.delay(img)
                                add_log_info(f"Descarga programada para: {img.name}")
                            except Exception as e:
                                add_log_error(f"Error programando descarga de {img.name}: {str(e)}")
                                # Si falla la programación de la descarga, continuamos con la siguiente imagen
                                continue
                    else:
                        add_log_error(f"La API respondió con código de error: {response.status_code}")
                except requests.exceptions.RequestException as e:
                    add_log_error(f"Error de conexión con la API: {str(e)}")
                    # Si falla la consulta principal a la API, continuamos con la siguiente imagen
                    continue
            except Exception as e:
                add_log_error(f"Error general procesando {image}: {str(e)}")
                # Si falla el procesamiento completo de una imagen, continuamos con la siguiente
                continue
        
        # Actualizar el número de imágenes en el batch
        batch.numberImages += total_images_created
        batch.save(update_fields=['numberImages'])
        add_log_info(f"Procesamiento del batch '{batch.name}' completado. Total de imágenes creadas: {total_images_created}")
        
        # Actualizar el estado del batch a 'COMPLETED' y guardar la hora de finalización
        batch.processing_status = 'COMPLETED'
        batch.processing_end_time = timezone.now()
        batch.save(update_fields=['processing_status', 'processing_end_time'])
        
    except Exception as e:
        add_log_error(f"Error fatal en el procesamiento del batch: {str(e)}")
        # Asegurarse de actualizar el número de imágenes incluso en caso de error
        if total_images_created > 0:
            batch.numberImages += total_images_created
            batch.save(update_fields=['numberImages'])
            
        # Marcar el batch como fallido
        batch.processing_status = 'FAILED'
        batch.processing_end_time = timezone.now()
        batch.save(update_fields=['processing_status', 'processing_end_time'])
        
        # Manejamos cualquier excepción no prevista
        return None
    
    return True


