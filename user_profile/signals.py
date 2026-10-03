"""
This module contains the signals for the user_profile app.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import UserProfile

User = get_user_model()

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Signal to create a UserProfile instance when a new User is created.
    
    Args:
        sender: The model class that sent the signal.
        instance: The actual instance being saved.
        created: Boolean; True if a new record was created.
        **kwargs: Additional keyword arguments.
    """
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """
    Ensure a UserProfile exists whenever a User is saved.

    Deliberately does NOT re-save instance.userprofile: that cached copy can
    be stale, and re-saving it on every User.save() (e.g. the last_login
    update at login) silently overwrites counters/fields written by other
    processes in the meantime.
    """
    UserProfile.objects.get_or_create(user=instance)