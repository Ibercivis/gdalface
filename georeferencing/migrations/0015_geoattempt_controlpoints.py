# Generated by Django 4.2.11 on 2024-09-24 21:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('georeferencing', '0014_geoattempt_skipped'),
    ]

    operations = [
        migrations.AddField(
            model_name='geoattempt',
            name='controlPoints',
            field=models.JSONField(default=dict),
        ),
    ]
