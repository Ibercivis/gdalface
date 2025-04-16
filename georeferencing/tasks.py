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
    print("Updating assigned GeoAttempts")
    GeoAttempt.objects.filter(
        status='ASSIGNED', 
        assignedDateTime__lt=timezone.now() - timedelta(hours=24)
    ).update(status='PENDING')


@job('default')  # Specify the queue (default, high, low) here
def download_image(image):
    """
    download_image is an RQ task that downloads an image from a given URL and stores it in the 'media/original/' folder.
    """
    try:
        url = image.largeImageURL
        print(f"Downloading image from {url}")
        # Get the image file name from the URL
        file_name = os.path.basename(image.largeImageURL)

        # Send an HTTP GET request to download the image
        try:
            response = requests.get(image.largeImageURL, timeout=20)
            response.raise_for_status()  # Raise an exception for any HTTP errors
        except requests.exceptions.RequestException as e:
            print(f"Failed to download image from {image.largeImageURL}: {e}")
            return None # TODO: Handle the error
        # Create the path where the image will be saved
        file_path = os.path.join('original', file_name)

        # Save the image to the media/original/ folder
        saved_path = default_storage.save(file_path, ContentFile(response.content))
        
        full_saved_path = os.path.join(settings.MEDIA_ROOT, saved_path)
        print(f"Large image downloaded and saved to: {full_saved_path}")

        # Send an HTTP GET request to download the small image
        try:
            response = requests.get(image.smallImageURL, timeout=20)
            response.raise_for_status()  # Raise an exception for any HTTP errors
        except requests.exceptions.RequestException as e:
            print(f"Failed to download image from {image.smallImageURL}: {e}")
            return None # TODO: Handle the error
        # Create the path where the image will be saved
        file_path = os.path.join('small', file_name)

         # Save the image to the media/original/ folder
        saved_path = default_storage.save(file_path, ContentFile(response.content))
        full_saved_path = os.path.join(settings.MEDIA_ROOT, saved_path)
        print(f"Small image downloaded and saved to: {full_saved_path}")
    except requests.exceptions.RequestException as e:
        print(f"Failed to download image from {image.largeImageURL}: {e}")
        return None
    
    # It downloaded the image successfully, so we can create the geoattempts
    # as many as the number of replicas of the image
    for _ in range(image.replicas):
        geoattemp = GeoAttempt.objects.create(
            image = image,
            status = 'PENDING'
        )
        print(f"GeoAttempt created for image {image}: {geoattemp.id}")
    geoattemp.save()

@job('default')  # Specify the queue (default, high, low) here
def generate_from_list(batch):
    """
    generate_from_list is a function that takes a list of Image objects and generates GeoAttempts for each image.
    """
    key = config('NASA_API_KEY')
    # We iterate over the list of images, separated by commas
    for image in batch.originalImages.split(','):
        print(f"Generating from list: {image}")
        # We do the query to the API for each image
        url = 'https://eol.jsc.nasa.gov/SearchPhotos/PhotosDatabaseAPI/PhotosDatabaseAPI.pl'
        query = 'query=images|directory|like|*large*'
        query = f'{query}|images|filename|like|*{image}*'
        url_request = (
            f'{url}?{query}&return=images|directory|images|filename|'
            f'nadir|lat|nadir|lon|nadir|elev|nadir|azi|camera|fclt'
            f'&key={key}'
        )

        # We do another query to get entries on the mlfeatures table
        # that match the image name
        url_request2 = (
            f'{url}?{query}&return=mlfeat|feat'
            f'&key={key}'
        )
        url_request3 = (
            f'{url}?{query}&return=mlcoord|lat|mlcoord|lon'
            f'&key={key}'
        )
        print(url_request)
        print(url_request2)
        print(url_request3)
        try:
            response = requests.get(url_request, timeout=10)
            print(response)
            if response.status_code == 200:
                data = response.json()
                print(f"Query successful: {data}")
                print(f"Data type: {type(data)}") 
                 # Check if the query returned no records
                if data.get('result') == 'SQL found no records that match the specified criteria':
                    print(f"No records found for image")
                    return None
                for d in data:

                    largeImageURL = (
                        f"https://eol.jsc.nasa.gov/DatabaseImages/"
                        f"{d['images.directory']}/{d['images.filename']}"
                    )
                    
                    # We create the image object
                    image = Image.objects.create(
                        name = d['images.filename'],
                        taken = timezone.now(),
                        focalLength = d['camera.fclt'],
                        spacecraftNadirPoint = f"{d['nadir.lat']}, {d['nadir.lon']}",
                        spaceCraftAltitude = d['nadir.elev'],
                        largeImageURL = largeImageURL,
                        # SmallImageURL  is the same as largeImageURL, but small instead of large
                        smallImageURL = largeImageURL.replace('large', 'small'),
                        batch = batch,
                        replicas = batch.replicas
                        
                    )
                print(f"Image created: {image.name}")
                # We download the image
                download_image.delay(image)
            else:
                print(f"Failed to query image: {image}")
        except requests.exceptions.RequestException as e:
            print(f"Failed to query image: {image}: {e}")
            return None
        

