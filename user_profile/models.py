"""
Models for the user_profile app.
"""

from django.db import models
from django.contrib.auth.models import User

# Create your models here.

class UserProfile(models.Model):
    """
    UserProfile model represents the profile information of a user.

    Attributes:
        - user (OneToOneField): A one-to-one relationship 
        with the User model.
        - bio (TextField): A brief biography of the user,
        optional.
        - profile_pic (ImageField): An optional profile 
        picture of the user, stored in 'profile_pics' directory.
        - geoattempts_done (IntegerField): The number of geographical 
        attempts completed by the user, defaults to 0.
        - time_spent (PositiveBigIntegerField): The total time spent 
        by the user in seconds , defaults to 0.
        - cheating (IntegerField): A flag indicating if the user has 
        cheated, defaults to 0.
        - controlPointsDone (PositiveBigIntegerField): The number of 
        control points completed by the user, defaults to 0.

    Methods:
        __str__(): Returns the username of the associated user.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(blank=True)
    profile_pic = models.ImageField(upload_to='profile_pics', blank=True)
    geoattempts_done = models.IntegerField(default=0)
    time_spent = models.PositiveBigIntegerField(default=0)
    cheating = models.IntegerField(default=0)
    controlPointsDone = models.PositiveBigIntegerField(default=0)

    def __str__(self):
        return self.user.email
