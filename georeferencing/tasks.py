from .models import GeoAttempt
from datetime import timedelta
from django.utils import timezone

def update_assigned():
    """
    update_assigned is a Django Q task that updates the status of GeoAttempts that have been assigned but not finished.
    I want to check assigned GeoAttempts that assignedDateTime is more than 24 hours ago and update their status to PENDING.
    """
    print("Updating assigned GeoAttempts")
    GeoAttempt.objects.filter(status='ASSIGNED', assignedDateTime__lt=timezone.now()-timedelta(hours=24)).update(status='PENDING')
   

