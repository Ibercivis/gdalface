from django.contrib import admin
from django.urls import path, reverse
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django import forms

from .models import Batch, Image, GeoAttempt
from .forms import PrettyJSONWidget
import requests
from decouple import config 

class BatchAdminForm(forms.ModelForm):
    class Meta:
        model = Batch
        fields = '__all__'
        widgets = {
            'result': PrettyJSONWidget(attrs={'rows': 20, 'cols': 80})
        }


class BatchAdmin(admin.ModelAdmin):
    form = BatchAdminForm
    list_display = ('name', 'createdDateTime', 'numberImages')
    list_filter = ('createdDateTime',)
    search_fields = ('name',)
    
    exclude = ('user',)

    # Add a custom URL for fetching data
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('fetch-api-data/', self.admin_site.admin_view(self.fetch_api_data), name='fetch_api_data'),
        ]
        return custom_urls + urls

    # Custom view to fetch data from an external API
    def fetch_api_data(self, request):
        feat_value = request.GET.get('feat', '')
        mission = request.GET.get('mission', '')
        url = 'https://eol.jsc.nasa.gov/SearchPhotos/PhotosDatabaseAPI/PhotosDatabaseAPI.pl'
        query = 'query=images|directory|like|*large*'
        if feat_value:
            query = f'{query}|frames|feat|like|*{feat_value}'
        elif mission:
            query = f'{query}|frames|mission|like|*{mission}'
        key = config('NASA_API_KEY')
        urlRequest = f'{url}?{query}&return=frames|geon|frames|feat|images|directory|images|filename|frames|fclt|frames|pdate|frames|ptime|frames|lat|frames|lon&key={key}'
        print(urlRequest)
        

        try:
            response = requests.get(urlRequest)  # Replace with your API URL
            if response.status_code == 200:
                return JsonResponse({'success': True, 'result': response.text})
            else:
                return JsonResponse({'success': False, 'error': f'Error {response.status_code}'})
        except requests.RequestException as e:
            return JsonResponse({'success': False, 'error': str(e)})

    # Override the form template to inject the custom fetch button
    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['fetch_api_url'] = reverse('admin:fetch_api_data')  # Use reverse to get the URL
        return super().changeform_view(request, object_id, form_url, extra_context)

    # Automatically assign the current user when saving
    def save_model(self, request, obj, form, change):
        if not change:
            obj.user = request.user
        obj.save()


class ImageAdmin(admin.ModelAdmin):
    list_display = ('name', 'createdDateTime', 'geoattempts_count')
    list_filter = ('createdDateTime',)
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


