from django.db import models
from django.utils import timezone
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
    assignedUser = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, blank=True, null=True)
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
    # Numeric copies of the best available "centre" coords used for spatial
    # filters (e.g. challenge bounding-box). Populated by save() and the
    # backfill_image_coords management command, with priority:
    # photoCenterPoint > photoCenterByMachineLearning > spacecraftNadirPoint.
    photoCenterLat = models.FloatField(blank=True, null=True, db_index=True)
    photoCenterLon = models.FloatField(blank=True, null=True, db_index=True)
    spaceCraftAltitude = models.IntegerField( blank = True, null = True)
    link = models.URLField( blank = True, null = True)
    largeImageURL = models.URLField( blank = True, null = True)
    smallImageURL = models.URLField( blank = True, null = True)
    batch = models.ForeignKey('Batch', on_delete=models.CASCADE, blank=True, null=True)
    replicas = models.IntegerField(default=5)

    @staticmethod
    def parse_latlon(s):
        """Parse a 'lat,lon' string into (float, float) or None on failure."""
        if not s:
            return None
        try:
            parts = [p.strip() for p in str(s).split(',')]
            if len(parts) < 2:
                return None
            lat = float(parts[0])
            lon = float(parts[1])
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                return None
            return (lat, lon)
        except (ValueError, TypeError):
            return None

    def best_center(self):
        """Return (lat, lon) using priority chain, or None."""
        for src in (self.photoCenterPoint,
                    self.photoCenterByMachineLearning,
                    self.spacecraftNadirPoint):
            parsed = self.parse_latlon(src)
            if parsed is not None:
                return parsed
        return None

    def save(self, *args, **kwargs):
        # Recompute numeric centre on every save so newly-added images
        # don't need the backfill command.
        center = self.best_center()
        if center is not None:
            self.photoCenterLat, self.photoCenterLon = center
        else:
            self.photoCenterLat = None
            self.photoCenterLon = None
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
    
    def get_percentage_done(self):
        """% of this batch's tasks already DONE (was misnamed get_percentage_remaining)."""
        geoattemps_created = GeoAttempt.objects.filter(image__batch=self).count()
        geoattemps_done = GeoAttempt.objects.filter(image__batch=self, status='DONE').count()
        return round(geoattemps_done / geoattemps_created * 100) if geoattemps_created > 0 else 0
    
class Expedition(models.Model):
    number = models.IntegerField(unique=True)
    crew = models.JSONField(default=list)  # list of astronaut name strings

    def __str__(self):
        return f"Expedition {self.number}"


class GeoAttemptsByUserByDay(models.Model):
    """Per-user daily activity. Feeds streaks, the heatmap and the rolling
    7/30-day rankings. Rebuilt from GeoAttempt DONE rows by reconcile_counters."""
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    date = models.DateField(db_index=True)
    numberGeoAttempts = models.IntegerField(default=0)
    controlPoints = models.IntegerField(default=0)
    seconds = models.IntegerField(default=0)

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

    # Optional spatial bounding-box filter. When set, only images whose
    # photoCenterLat/Lon fall inside the rectangle count towards the
    # challenge. Antimeridian-aware: if min_lon > max_lon the box wraps.
    bbox_min_lat = models.FloatField(blank=True, null=True)
    bbox_max_lat = models.FloatField(blank=True, null=True)
    bbox_min_lon = models.FloatField(blank=True, null=True)
    bbox_max_lon = models.FloatField(blank=True, null=True)

    # Cached counts of images / tasks that match (batch ∩ bbox). Refreshed
    # on save() and via the "Recompute counts" admin action. Stale if new
    # images are added to the batch after the challenge is saved.
    cached_image_count = models.PositiveIntegerField(default=0)
    cached_task_count  = models.PositiveIntegerField(default=0)

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

    # ── Bounding-box helpers ───────────────────────────────────────────
    @property
    def has_bbox(self):
        return None not in (
            self.bbox_min_lat, self.bbox_max_lat,
            self.bbox_min_lon, self.bbox_max_lon,
        )

    def bbox_filter_q(self, lat_field='photoCenterLat', lon_field='photoCenterLon'):
        """
        Return a Q filtering Image (or related) rows whose lat/lon fall
        inside the challenge's bbox. Returns Q() (no-op) if no bbox.
        Antimeridian-aware: if min_lon > max_lon, the bbox wraps.
        """
        if not self.has_bbox:
            return models.Q()
        lat_q = models.Q(**{f'{lat_field}__gte': self.bbox_min_lat,
                            f'{lat_field}__lte': self.bbox_max_lat})
        if self.bbox_min_lon <= self.bbox_max_lon:
            lon_q = models.Q(**{f'{lon_field}__gte': self.bbox_min_lon,
                                f'{lon_field}__lte': self.bbox_max_lon})
        else:
            # Wraps: lon ≥ min OR lon ≤ max (e.g. 170°E to -170°W = Pacific).
            lon_q = (
                models.Q(**{f'{lon_field}__gte': self.bbox_min_lon})
                | models.Q(**{f'{lon_field}__lte': self.bbox_max_lon})
            )
        return lat_q & lon_q

    def matching_images(self):
        """Image queryset filtered by batch (if any) AND bbox (if any).
        Images without lat/lon are excluded when a bbox is set."""
        qs = Image.objects.all()
        if self.batch_id:
            qs = qs.filter(batch_id=self.batch_id)
        if self.has_bbox:
            qs = qs.filter(self.bbox_filter_q()).filter(
                photoCenterLat__isnull=False,
                photoCenterLon__isnull=False,
            )
        return qs

    def matching_tasks(self):
        """GeoAttempt queryset for images that match the challenge."""
        qs = GeoAttempt.objects.filter(image__in=self.matching_images())
        return qs

    def compute_counts(self):
        """Return (n_images, n_tasks) for the current batch+bbox config."""
        n_images = self.matching_images().count()
        n_tasks = self.matching_tasks().count()
        return n_images, n_tasks

    def save(self, *args, **kwargs):
        """Refresh cached_image_count / cached_task_count whenever the
        conditions (batch / bbox) might have changed. Callers that update
        only unrelated fields can pass update_fields to skip the recount."""
        update_fields = kwargs.get('update_fields')
        affecting = {'batch', 'batch_id',
                     'bbox_min_lat', 'bbox_max_lat',
                     'bbox_min_lon', 'bbox_max_lon'}
        should_recount = update_fields is None or bool(set(update_fields) & affecting)
        if should_recount:
            try:
                self.cached_image_count, self.cached_task_count = self.compute_counts()
                if update_fields is not None:
                    kwargs['update_fields'] = list(
                        set(update_fields) | {'cached_image_count', 'cached_task_count'}
                    )
            except Exception:
                pass  # Don't block save() on a count error.
        super().save(*args, **kwargs)

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
    # Unique token printed on the participant's challenge diploma; backs the
    # public /verify/<code>/ page. Generated lazily on first download.
    verify_code = models.CharField(max_length=48, blank=True, db_index=True)

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

    # ── Enrollment history ───────────────────────────────────────────
    # joined_at/left_at only describe the *current* stint. Re-joining revives
    # this row, so the exact set of periods lives in ChallengeEnrollmentPeriod.
    def open_period(self):
        return self.periods.filter(left_at__isnull=True).order_by('-joined_at').first()

    def start_period(self, at=None):
        at = at or timezone.now()
        self.close_periods(at)
        return self.periods.create(joined_at=at)

    def close_periods(self, at=None):
        at = at or timezone.now()
        return self.periods.filter(left_at__isnull=True).update(left_at=at)

    def ensure_verify_code(self):
        """Generate the diploma verification token if missing and persist it.
        Uses hex (no '-'/'_') so the code survives copy-paste from the PDF."""
        if not self.verify_code:
            import secrets
            self.verify_code = secrets.token_hex(16)
            if self.pk:
                self.save(update_fields=['verify_code'])
        return self.verify_code

    def __str__(self):
        state = 'left' if self.left_at else 'active'
        return f'{self.user} -> {self.challenge} ({state}, {self.cached_cp_count} cp)'


class ChallengeEnrollmentPeriod(models.Model):
    """
    One row per stint of a user inside a challenge. Written by join / leave /
    auto-leave; never edited by hand. `reconcile_counters` sums control points
    over these windows, so re-joining a challenge no longer loses history.
    Rows created by the 0056 backfill are flagged: they approximate the single
    joined_at/left_at that existed before and may miss intermediate stints.
    """
    participant = models.ForeignKey(
        ChallengeParticipant, on_delete=models.CASCADE, related_name='periods',
    )
    joined_at = models.DateTimeField(db_index=True)
    left_at = models.DateTimeField(blank=True, null=True)
    backfilled = models.BooleanField(default=False)

    class Meta:
        ordering = ['joined_at']
        indexes = [models.Index(fields=['participant', 'left_at'])]

    def __str__(self):
        end = f'{self.left_at:%Y-%m-%d %H:%M}' if self.left_at else 'open'
        return f'{self.participant} [{self.joined_at:%Y-%m-%d %H:%M} → {end}]'


class DiplomaDownload(models.Model):
    """One row per successful diploma render. Lets us measure whether diplomas
    are actually used: real downloads vs. previews, by whom, and over time."""
    KIND_CHOICES = (('general', 'general'), ('challenge', 'challenge'))
    user = models.ForeignKey(
        get_user_model(), on_delete=models.SET_NULL,
        null=True, blank=True, related_name='diploma_downloads',
    )
    kind = models.CharField(max_length=12, choices=KIND_CHOICES, db_index=True)
    challenge = models.ForeignKey(
        'Challenge', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='diploma_downloads',
    )
    # True when opened as an inline preview (?inline=1); False for a real download.
    inline = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['kind', '-created_at'])]

    def __str__(self):
        who = self.user.username if self.user_id else 'deleted-user'
        target = self.challenge.name if self.challenge_id else 'overall'
        mode = 'preview' if self.inline else 'download'
        return f'{who} · {self.kind}/{target} · {mode} · {self.created_at:%Y-%m-%d %H:%M}'


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


class FailedImage(models.Model):
    """
    Records an image name from a LIST batch that could not be resolved/imported,
    associated with the batch that created it. One row per (batch, name); a later
    successful re-run removes the row (see process_single_image).
    """

    FAILURE_REASON_CHOICES = (
        ('NOT_FOUND',       _('No image file found (not in images table)')),
        ('NO_COORDS',       _('No coordinates (not in frames or nadir)')),
        ('DOWNLOAD_FAILED', _('Download failed')),
        ('API_ERROR',       _('NASA API error')),
        ('PARSE_ERROR',     _('Could not parse mission/roll/frame')),
        ('ERROR',           _('Unexpected error')),
    )

    batch = models.ForeignKey('Batch', on_delete=models.CASCADE, related_name='failed_images')
    name = models.CharField(max_length=100)
    reason = models.CharField(max_length=30, choices=FAILURE_REASON_CHOICES, default='ERROR')
    detail = models.TextField(blank=True, null=True)
    createdDateTime = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('batch', 'name')
        ordering = ['-createdDateTime']

    def __str__(self):
        return f"{self.name} ({self.reason})"


class StatsEvent(models.Model):
    """
    A dated note on the staff statistics page ("newsletter sent", "campaign
    launched", "press article"...). Drawn as a vertical marker on the daily
    charts so staff can see whether an action moved sign-ups or contributions.
    """
    KIND_CHOICES = (
        ('campaign',   _('Campaign')),
        ('email',      _('Email / newsletter')),
        ('press',      _('Press / media')),
        ('social',     _('Social media')),
        ('challenge',  _('Challenge')),
        ('deploy',     _('Deploy / release')),
        ('batch',      _('Batch loaded')),
        ('other',      _('Other')),
    )

    happened_at = models.DateTimeField(default=timezone.now, db_index=True)
    kind = models.CharField(max_length=12, choices=KIND_CHOICES, default='other')
    title = models.CharField(max_length=140)
    note = models.TextField(blank=True)
    url = models.URLField(blank=True)
    created_by = models.ForeignKey(
        get_user_model(), on_delete=models.SET_NULL, blank=True, null=True,
        related_name='stats_events',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-happened_at']

    def __str__(self):
        return f'{self.happened_at:%Y-%m-%d} · {self.get_kind_display()} · {self.title}'


class DailyMetric(models.Model):
    """
    One value per (day, key). Written once a day by the scheduler for metrics
    that are *states* with no history in the database (pending tasks, team
    count, newsletter subscribers…). Event-like metrics (contributions,
    sign-ups) are not stored here: they are recomputed from their own
    timestamps, so corrections to the data correct the charts too.
    """
    date = models.DateField(db_index=True)
    key = models.CharField(max_length=40)
    value = models.BigIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['date', 'key'], name='unique_daily_metric')]
        indexes = [models.Index(fields=['key', 'date'])]
        ordering = ['date']

    def __str__(self):
        return f'{self.date} {self.key}={self.value}'


class NasaPhoto(models.Model):
    """
    Our catalogue of NASA's ISS photography: one row per photo of every synced
    mission, built from the cached EOL tables (`fetch_nasa_cache` +
    `sync_nasa_catalog`). Metadata only; files are downloaded when a photo is
    loaded as a task (`import_task_list`).

    tier: how easy the photo is to locate — A catalogued centre, B machine-
    learning centre, C nadir only with a long lens (likely looking down),
    D nadir only with a wide lens or oblique, '' no coordinates at all.
    """
    TIERS = (('A', 'Catalogued centre'), ('B', 'ML centre'), ('C', 'Nadir, long lens'),
             ('D', 'Nadir, wide/oblique'), ('', 'No coordinates'))

    mission = models.CharField(max_length=10, db_index=True)
    roll = models.CharField(max_length=2, default='E')
    frame = models.IntegerField()
    has_large = models.BooleanField(default=False)
    filename = models.CharField(max_length=100, blank=True)
    directory = models.CharField(max_length=100, blank=True)
    nadir_lat = models.FloatField(null=True, blank=True)
    nadir_lon = models.FloatField(null=True, blank=True)
    center_lat = models.FloatField(null=True, blank=True)
    center_lon = models.FloatField(null=True, blank=True)
    ml_lat = models.FloatField(null=True, blank=True)
    ml_lon = models.FloatField(null=True, blank=True)
    taken = models.DateTimeField(null=True, blank=True)
    camera = models.CharField(max_length=100, blank=True)
    focal = models.IntegerField(null=True, blank=True)
    tilt = models.CharField(max_length=4, blank=True)        # NV / LO / HO or degrees (catalogued only)
    features = models.CharField(max_length=200, blank=True)  # NASA analyst keywords (catalogued only)
    cloud_pct = models.IntegerField(null=True, blank=True)
    region = models.CharField(max_length=120, blank=True)    # NASA geographic name (catalogued only)
    sun_elev_nasa = models.FloatField(null=True, blank=True)
    sun_elev = models.FloatField(null=True, blank=True)      # computed from nadir/centre + time
    night = models.BooleanField(default=False)               # sun_elev <= -6
    tier = models.CharField(max_length=1, blank=True, choices=TIERS)
    image = models.ForeignKey('Image', null=True, blank=True, on_delete=models.SET_NULL, related_name='catalog_rows')
    done_count = models.IntegerField(default=0)
    pending_count = models.IntegerField(default=0)
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['mission', 'roll', 'frame'], name='unique_nasa_photo')]
        indexes = [
            models.Index(fields=['night', 'tier']),
            models.Index(fields=['nadir_lat', 'nadir_lon']),
            models.Index(fields=['mission', 'night']),
        ]

    @property
    def nasa_id(self):
        return f'{self.mission}-{self.roll}-{self.frame}'

    @property
    def best_lat(self):
        return self.center_lat if self.center_lat is not None else (self.ml_lat if self.ml_lat is not None else self.nadir_lat)

    @property
    def best_lon(self):
        return self.center_lon if self.center_lon is not None else (self.ml_lon if self.ml_lon is not None else self.nadir_lon)

    def __str__(self):
        return self.nasa_id


class SkipReason(models.Model):
    """
    Why a volunteer skipped a task. One click on the Skip chooser; optional
    ("no reason" is allowed). Aggregated per image it is a crowd-sourced content
    label (not night / no city lights / too hard / broken image) that feeds the
    catalogue and the auto-parking rule.
    """
    REASONS = (
        ('not_night', _('Not a night photo')),
        ('no_city', _('No city lights visible')),
        ('too_hard', _('Too hard to locate')),
        ('bad_image', _('Problem with the image')),
        ('none', _('No reason given')),
    )
    PARKING_REASONS = ('not_night', 'no_city', 'bad_image')

    image = models.ForeignKey('Image', on_delete=models.CASCADE, related_name='skip_reasons')
    geoattempt = models.ForeignKey('GeoAttempt', null=True, blank=True, on_delete=models.SET_NULL, related_name='skip_reasons')
    user = models.ForeignKey(get_user_model(), null=True, blank=True, on_delete=models.SET_NULL, related_name='skip_reasons')
    reason = models.CharField(max_length=12, choices=REASONS, default='none')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [models.Index(fields=['image', 'reason'])]

    def __str__(self):
        return f'{self.image_id} {self.reason} {self.created_at:%Y-%m-%d}'
