# Generated by Django 4.2.16 on 2024-10-16 22:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('georeferencing', '0030_geoattempt_assigneduser'),
    ]

    operations = [
        migrations.AddField(
            model_name='batch',
            name='fcltge',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='batch',
            name='fcltlt',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
