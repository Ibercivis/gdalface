# Generated by Django 4.2.16 on 2024-10-27 07:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('georeferencing', '0035_batch_type_alter_batch_originalimages'),
    ]

    operations = [
        migrations.AddField(
            model_name='geoattempt',
            name='maxZoom',
            field=models.IntegerField(default=2),
        ),
    ]
