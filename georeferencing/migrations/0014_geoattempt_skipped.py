# Generated by Django 4.2.11 on 2024-09-24 21:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('georeferencing', '0013_alter_geoattempt_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='geoattempt',
            name='skipped',
            field=models.IntegerField(default=0),
        ),
    ]
