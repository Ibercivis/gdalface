"""
Peer review of georeferencing attempts.

`AttemptOverlay` is the derived, regenerable artefact of one DONE attempt: the
photo warped onto the map (a WebP with alpha, kept on disk under MEDIA_ROOT) plus
its footprint. The control points stay the source of truth; the file is a cache
keyed by `points_hash`. `AttemptReview` is one volunteer's OK / not OK on one
attempt.
"""
from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import gettext_lazy as _


class AttemptOverlay(models.Model):
    OK, SKIPPED, FAILED = 'ok', 'skipped', 'failed'
    STATUS_CHOICES = ((OK, 'OK'), (SKIPPED, 'Skipped'), (FAILED, 'Failed'))

    geoattempt = models.OneToOneField('georeferencing.GeoAttempt', on_delete=models.CASCADE,
                                      related_name='overlay')
    points_hash = models.CharField(max_length=40)
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, db_index=True)
    detail = models.CharField(max_length=300, blank=True)   # why skipped / failed
    n_points = models.IntegerField(default=0)
    file = models.CharField(max_length=200, blank=True)     # relative to MEDIA_ROOT
    south = models.FloatField(null=True, blank=True)
    west = models.FloatField(null=True, blank=True)
    north = models.FloatField(null=True, blank=True)
    east = models.FloatField(null=True, blank=True)
    polygon = models.JSONField(null=True, blank=True)       # closed GeoJSON ring [[lon, lat], ...]
    width = models.IntegerField(null=True, blank=True)
    height = models.IntegerField(null=True, blank=True)
    bytes = models.IntegerField(default=0)
    area_km2 = models.FloatField(null=True, blank=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'attempt {self.geoattempt_id}: {self.status}'


class AttemptReview(models.Model):
    OK, NOT_OK = 'ok', 'not_ok'
    VERDICTS = ((OK, _('OK')), (NOT_OK, _('Not OK')))

    geoattempt = models.ForeignKey('georeferencing.GeoAttempt', on_delete=models.CASCADE,
                                   related_name='reviews')
    user = models.ForeignKey(get_user_model(), null=True, blank=True, on_delete=models.SET_NULL,
                             related_name='attempt_reviews')
    verdict = models.CharField(max_length=6, choices=VERDICTS)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['geoattempt', 'user'], name='one_review_per_user_attempt')]
        indexes = [models.Index(fields=['geoattempt', 'verdict'])]

    def __str__(self):
        return f'{self.user_id} -> {self.geoattempt_id}: {self.verdict}'
