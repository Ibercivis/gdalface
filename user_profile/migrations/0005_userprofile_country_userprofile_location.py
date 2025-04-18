# Generated by Django 4.2.16 on 2025-04-16 10:04

from django.db import migrations, models
import django_countries.fields


class Migration(migrations.Migration):

    dependencies = [
        ('user_profile', '0004_userprofile_cheating'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='country',
            field=django_countries.fields.CountryField(blank=True, max_length=2, null=True, verbose_name='País'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='location',
            field=models.CharField(blank=True, max_length=100, verbose_name='Ciudad'),
        ),
    ]
