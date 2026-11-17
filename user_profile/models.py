"""
Models for the user_profile app.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django_countries.fields import CountryField
from django.utils.translation import gettext_lazy as _

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
    geoattempts_done = models.IntegerField(default=0, db_index=True)
    time_spent = models.PositiveBigIntegerField(default=0, db_index=True)
    cheating = models.IntegerField(default=0)
    controlPointsDone = models.PositiveBigIntegerField(default=0, db_index=True)
    country = CountryField(blank=True, null=True, verbose_name=_("Country"))
    location = models.CharField(max_length=100, blank=True, verbose_name=_("City"))
    visible = models.BooleanField(default=True, verbose_name=_("Visible in rankings"), help_text=_("If disabled, your profile will not appear in public rankings"))

    # ── GDPR consent tracking ────────────────────────────────────────────
    privacy_accepted_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Privacy policy accepted at"))
    privacy_policy_version = models.CharField(max_length=20, blank=True, verbose_name=_("Privacy policy version"))

    newsletter_subscribed = models.BooleanField(default=False, verbose_name=_("Subscribed to newsletter"))
    newsletter_subscribed_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Newsletter subscribed at"))
    newsletter_unsubscribed_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Newsletter unsubscribed at"))
    newsletter_token = models.CharField(max_length=48, blank=True, db_index=True, verbose_name=_("Newsletter unsubscribe token"))

    cookies_analytics_consent = models.BooleanField(default=False, verbose_name=_("Analytics cookies consent"))
    cookies_functional_consent = models.BooleanField(default=False, verbose_name=_("Functional cookies consent"))
    cookies_consent_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Cookies consent given at"))

    # ── Diploma verification ─────────────────────────────────────────────
    # Unique token printed on the user's general (all-time) diploma; backs the
    # public /verify/<code>/ page. Generated lazily on first download.
    diploma_code = models.CharField(max_length=48, blank=True, db_index=True, verbose_name=_("Diploma verification code"))

    def __str__(self):
        return str(self.user.email) # pylint: disable=no-member

    def ensure_diploma_code(self):
        """Generate the general-diploma verification token if missing and persist it.
        Uses hex (no '-'/'_') so the code survives copy-paste from the PDF."""
        if not self.diploma_code:
            import secrets
            self.diploma_code = secrets.token_hex(16)
            if self.pk:
                self.save(update_fields=['diploma_code'])
        return self.diploma_code

    def ensure_newsletter_token(self):
        """Generate a token if missing — used when subscribing or for unsubscribe links."""
        if not self.newsletter_token:
            import secrets
            self.newsletter_token = secrets.token_urlsafe(32)
        return self.newsletter_token


class ApiToken(models.Model):
    """
    Personal API token for staff, used as `Authorization: Bearer <token>` on the
    read-only export API. Only the SHA-256 of the token is stored: the plaintext
    is shown once, when it is generated. One active token per user; generating a
    new one revokes the previous.
    """
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='api_tokens')
    token_hash = models.CharField(max_length=64, unique=True)
    prefix = models.CharField(max_length=8)
    created = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(null=True, blank=True)
    revoked = models.BooleanField(default=False)

    @staticmethod
    def hash_token(raw):
        import hashlib
        return hashlib.sha256(raw.encode()).hexdigest()

    @classmethod
    def issue(cls, user):
        """Revoke the user's active tokens and return (token_row, plaintext)."""
        import secrets
        cls.objects.filter(user=user, revoked=False).update(revoked=True)
        raw = secrets.token_urlsafe(32)
        row = cls.objects.create(user=user, token_hash=cls.hash_token(raw), prefix=raw[:8])
        return row, raw

    def __str__(self):
        return f'{self.user_id}:{self.prefix}…'
