# Generated by Django 4.2.11 on 2024-10-11 20:00

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('georeferencing', '0019_rename_created_image_createddatetime'),
    ]

    operations = [
        migrations.DeleteModel(
            name='Controlpoint',
        ),
    ]