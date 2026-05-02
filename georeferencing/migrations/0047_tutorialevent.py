from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('georeferencing', '0046_add_expedition_model'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TutorialEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_key', models.CharField(blank=True, max_length=40)),
                ('event', models.CharField(choices=[('started', 'Started'), ('step', 'Step'), ('completed', 'Completed'), ('dismissed', 'Dismissed')], max_length=20)),
                ('step', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddIndex(
            model_name='tutorialevent',
            index=models.Index(fields=['event', 'created_at'], name='georeferenc_event_4ceb18_idx'),
        ),
    ]
