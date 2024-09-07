from django.contrib import admin

from .models import Controlpoint, Image, GeoAttempt

admin.site.register(Controlpoint)
admin.site.register(Image)
admin.site.register(GeoAttempt)

# Register your models here.
