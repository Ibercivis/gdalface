# Generated by Django 4.2.11 on 2024-10-01 16:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('georeferencing', '0017_alter_geoattempt_status'),
    ]

    operations = [
        migrations.RenameField(
            model_name='geoattempt',
            old_name='created',
            new_name='createdDateTime',
        ),
        migrations.AddField(
            model_name='geoattempt',
            name='assignedDateTime',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='geoattempt',
            name='finishedDateTime',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='geoattempt',
            name='numberTries',
            field=models.IntegerField(default=0),
        ),
    ]
