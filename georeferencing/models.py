from django.db import models
import hashlib
import uuid
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
    
class GeoAttempt(models.Model):

    STATUS_CHOICES = (
        ('PENDING', _('Pending')),
        ('ASSIGNED', _('Assigned')),
        ('DONE', _('Done')),
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

    IMAGE_STATUS_CHOICES = (
        ('PENDING',              _('Pending download')),
        ('DOWNLOADED',           _('Downloaded')),
        ('FAILED_DOWNLOADED',    _('Failed download')),
        ('DOWNLOADED_GENERATED', _('Downloaded & Generated')),
    )

    name = models.CharField(max_length=100)
    status = models.CharField(
        max_length=30,
        choices=IMAGE_STATUS_CHOICES,
        default='PENDING',
    )
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
    
    def save(self, *args, **kwargs):
        print(self.focalLength)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return str(self.name)
    

    

class Batch(models.Model):
    BATCH_CHOICES = (
        ('SEARCH', _('Search')),
        ('LIST', _('List')),
    )

    PROCESSING_STATUS_CHOICES = (
        ('NOT_STARTED', _('Not Started')),
        ('PROCESSING', _('Processing')),
        ('COMPLETED', _('Completed')),
        ('FAILED', _('Failed')),
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
    fcltle = models.IntegerField(blank = True, null = True, verbose_name=_("Focal length <="))
    fcltge = models.IntegerField(blank = True, null = True, verbose_name=_("Focal length >="))
    originalImages = models.TextField(blank = True, null = True, verbose_name=_("Original images"))
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    result = models.JSONField(default=dict, blank=True, null=True)
    numberImages = models.IntegerField(default=0)
    replicas = models.IntegerField(default=5)
    log = models.TextField(blank = True, null = True)

    processing_status = models.CharField(
        max_length=20,
        choices = PROCESSING_STATUS_CHOICES,
        default = 'NOT_STARTED',
        verbose_name=_("Processing Status")
    )
    processing_start_time = models.DateTimeField(blank=True, null=True)
    processing_end_time = models.DateTimeField(blank=True, null=True)
    total_images_in_queue = models.IntegerField(default=0)
    processed_images_in_queue = models.IntegerField(default=0)
    
    def __str__(self):
        return str(self.name)
    
    def get_example_image(self):
        image = Image.objects.filter(batch=self).first()
        return f"/media/small/{image.name}" if image else "/media/small/default.jpg"
    
    def get_number_images(self):
        return Image.objects.filter(batch=self).count()

    def get_number_geoattempts(self):
        return GeoAttempt.objects.filter(image__batch=self).count()
    
    def get_percentage_remaining(self):
        geoattemps_created = GeoAttempt.objects.filter(image__batch=self).count()
        geoattemps_done = GeoAttempt.objects.filter(image__batch=self, status='DONE').count()
        return round(geoattemps_done / geoattemps_created * 100) if geoattemps_created > 0 else 0
    
class Expedition(models.Model):
    number = models.IntegerField(unique=True)
    crew = models.JSONField(default=list)  # list of astronaut name strings

    def __str__(self):
        return f"Expedition {self.number}"


class GeoAttemptsByUserByDay(models.Model):
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    date = models.DateField()
    numberGeoAttempts = models.IntegerField(default=0)

    def __str__(self):
        return str(self.user) +  " - " + str(self.date) + " - " + str(self.numberGeoAttempts)


class Challenge(models.Model):
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    batch = models.ForeignKey(
        'Batch', on_delete=models.SET_NULL, blank=True, null=True,
        related_name='challenges',
        help_text=_('Leave empty for a general challenge applicable to any batch.'),
    )
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    target_bronze = models.PositiveIntegerField(default=1000)
    target_silver = models.PositiveIntegerField(default=2000)
    target_gold = models.PositiveIntegerField(default=3000)
    is_paused = models.BooleanField(default=False)
    paused_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        get_user_model(), on_delete=models.SET_NULL,
        blank=True, null=True, related_name='created_challenges',
    )

    class Meta:
        ordering = ['-start_at']
        constraints = [
            models.CheckConstraint(
                check=models.Q(start_at__lt=models.F('end_at')),
                name='challenge_start_before_end',
            ),
            models.CheckConstraint(
                check=(
                    models.Q(target_bronze__lte=models.F('target_silver'))
                    & models.Q(target_silver__lte=models.F('target_gold'))
                ),
                name='challenge_targets_ordered',
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def status(self):
        from django.utils import timezone
        now = timezone.now()
        if self.is_paused:
            return 'paused'
        if now < self.start_at:
            return 'upcoming'
        if now >= self.end_at:
            return 'finished'
        return 'active'

    def is_open_for_submissions(self):
        return self.status == 'active'

    def total_cp(self):
        return self.participants.aggregate(
            total=models.Sum('cached_cp_count'),
        )['total'] or 0


class ChallengeParticipant(models.Model):
    challenge = models.ForeignKey(
        Challenge, on_delete=models.CASCADE, related_name='participants',
    )
    user = models.ForeignKey(
        get_user_model(), on_delete=models.CASCADE,
        related_name='challenge_participations',
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(blank=True, null=True)
    cached_cp_count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['challenge', 'user'],
                name='unique_participant_per_challenge',
            ),
            # At most one active enrollment per user across all challenges.
            models.UniqueConstraint(
                fields=['user'],
                condition=models.Q(left_at__isnull=True),
                name='one_active_challenge_per_user',
            ),
        ]
        indexes = [
            models.Index(fields=['challenge', '-cached_cp_count']),
        ]

    @property
    def is_active(self):
        return self.left_at is None

    def __str__(self):
        state = 'left' if self.left_at else 'active'
        return f'{self.user} -> {self.challenge} ({state}, {self.cached_cp_count} cp)'


class TutorialEvent(models.Model):
    EVENT_CHOICES = (
        ('started', _('Started')),
        ('step', _('Step')),
        ('completed', _('Completed')),
        ('dismissed', _('Dismissed')),
    )

    user = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, blank=True, null=True)
    session_key = models.CharField(max_length=40, blank=True)
    event = models.CharField(max_length=20, choices=EVENT_CHOICES)
    step = models.PositiveSmallIntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['event', 'created_at']),
        ]

    def __str__(self):
        who = self.user.username if self.user else f"anon:{self.session_key[:8]}"
        return f"{who} - {self.event}{f' #{self.step}' if self.step is not None else ''} - {self.created_at:%Y-%m-%d %H:%M}"
