# Generated by Django 4.2.16 on 2025-03-01 11:02

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('georeferencing', '0038_image_maxzoom_image_minzoom'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='image',
            name='maxZoom',
        ),
        migrations.RemoveField(
            model_name='image',
            name='minZoom',
        ),
    ]
