# Generated by Django 4.2.16 on 2025-03-01 13:49

from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('georeferencing', '0040_geoattemptbyuserbyday'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='GeoAttemptByUserByDay',
            new_name='GeoAttemptsByUserByDay',
        ),
    ]
