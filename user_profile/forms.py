"""
Forms for the user_profile app.
"""
import secrets
from django import forms
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_countries.widgets import CountrySelectWidget
from allauth.account.forms import SignupForm
from .models import UserProfile

class UserProfileForm(forms.ModelForm):
    """
    Form for editing user profile information.
    """
    class Meta:
        model = UserProfile
        fields = ['bio', 'profile_pic', 'country', 'location', 'visible', 'newsletter_subscribed']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'profile_pic': forms.FileInput(attrs={'class': 'form-control'}),
            'country': CountrySelectWidget(attrs={'class': 'form-control form-select'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('City')}),
            'visible': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'newsletter_subscribed': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'bio': _('Biography'),
            'profile_pic': _('Profile Picture'),
            'country': _('Country'),
            'location': _('City'),
            'visible': _('Visible in rankings'),
            'newsletter_subscribed': _('Receive newsletters and project updates'),
        }
        help_texts = {
            'visible': _('If disabled, your profile will not appear in public rankings'),
            'newsletter_subscribed': _('Occasional emails about new campaigns, features and citizen-science news. You can opt out at any time.'),
        }


class CustomSignupForm(SignupForm):
    """Allauth signup form augmented with GDPR consent + newsletter opt-in."""

    privacy_accepted = forms.BooleanField(
        required=True,
        label=_('I have read and accept the privacy policy and terms of use.'),
        error_messages={
            'required': _('You must accept the privacy policy to create an account.'),
        },
    )
    newsletter_subscribed = forms.BooleanField(
        required=False,
        label=_('Send me updates about Lost at Night and citizen-science campaigns (optional).'),
    )

    def save(self, request):
        user = super().save(request)
        profile, _created = UserProfile.objects.get_or_create(user=user)
        now = timezone.now()
        profile.privacy_accepted_at = now
        profile.privacy_policy_version = getattr(settings, 'PRIVACY_POLICY_VERSION', '')
        if self.cleaned_data.get('newsletter_subscribed'):
            profile.newsletter_subscribed = True
            profile.newsletter_subscribed_at = now
            if not profile.newsletter_token:
                profile.newsletter_token = secrets.token_urlsafe(32)
        profile.save()
        return user
