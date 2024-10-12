from django.apps import AppConfig
from django.db.models.signals import post_migrate
from django_rq import get_scheduler
from datetime import datetime, timedelta
import django_rq


class GeoreferencingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'georeferencing'

    def ready(self):
        # Connect the post_migrate signal to schedule tasks after migrations
        post_migrate.connect(schedule_tasks, sender=self)


def schedule_tasks(sender, **kwargs):
    scheduler = get_scheduler('default')

    # First, clear the existing job for update_assigned if it exists
    for job in scheduler.get_jobs():
        if job.func_name == 'georeferencing.tasks.update_assigned':
            job.delete()

    # Now, schedule the new task to run every hour indefinitely
    scheduler.schedule(
        scheduled_time=datetime.utcnow(),  # First execution time
        func='georeferencing.tasks.update_assigned',  # Task to run
        interval=3600,  # 3600 seconds = 1 hour
        repeat=None  # Run indefinitely
    )
