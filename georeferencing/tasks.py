from .models import GeoAttempt
from datetime import timedelta
from django.utils import timezone
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