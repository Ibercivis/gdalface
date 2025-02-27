from django.db import models
import hashlib
import uuid
from django.contrib.auth import get_user_model
    
class GeoAttempt(models.Model):

    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('ASSIGNED', 'Assigned'),
        ('DONE', 'Done'),
    )

 
    
    image = models.ForeignKey('Image', on_delete=models.CASCADE)
    assignedUser = models.ForeignKey(get_user_model(), on_delete=models.DO_NOTHING, blank=True, null=True)
    createdDateTime = models.DateTimeField(auto_now_add=True)
    assignedDateTime = models.DateTimeField(blank=True, null=True)
    finishedDateTime = models.DateTimeField(blank=True, null=True)
    numberTries = models.IntegerField(default=0)
    hash = models.CharField(
        max_length=100,
        blank=True,
        unique=True,) 
    status = models.CharField(
        max_length=10,
        choices = STATUS_CHOICES,
        default = 'PENDING')
    skipped = models.IntegerField(default=0)
    controlPoints = models.JSONField(default=dict, blank=True, null=True)

    
    def save(self, *args, **kwargs):
        if not self.hash:
            self.hash = hashlib.md5(str(uuid.uuid4()).encode()).hexdigest()
        super(GeoAttempt, self).save(*args, **kwargs)

    def elapsedTime(self):
        if self.finishedDateTime and self.createdDateTime:
            return self.finishedDateTime - self.createdDateTime
        else:
            return None

    def __str__(self):
        return str(self.image.name) + " - " + str(self.createdDateTime) + " - " + str(self.status)

    
class Image(models.Model):
    name = models.CharField(max_length=100)
    taken = models.DateTimeField(blank=True, null=True)
    createdDateTime = models.DateTimeField(auto_now_add=True, blank = True, null = True)
    camera = models.CharField(max_length=100, blank = True, null = True)
    focalLength = models.IntegerField(blank = True, null = True)
    cameraTilt = models.IntegerField(blank = True, null = True)
    spacecraftNadirPoint = models.CharField(max_length=100, blank = True, null = True)
    photoCenterPoint = models.CharField(max_length=100, blank = True, null = True)
    photoCenterByMachineLearning = models.CharField(max_length=100, blank = True, null = True)
    spaceCraftAltitude = models.IntegerField( blank = True, null = True)
    link = models.URLField( blank = True, null = True)
    largeImageURL = models.URLField( blank = True, null = True)
    smallImageURL = models.URLField( blank = True, null = True)
    batch = models.ForeignKey('Batch', on_delete=models.CASCADE, blank=True, null=True)
    replicas = models.IntegerField(default=5)
    maxZoom = models.IntegerField(blank=True, null=True)
    minZoom = models.IntegerField(blank=True, null=True)
    
    def save(self, *args, **kwargs):
        print(self.focalLength)
        if self.focalLength is not None:
            self.minZoom, self.maxZoom = self.get_zoom_levels()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return str(self.name)
    

    

class Batch(models.Model):
    BATCH_CHOICES = (
        ('SEARCH', 'Search'),
        ('LIST', 'List'),
    )

    name = models.CharField(max_length=100)
    createdDateTime = models.DateTimeField(auto_now_add=True)
    type = models.CharField(
        max_length=20,
        choices = BATCH_CHOICES,
        default = 'SEARCH')
    # Search fields
    feat = models.CharField(max_length=100, blank = True, null = True)
    mission = models.CharField(max_length=100, blank = True, null = True)
    fcltle = models.IntegerField(blank = True, null = True, verbose_name="Focal length <=")
    fcltge = models.IntegerField(blank = True, null = True, verbose_name="Focal length >=")
    originalImages = models.TextField(blank = True, null = True, verbose_name="Original images")
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    result = models.JSONField(default=dict, blank=True, null=True)
    numberImages = models.IntegerField(default=0)
    replicas = models.IntegerField(default=5)
    def __str__(self):
        return str(self.name)
