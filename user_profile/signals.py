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
    Signal to save the UserProfile instance when the User is saved.
    
    Args:
        sender: The model class that sent the signal.
        instance: The actual instance being saved.
        **kwargs: Additional keyword arguments.
    """
    # Aseguramos que el perfil existe antes de guardarlo
    try:
        instance.userprofile.save()
    except UserProfile.DoesNotExist:
        # Si el perfil no existe, lo creamos
        UserProfile.objects.create(user=instance)