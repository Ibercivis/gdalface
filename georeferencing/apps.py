from django.apps import AppConfig
from django.db.models.signals import post_migrate


class GeoreferencingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'georeferencing'

    def ready(self):
        # Connect the post_migrate signal to schedule tasks after migrations
        post_migrate.connect(schedule_tasks, sender=self)


def schedule_tasks(sender, **kwargs):
    # Delay import until after the app registry is fully loaded
    from django_q.tasks import schedule, Schedule
    from django.db.utils import OperationalError

    try:
        # Ensure the task isn't already scheduled
        if not Schedule.objects.filter(func='georeferencing.tasks.update_assigned').exists():
            # Schedule the task
            schedule(
                'georeferencing.tasks.update_assigned',
                schedule_type='H',
                hours=1,
                repeats=-1  # repeat indefinitely
            )
    except OperationalError:
        # If database isn't ready yet, avoid scheduling
        pass
