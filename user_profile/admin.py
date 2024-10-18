"""
This module registers the UserProfile model with the Django admin site.

Imports:
    admin (django.contrib.admin): The Django admin module.
    UserProfile (user_profile.models): The UserProfile model
    from the current package.

Registration:
    The UserProfile model is registered with the Django admin 
    site to enable its management through the admin interface.
"""
from django.contrib import admin
from .models import UserProfile

# Register your models here.
register = admin.site.register(UserProfile)
