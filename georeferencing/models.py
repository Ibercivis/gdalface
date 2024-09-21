from django.db import models
import hashlib
import uuid
from django.contrib.auth.models import User

# Create your models here.
class Controlpoint(models.Model):

    x = models.FloatField()
    y = models.FloatField()
    lat = models.FloatField()
    long = models.FloatField()
    created = models.DateTimeField(auto_now_add=True)
    geoAttempt = models.ForeignKey(
        'GeoAttempt',
        on_delete=models.CASCADE,
        null=True,)

    def __str__(self):
        return str(self.geoAttempt.image.name) + " - " + str(self.x) + " - " + str(self.y)
    
class GeoAttempt(models.Model):

    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('DOING', 'Doing'),
        ('SUCCESS', 'Success'),
        ('FAILURE', 'Failure'),
    )
    created = models.DateTimeField(auto_now_add=True)
    image = models.ForeignKey('Image', on_delete=models.CASCADE)
    hash = models.CharField(
        max_length=100,
        blank=True,
        unique=True,) 
    status = models.CharField(
        max_length=10,
        choices = STATUS_CHOICES,
        default = 'PENDING')
    
    def save(self, *args, **kwargs):
        if not self.hash:
            self.hash = hashlib.md5(str(uuid.uuid4()).encode()).hexdigest()
        super(GeoAttempt, self).save(*args, **kwargs)

    def __str__(self):
        return str(self.image.name) + " - " + str(self.created) + " - " + str(self.status)

    
class Image(models.Model):
    name = models.CharField(max_length=100)
    taken = models.DateTimeField(blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True, blank = True, null = True)
    camera = models.CharField(max_length=100, blank = True, null = True)
    focalLength = models.IntegerField(blank = True, null = True)
    cameraTilt = models.IntegerField(blank = True, null = True)
    spacecraftNadirPoint = models.CharField(max_length=100, blank = True, null = True)
    photoCenterPoint = models.CharField(max_length=100, blank = True, null = True)
    photoCenterByMachineLearning = models.CharField(max_length=100, blank = True, null = True)
    spaceCraftAltitude = models.IntegerField( blank = True, null = True)
    link = models.URLField( blank = True, null = True)
    def __str__(self):
        return self.name
