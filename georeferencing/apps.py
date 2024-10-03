from django.apps import AppConfig



class GeoreferencingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'georeferencing'

    def ready(self):
        from django_q.tasks import schedule
        from datetime import timedelta
        from django.utils import timezone
        # Schedule a task to run every minute
        schedule('georeferencing.tasks.update_assigned', schedule_type='H', hours=24)
