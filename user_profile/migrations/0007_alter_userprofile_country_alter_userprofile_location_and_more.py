# Generated by Django 4.2.16 on 2025-04-19 07:53

from django.db import migrations, models
import django_countries.fields


class Migration(migrations.Migration):

    dependencies = [
        ('user_profile', '0006_userprofile_visible'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userprofile',
            name='country',
            field=django_countries.fields.CountryField(blank=True, max_length=2, null=True, verbose_name='Country'),
        ),
        migrations.AlterField(
            model_name='userprofile',
            name='location',
            field=models.CharField(blank=True, max_length=100, verbose_name='City'),
        ),
        migrations.AlterField(
            model_name='userprofile',
            name='visible',
            field=models.BooleanField(default=True, help_text='If disabled, your profile will not appear in public rankings', verbose_name='Visible in rankings'),
        ),
    ]
