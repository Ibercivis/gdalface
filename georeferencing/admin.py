
"""
This module defines Django admin configurations for the georeferencing application, including
custom admin views and actions.
"""
from datetime import datetime

import requests
from decouple import config
from django import forms
from django.contrib import admin
from django.http import JsonResponse
from django.urls import path, reverse

from .forms import PrettyJSONWidget
from .models import Batch, Image, GeoAttempt
from .tasks import download_image

class BatchAdminForm(forms.ModelForm):
    """
    BatchAdminForm is a ModelForm for the Batch model. It includes all fields of the model
    and uses a custom widget for the 'result' field.
    """
    class Meta:
        """
        Meta class for the Batch model form.

        Attributes:
            - model (Model): Specifies the model associated with the form.
            - fields (str): Indicates that all fields of the model should be included in the 
            form.
            - widgets (dict): Customizes the form field for 'result' using PrettyJSONWidget 
            with specified attributes.
        """
        model = Batch
        fields = '__all__'
        widgets = {
            'result': PrettyJSONWidget(attrs={'rows': 20, 'cols': 80})
        }


class BatchAdmin(admin.ModelAdmin):
    """
    Custom admin interface for managing Batch objects.
    Attributes:
        form (BatchAdminForm): The form class to use for creating and editing Batch objects.
        list_display (tuple): Fields to display in the list view.
        list_filter (tuple): Fields to filter by in the list view.
        search_fields (tuple): Fields to search by in the list view.
        exclude (tuple): Fields to exclude from the form.
    """
    form = BatchAdminForm
    list_display = ('name', 'createdDateTime', 'numberImages')
    list_filter = ('createdDateTime',)
    search_fields = ('name',)
    exclude = ('user',)

    # Add a custom URL for fetching data
    def get_urls(self):
        """
        Overrides the default get_urls method to add custom URLs for the admin interface.

        Returns:
            list: A list of URL patterns, including the custom URL for fetching API data.
        """
        urls = super().get_urls()
        custom_urls = [
            path('fetch-api-data/',
                 self.admin_site.admin_view(self.fetch_api_data),
                 name='fetch_api_data'),
        ]
        return custom_urls + urls

    # Custom view to fetch data from an external API
    def fetch_api_data(self, request):
        """
        Fetches data from the NASA Photos Database API based on query parameters.
        Args:
            request (HttpRequest): The HTTP request object containing GET parameters.
        Returns:
            JsonResponse: A JSON response containing the success status and either the 
                          fetched data or an error message.
        GET Parameters:
            feat (str): Optional. A feature value to filter the images.
            mission (str): Optional. A mission value to filter the images.
        Raises:
            requests.RequestException: If there is an issue with the HTTP request.
        """
        print(request.GET)
        feat_value = request.GET.get('feat', '')
        mission = request.GET.get('mission', '')
        fcltle = request.GET.get('fcltle', '')
        fcltge = request.GET.get('fcltge', '')
        url = 'https://eol.jsc.nasa.gov/SearchPhotos/PhotosDatabaseAPI/PhotosDatabaseAPI.pl'
        query = 'query=images|directory|like|*large*'
        if feat_value:
            query = f'{query}|frames|feat|like|*{feat_value}*'
        if mission:
            query = f'{query}|frames|mission|like|*{mission}'
        if fcltle:
            query = f'{query}|frames|fclt|le|{fcltle}'
        if fcltge:
            query = f'{query}|frames|fclt|ge|{fcltge}'
        key = config('NASA_API_KEY')
        url_request = (
            f'{url}?{query}&return=frames|frame|frames|geon|frames|feat|frames|roll|'
            f'frames|mission|images|directory|images|filename|frames|fclt|frames|pdate|'
            f'frames|ptime|frames|lat|frames|lon|frames|nlat|frames|nlon&key={key}'
        )
        print(url_request)
        try:
            response = requests.get(url_request, timeout=5)
            if response.status_code == 200:
                return JsonResponse({'success': True, 'result': response.text})
            else:
                return JsonResponse({'success': False, 'error': f'Error {response.status_code}'})
        except requests.RequestException as e:
            return JsonResponse({'success': False, 'error': str(e)})

    # Override the form template to inject the custom fetch button
    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['fetch_api_url'] = reverse('admin:fetch_api_data')
        return super().changeform_view(request, object_id, form_url, extra_context)

    # Automatically assign the current user when saving
    def save_model(self, request, obj, form, change):
        if not change:
            obj.user = request.user
        obj.save()

        # Now, we create the images based on result, for each item in result
        # we create an image and assign it to the batch
        if obj.result:
            for item in obj.result:
                datetime_str = item['frames.pdate'] + ' ' + item['frames.ptime']
                formated_datetime = datetime.strptime(datetime_str, '%Y%m%d %H%M%S')
                largeImageURL = f"https://eol.jsc.nasa.gov/DatabaseImages/{item['images.directory']}/{item['images.filename']}"
                image = Image.objects.create(
                    name=item['images.filename'],
                    taken=formated_datetime,
                    focalLength=item['frames.fclt'],
                    photoCenterPoint=f"{item['frames.lat']}, {item['frames.lon']}",
                    spacecraftNadirPoint=f"{item['frames.nlat']}, {item['frames.nlon']}",
                    link = f"https://eol.jsc.nasa.gov/SearchPhotos/photo.pl?mission={item['frames.mission']}&roll={item['frames.roll']}&frame={item['frames.frame']}",
                    largeImageURL = largeImageURL,
                    batch=obj,
                    replicas = obj.replicas
                )
                image.save()

                # Now, add to django-rq queue the download of the large image
               
                download_image.delay(image)

                


class ImageAdmin(admin.ModelAdmin):
    list_display = ('name', 'createdDateTime', 'geoattempts_count')
    list_filter = ('createdDateTime', 'batch')
    search_fields = ('name',)

    def geoattempts_count(self, obj):
        return GeoAttempt.objects.filter(image=obj).count()
    
    geoattempts_count.short_description = '# GeoAttempts'

class GeoAttemptAdmin(admin.ModelAdmin):
    list_display = ('image', 'createdDateTime', 'status')
    list_filter = ('status', 'createdDateTime')
    search_fields = ('image__name',)

    # Define custom actions
    actions = ['mark_as_done', 'mark_as_assigned', 'mark_as_pending']

    def mark_as_done(self, request, queryset):
        update = queryset.update(status='DONE')
        self.message_user(request, f'{update} attempts marked as done')

    def mark_as_assigned(self, request, queryset):
        update = queryset.update(status='ASSIGNED')
        self.message_user(request, f'{update} attempts marked as assigned')

    def mark_as_pending(self, request, queryset):
        update = queryset.update(status='PENDING')
        self.message_user(request, f'{update} attempts marked as pending')


admin.site.register(Batch, BatchAdmin)
admin.site.register(Image, ImageAdmin)
admin.site.register(GeoAttempt, GeoAttemptAdmin)

# Register your models here.


