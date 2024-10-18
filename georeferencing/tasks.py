import os
import requests
from .models import GeoAttempt
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

        print(f"Image downloaded and saved to: {full_saved_path}")
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

