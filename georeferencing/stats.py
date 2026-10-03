"""
Project-level aggregate statistics, exposed as a small, stable JSON contract so
external dashboards can pull a uniform snapshot from every project.

The shape is the "standard": keep ``schema_version``, ``project``,
``generated_at`` and ``metrics`` stable across projects; only ``metrics`` grows
over time. Add new keys to ``metrics`` — never rename or repurpose old ones.
"""
import json
import os

from django.conf import settings
from django.utils import timezone

SCHEMA_VERSION = "1.0"

# Where the daily snapshot is written. Lives under MEDIA_ROOT so it survives
# `collectstatic` and is already served by nginx at /media/ in production.
SNAPSHOT_PATH = os.path.join(settings.MEDIA_ROOT, "stats.json")


def _public_activity_metrics():
    """Public counters, all from georeferencing.metrics."""
    from . import metrics
    t = metrics.project_totals()
    return {
        "participants": t["participants"],
        "contributions_total": t["tasks_done"],
        "control_points_total": t["control_points"],
        "images_georeferenced": t["images_georeferenced"],
        "tasks_pending": t["tasks_pending"],
        "active_users_7d": metrics.active_users(7),
        "active_users_30d": metrics.active_users(30),
    }


def build_stats():
    """Compute the current stats snapshot as a plain dict."""
    identity = getattr(settings, "PROJECT_STATS_IDENTITY", {})
    return {
        "schema_version": SCHEMA_VERSION,
        "project": {
            "id": identity.get("id", "lostatnight"),
            "name": identity.get("name", "Lost at Night"),
            "url": identity.get("url", ""),
        },
        "generated_at": timezone.now().isoformat(),
        "metrics": _public_activity_metrics(),
    }


def write_snapshot():
    """Compute and atomically persist the snapshot to SNAPSHOT_PATH. Returns it."""
    data = build_stats()
    os.makedirs(os.path.dirname(SNAPSHOT_PATH), exist_ok=True)
    tmp = SNAPSHOT_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, SNAPSHOT_PATH)  # atomic swap, never a half-written file
    return data


def read_snapshot():
    """Return the persisted snapshot, or None if it hasn't been generated yet."""
    try:
        with open(SNAPSHOT_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


# ═══════════════════════════════════════════════════════════════════════════
# Staff dashboard (/stats/) — richer, internal-only metrics.
# ═══════════════════════════════════════════════════════════════════════════
from datetime import timedelta  # noqa: E402

from django.db import models  # noqa: E402
from django.db.models import Count, Q, Sum  # noqa: E402
from django.db.models.functions import TruncDate  # noqa: E402

STAFF_STATS_CACHE_KEY = "staff_stats:v1"
STAFF_STATS_CACHE_SECONDS = 300
STALE_ASSIGNED_HOURS = 7  # update_assigned releases at 6 h and runs hourly, so >7 h means it is not running


def _date_range(start, end):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def _daily(qs, field, start, end):
    """{date: count} for rows of ``qs`` whose ``field`` falls in [start, end]."""
    rows = (qs.filter(**{f"{field}__date__gte": start, f"{field}__date__lte": end})
            .annotate(_d=TruncDate(field)).values("_d")
            .annotate(n=Count("id")).order_by())
    counts = {r["_d"]: r["n"] for r in rows}
    return {d: counts.get(d, 0) for d in _date_range(start, end)}


def _series(mapping):
    """{date: n} → [{'date': 'YYYY-MM-DD', 'n': n}, ...] (JSON friendly)."""
    return [{"date": d.isoformat(), "n": n} for d, n in sorted(mapping.items())]


def _active_users(since_date):
    from .models import GeoAttemptsByUserByDay
    return (GeoAttemptsByUserByDay.objects
            .filter(date__gte=since_date, numberGeoAttempts__gt=0)
            .values("user_id").distinct().count())


def _people(now, today, start):
    from django.contrib.auth import get_user_model
    from allauth.account.models import EmailAddress
    from user_profile.models import UserProfile
    from .models import GeoAttempt
    User = get_user_model()
    users = User.objects.all()
    contributors_ever = (GeoAttempt.objects.filter(status="DONE", assignedUser__isnull=False)
                         .values("assignedUser_id").distinct().count())
    total = users.count()
    return {
        "total": total,
        "verified": EmailAddress.objects.filter(verified=True).values("user_id").distinct().count(),
        "staff": users.filter(is_staff=True).count(),
        "signups_7": users.filter(date_joined__gte=now - timedelta(days=7)).count(),
        "signups_30": users.filter(date_joined__gte=now - timedelta(days=30)).count(),
        "signups_series": _series(_daily(users, "date_joined", start, today)),
        "active_7": _active_users(today - timedelta(days=7)),
        "active_30": _active_users(today - timedelta(days=30)),
        "contributors_ever": contributors_ever,
        "contributors_pct": round(contributors_ever / total * 100, 1) if total else 0,
        "newsletter": UserProfile.objects.filter(newsletter_subscribed=True).count(),
        "cheating_flagged": UserProfile.objects.filter(cheating__gt=0).count(),
    }


def _contributions(now, today, start):
    from user_profile.models import UserProfile
    from .models import GeoAttempt
    done = GeoAttempt.objects.filter(status="DONE")
    total_series = _daily(done, "finishedDateTime", start, today)
    reg_series = _daily(done.filter(assignedUser__isnull=False), "finishedDateTime", start, today)
    anon_series = {d: total_series[d] - reg_series[d] for d in total_series}
    prof = UserProfile.objects.aggregate(cp=Sum("controlPointsDone"),
                                         secs=Sum("time_spent"),
                                         n=Sum("geoattempts_done"))
    last7 = sum(v for d, v in total_series.items() if d > today - timedelta(days=7))
    last30 = sum(v for d, v in total_series.items() if d > today - timedelta(days=30))
    return {
        "total": done.count(),
        "anonymous_total": done.filter(assignedUser__isnull=True).count(),
        "last_7": last7,
        "last_30": last30,
        "avg_per_day_7": round(last7 / 7, 1),
        "series": _series(total_series),
        "series_registered": _series(reg_series),
        "series_anonymous": _series(anon_series),
        "control_points_total": prof["cp"] or 0,
        "skipped_total": GeoAttempt.objects.aggregate(s=Sum("skipped"))["s"] or 0,
        "avg_seconds_per_task": round((prof["secs"] or 0) / prof["n"]) if prof["n"] else None,
    }


def _queue(now, avg_per_day_7):
    from .models import Batch, GeoAttempt, Image
    by_status = dict(GeoAttempt.objects.values_list("status").annotate(n=Count("id")).order_by())
    pending = by_status.get("PENDING", 0)
    per_batch = []
    for b in Batch.objects.order_by("-createdDateTime"):
        st = dict(GeoAttempt.objects.filter(image__batch=b)
                  .values_list("status").annotate(n=Count("id")).order_by())
        tot = sum(st.values())
        per_batch.append({
            "id": b.id, "name": b.name, "created": b.createdDateTime.date().isoformat(),
            "images": Image.objects.filter(batch=b).count(),
            "pending": st.get("PENDING", 0), "assigned": st.get("ASSIGNED", 0),
            "done": st.get("DONE", 0), "total": tot,
            "pct_done": round(st.get("DONE", 0) / tot * 100, 1) if tot else 0,
            "images_untouched": Image.objects.filter(batch=b).exclude(
                id__in=GeoAttempt.objects.filter(status="DONE").values("image_id")).count(),
        })
    return {
        "pending": pending,
        "assigned": by_status.get("ASSIGNED", 0),
        "done": by_status.get("DONE", 0),
        "total": sum(by_status.values()),
        "orphan_pending": GeoAttempt.objects.filter(status="PENDING", image__batch__isnull=True).count(),
        "images_total": Image.objects.count(),
        "images_untouched": Image.objects.exclude(
            id__in=GeoAttempt.objects.filter(status="DONE").values("image_id")).count(),
        "days_to_exhaust": round(pending / avg_per_day_7) if avg_per_day_7 else None,
        "per_batch": per_batch,
    }


def _challenge_detail(ch, now, today, start):
    """Per-challenge block. Daily series = DONE tasks by enrolled participants
    inside their enrollment window and the challenge window, on images that
    match the challenge (batch ∩ bbox)."""
    from .models import GeoAttempt
    parts = list(ch.participants.select_related("user", "user__userprofile")
                 .order_by("-cached_cp_count", "joined_at"))
    active_parts = [p for p in parts if p.left_at is None]
    total_cp = sum(p.cached_cp_count for p in parts)

    q = Q(pk__in=[])  # always-false seed
    for p in parts:
        lo = max(p.joined_at, ch.start_at)
        hi = min(p.left_at or ch.end_at, ch.end_at)
        q |= Q(assignedUser_id=p.user_id, finishedDateTime__gte=lo, finishedDateTime__lt=hi)
    done_qs = GeoAttempt.objects.filter(status="DONE").filter(q)
    if ch.batch_id:
        done_qs = done_qs.filter(image__batch_id=ch.batch_id)
    if ch.has_bbox:
        done_qs = done_qs.filter(ch.bbox_filter_q("image__photoCenterLat", "image__photoCenterLon"))

    ser_start = max(start, ch.start_at.date())
    ser_end = min(today, ch.end_at.date())
    series = _daily(done_qs, "finishedDateTime", ser_start, ser_end) if ser_start <= ser_end else {}
    tasks_total = ch.matching_tasks().count()
    tasks_pending = ch.matching_tasks().filter(status="PENDING").count()

    tiers = [("bronze", ch.target_bronze), ("silver", ch.target_silver), ("gold", ch.target_gold)]
    next_tier = next(((lbl, v - total_cp) for lbl, v in tiers if total_cp < v), None)
    if now >= ch.end_at:
        days_left = 0
    elif now < ch.start_at:
        days_left = (ch.start_at - now).days
    else:
        days_left = (ch.end_at - now).days
    joined_7 = sum(1 for p in parts if p.joined_at >= now - timedelta(days=7))
    done_7 = done_qs.filter(finishedDateTime__gte=now - timedelta(days=7)).count()
    done_total = done_qs.count()
    contributing = (done_qs.values("assignedUser_id").distinct().count())
    return {
        "id": ch.id, "name": ch.name, "status": ch.status,
        "start": ch.start_at.date().isoformat(), "end": ch.end_at.date().isoformat(),
        "days_left": days_left,
        "batch": ch.batch.name if ch.batch_id else None, "has_bbox": ch.has_bbox,
        "participants": len(parts), "participants_active": len(active_parts),
        "participants_contributing": contributing,
        "joined_7": joined_7,
        "total_cp": total_cp,
        "targets": {"bronze": ch.target_bronze, "silver": ch.target_silver, "gold": ch.target_gold},
        "progress_pct": round(min(100, total_cp / ch.target_gold * 100), 1) if ch.target_gold else 0,
        "next_tier": {"label": next_tier[0], "remaining": next_tier[1]} if next_tier else None,
        "tasks_total": tasks_total, "tasks_pending": tasks_pending,
        "tasks_done": done_total, "tasks_done_7": done_7,
        "cached_task_count": ch.cached_task_count,
        "series": _series(series),
        "top": [{"username": p.user.username, "cp": p.cached_cp_count,
                 "active": p.left_at is None} for p in parts[:10]],
        "diplomas": ch.diploma_downloads.filter(inline=False).count(),
    }


def _challenges(now, today, start):
    from .models import Challenge
    detail, finished = [], []
    for ch in Challenge.objects.select_related("batch"):
        if ch.status in ("active", "paused", "upcoming"):
            detail.append(_challenge_detail(ch, now, today, start))
        else:
            parts = ch.participants.all()
            finished.append({
                "id": ch.id, "name": ch.name, "status": ch.status,
                "start": ch.start_at.date().isoformat(), "end": ch.end_at.date().isoformat(),
                "participants": parts.count(),
                "total_cp": parts.aggregate(s=Sum("cached_cp_count"))["s"] or 0,
                "gold": ch.target_gold,
                "diplomas": ch.diploma_downloads.filter(inline=False).count(),
            })
    return {"open": detail, "finished": finished}


def _health(now):
    from .models import Batch, FailedImage, GeoAttempt, Image
    last_batch = Batch.objects.order_by("-createdDateTime").first()
    return {
        "stale_assigned": GeoAttempt.objects.filter(
            status="ASSIGNED",
            assignedDateTime__lt=now - timedelta(hours=STALE_ASSIGNED_HOURS)).count(),
        "images_pending_download": Image.objects.filter(status="PENDING").count(),
        "images_failed_download": Image.objects.filter(status="FAILED_DOWNLOADED").count(),
        "images_no_coords": Image.objects.filter(photoCenterLat__isnull=True).count(),
        "failed_images": list(FailedImage.objects.values("reason")
                              .annotate(n=Count("id")).order_by("-n")),
        "last_batch": {
            "name": last_batch.name, "status": last_batch.processing_status,
            "created": last_batch.createdDateTime.date().isoformat(),
        } if last_batch else None,
        "snapshot_generated_at": (read_snapshot() or {}).get("generated_at"),
    }


def _onboarding():
    from .models import DiplomaDownload, TutorialEvent

    def distinct(event):
        qs = TutorialEvent.objects.filter(event=event)
        users = qs.filter(user__isnull=False).values("user_id").distinct().count()
        anon = qs.filter(user__isnull=True).values("session_key").distinct().count()
        return users + anon

    started = distinct("started")
    completed = distinct("completed")
    return {
        "tutorial_started": started,
        "tutorial_completed": completed,
        "tutorial_dismissed": distinct("dismissed"),
        "tutorial_completion_pct": round(completed / started * 100, 1) if started else 0,
        "diploma_downloads": DiplomaDownload.objects.filter(inline=False).count(),
        "diploma_previews": DiplomaDownload.objects.filter(inline=True).count(),
    }


def _events(start):
    from .models import StatsEvent
    return [{
        "id": e.id, "date": e.happened_at.date().isoformat(),
        "kind": e.kind, "kind_label": str(e.get_kind_display()),
        "title": e.title, "note": e.note, "url": e.url,
        "by": e.created_by.username if e.created_by_id else "",
    } for e in StatsEvent.objects.select_related("created_by")
        .filter(happened_at__date__gte=start)]


def build_staff_stats(days=60):
    """Everything the staff dashboard shows, as one JSON-serialisable dict."""
    now = timezone.now()
    today = now.date()
    start = today - timedelta(days=days - 1)
    contributions = _contributions(now, today, start)
    return {
        "generated_at": now.isoformat(),
        "days": days,
        "start": start.isoformat(),
        "end": today.isoformat(),
        "people": _people(now, today, start),
        "contributions": contributions,
        "queue": _queue(now, contributions["avg_per_day_7"]),
        "challenges": _challenges(now, today, start),
        "health": _health(now),
        "onboarding": _onboarding(),
        "events": _events(start),
    }


def cached_staff_stats(days=60, refresh=False):
    from django.core.cache import cache
    key = f"{STAFF_STATS_CACHE_KEY}:{days}"
    data = None if refresh else cache.get(key)
    if data is None:
        data = build_staff_stats(days)
        cache.set(key, data, STAFF_STATS_CACHE_SECONDS)
    return data
