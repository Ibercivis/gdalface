# Generated by Django 4.2.11 on 2024-03-26 18:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('georeferencing', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='imagegeoattempt',
            name='status',
            field=models.CharField(choices=[('PENDING', 'Pending'), ('DOING', 'Doing'), ('SUCCESS', 'Success'), ('FAILURE', 'Failure')], default='PENDING', max_length=10),
        ),
    ]
