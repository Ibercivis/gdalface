from django.apps import AppConfig
from django.db.models.signals import post_migrate
from django_rq import get_scheduler
from datetime import datetime


class GeoreferencingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'georeferencing'

    def ready(self):
        # Connect the post_migrate signal to schedule tasks after migrations
        post_migrate.connect(schedule_tasks, sender=self)


def schedule_tasks(sender, **kwargs):
    import sys
    # The test runner also emits post_migrate (while building the test DB) and
    # would register jobs in the real Redis. Skip it there.
    if 'test' in sys.argv[1:2] or 'PYTEST_CURRENT_TEST' in __import__('os').environ:
        return
    scheduler = get_scheduler('lost_scheduler')

    # First, clear existing copies of the jobs we (re)schedule below.
    managed = {'georeferencing.tasks.update_assigned',
               'georeferencing.tasks.write_stats_snapshot',
               'georeferencing.tasks.reconcile_counters_job'}
    for job in scheduler.get_jobs():
        if job.func_name in managed:
            scheduler.cancel(job)  # removes the zset entry too (job.delete() left dangling ids)

    # Now, schedule the new task to run every hour indefinitely
    scheduler.schedule(
        scheduled_time=datetime.utcnow(),  # First execution time
        func='georeferencing.tasks.update_assigned',  # Task to run
        interval=3600,  # 3600 seconds = 1 hour
        repeat=None  # Run indefinitely
    )

    # Refresh the public project-stats snapshot every day at 00:00 UTC.
    scheduler.cron(
        '0 0 * * *',  # midnight UTC (rq-scheduler uses UTC by default)
        func='georeferencing.tasks.write_stats_snapshot',
        queue_name='lost_scheduler',
        repeat=None  # Run indefinitely
    )

    # Weekly counter reconciliation (Monday 03:00 UTC). Logs drift as a StatsEvent.
    scheduler.cron(
        '0 3 * * 1',
        func='georeferencing.tasks.reconcile_counters_job',
        queue_name='lost_scheduler',
        repeat=None
    )
