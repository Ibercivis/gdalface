"""
Forms for the user_profile app.
"""
from django import forms
from django_countries.widgets import CountrySelectWidget
from .models import UserProfile

class UserProfileForm(forms.ModelForm):
    """
    Form for editing user profile information.
    """
    class Meta:
        model = UserProfile
        fields = ['bio', 'profile_pic', 'country', 'location']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'profile_pic': forms.FileInput(attrs={'class': 'form-control'}),
            'country': CountrySelectWidget(attrs={'class': 'form-control form-select'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ciudad'})
        }
        labels = {
            'bio': 'Biography',
            'profile_pic': 'Profile Picture',
            'country': 'País',
            'location': 'Ciudad'
        }