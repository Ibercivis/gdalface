# Generated by Django 4.2.16 on 2024-10-27 09:33

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('georeferencing', '0036_geoattempt_maxzoom'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='geoattempt',
            name='maxZoom',
        ),
    ]
