# Generated by Django 4.2.11 on 2024-09-02 11:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('georeferencing', '0004_alter_imagegeoattempt_path'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='controlpoint',
            name='user',
        ),
        migrations.RemoveField(
            model_name='imagegeoattempt',
            name='user',
        ),
        migrations.AlterField(
            model_name='imagegeoattempt',
            name='path',
            field=models.FilePathField(path='/tmp/'),
        ),
    ]
