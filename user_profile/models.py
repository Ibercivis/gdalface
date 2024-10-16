from django.db import models
from django.contrib.auth.models import User

# Create your models here.

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(blank=True)
    profile_pic = models.ImageField(upload_to='profile_pics', blank=True)
    geoattempts_done = models.IntegerField(default=0)
    time_spent = models.PositiveBigIntegerField(default=0)
    cheating = models.IntegerField(default=0)
    controlPointsDone = models.PositiveBigIntegerField(default=0)

    def __str__(self):
        return self.user.username
