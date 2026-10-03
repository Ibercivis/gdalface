"""
Summary of diploma usage — a quick read on whether diplomas are worth keeping.

    python manage.py diploma_stats
    python manage.py diploma_stats --days 30   # window for the breakdowns
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone

from georeferencing.models import DiplomaDownload


class Command(BaseCommand):
    help = "Print diploma download/preview statistics."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=30,
                            help="Window (days) for the by-kind/by-challenge breakdowns.")

    def handle(self, *args, **opts):
        qs = DiplomaDownload.objects.all()
        total = qs.count()
        if not total:
            self.stdout.write("No diploma activity logged yet.")
            return

        downloads = qs.filter(inline=False).count()
        previews = qs.filter(inline=True).count()
        uniq_users = qs.exclude(user=None).values("user").distinct().count()

        self.stdout.write(self.style.MIGRATE_HEADING("Diploma usage"))
        self.stdout.write(f"  Total events : {total}  (downloads={downloads}, previews={previews})")
        self.stdout.write(f"  Unique users : {uniq_users}")

        self.stdout.write("  Recent activity:")
        now = timezone.now()
        for label, days in (("last 24h", 1), ("last 7d", 7), ("last 30d", 30)):
            n = qs.filter(created_at__gte=now - timedelta(days=days)).count()
            d = qs.filter(created_at__gte=now - timedelta(days=days), inline=False).count()
            self.stdout.write(f"    {label:<9}: {n:>4}  (downloads={d})")

        window = now - timedelta(days=opts["days"])
        w = qs.filter(created_at__gte=window)

        self.stdout.write(f"  By kind (last {opts['days']}d):")
        for r in w.values("kind").annotate(n=Count("id")).order_by("-n"):
            self.stdout.write(f"    {r['kind']:<10}: {r['n']}")

        self.stdout.write(f"  By challenge (last {opts['days']}d):")
        rows = (w.exclude(challenge=None)
                 .values("challenge__name")
                 .annotate(n=Count("id"))
                 .order_by("-n"))
        if rows:
            for r in rows:
                self.stdout.write(f"    {r['challenge__name']:<20}: {r['n']}")
        else:
            self.stdout.write("    (none)")
