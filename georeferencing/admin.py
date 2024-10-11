from django.contrib import admin

from .models import Controlpoint, Image, GeoAttempt


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






admin.site.register(Controlpoint)
admin.site.register(Image, ImageAdmin)
admin.site.register(GeoAttempt, GeoAttemptAdmin)

# Register your models here.


