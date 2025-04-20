"""
Models for the user_profile app.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django_countries.fields import CountryField

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
        - country (CountryField): The country of the user, optional.
        - location (CharField): The city of the user, optional.
        - visible (BooleanField): Whether the user profile should be visible in rankings, defaults to True.

    Methods:
        __str__(): Returns the username of the associated user.
    """
    user = models.OneToOneField(get_user_model(), on_delete=models.CASCADE)
    bio = models.TextField(blank=True)
    profile_pic = models.ImageField(upload_to='profile_pics', blank=True)
    geoattempts_done = models.IntegerField(default=0)
    time_spent = models.PositiveBigIntegerField(default=0)
    cheating = models.IntegerField(default=0)
    controlPointsDone = models.PositiveBigIntegerField(default=0)
    country = CountryField(blank=True, null=True, verbose_name="Country")
    location = models.CharField(max_length=100, blank=True, verbose_name="City")
    visible = models.BooleanField(default=True, verbose_name="Visible in rankings", help_text="If disabled, your profile will not appear in public rankings")

    def __str__(self):
        return str(self.user.email) # pylint: disable=no-member
