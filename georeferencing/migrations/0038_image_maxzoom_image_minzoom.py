# Generated by Django 4.2.16 on 2024-10-27 09:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('georeferencing', '0037_remove_geoattempt_maxzoom'),
    ]

    operations = [
        migrations.AddField(
            model_name='image',
            name='maxZoom',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='image',
            name='minZoom',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]