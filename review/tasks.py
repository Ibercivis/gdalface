from django_rq import job


@job('lost_scheduler', timeout=1200)
def build_overlays_job(limit=200, workers=2):
    """Periodic: warp any DONE attempt whose overlay is missing or out of date
    (new attempts, or control points edited since). Bounded per run so a backlog
    drains over several runs instead of hogging the worker."""
    from io import StringIO
    from django.core.management import call_command
    out = StringIO()
    call_command('build_overlays', '--limit', str(limit), '--workers', str(workers), stdout=out, stderr=out)
    return out.getvalue().strip()[-500:]
