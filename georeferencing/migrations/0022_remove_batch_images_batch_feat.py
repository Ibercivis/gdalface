# Generated by Django 4.2.11 on 2024-10-11 21:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('georeferencing', '0021_batch'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='batch',
            name='images',
        ),
        migrations.AddField(
            model_name='batch',
            name='feat',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
