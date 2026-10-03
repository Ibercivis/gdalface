"""
Recompute every denormalised counter from GeoAttempt DONE rows and report the
drift. Dry-run by default; pass --apply to write.

    manage.py reconcile_counters            # report only
    manage.py reconcile_counters --apply    # fix
    manage.py reconcile_counters --apply --quiet
    manage.py reconcile_counters --apply --challenges   # also rewrite challenge CP (see --help)
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from georeferencing.models import (
    Challenge, ChallengeParticipant, GeoAttemptsByUserByDay,
)
from georeferencing.reconcile import (
    expected_daily_counts, expected_participant_cp, expected_profile_totals,
)
from user_profile.models import UserProfile


class Command(BaseCommand):
    help = 'Recompute profile / daily / challenge counters from DONE GeoAttempts (dry-run unless --apply).'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Write the corrected values.')
        parser.add_argument('--challenges', action='store_true',
                            help='Also rewrite ChallengeParticipant.cached_cp_count. Off by default: '
                                 'the model keeps no join/leave history, so a re-joined enrollment '
                                 'cannot be reconstructed exactly (see PLAN.md 1.2).')
        parser.add_argument('--quiet', action='store_true', help='Only print the summary line.')
        parser.add_argument('--limit', type=int, default=25, help='Max per-row diffs to print.')

    def handle(self, *args, **opts):
        apply, quiet, limit = opts['apply'], opts['quiet'], opts['limit']
        apply_ch = apply and opts['challenges']
        shown = 0

        def show(line):
            nonlocal shown
            if not quiet and shown < limit:
                self.stdout.write('  ' + line)
                shown += 1

        summary = {}
        with transaction.atomic():
            # ── UserProfile ──────────────────────────────────────────
            expected = expected_profile_totals()
            profiles = {p.user_id: p for p in UserProfile.objects.select_related('user')}
            drift = 0
            for uid, p in profiles.items():
                e = expected.get(uid, {'tasks': 0, 'cp': 0, 'seconds': 0})
                diff = (p.geoattempts_done != e['tasks'] or p.controlPointsDone != e['cp']
                        or p.time_spent != e['seconds'])
                if not diff:
                    continue
                drift += 1
                show(f"profile {p.user.username}: tasks {p.geoattempts_done}->{e['tasks']} "
                     f"cp {p.controlPointsDone}->{e['cp']} time {p.time_spent}->{e['seconds']}")
                if apply:
                    p.geoattempts_done, p.controlPointsDone, p.time_spent = e['tasks'], e['cp'], e['seconds']
                    p.save(update_fields=['geoattempts_done', 'controlPointsDone', 'time_spent'])
            missing_profiles = [uid for uid in expected if uid not in profiles]
            summary['profiles_drifted'] = drift
            summary['users_without_profile'] = len(missing_profiles)
            summary['cp_expected_total'] = sum(e['cp'] for e in expected.values())
            summary['cp_stored_total'] = sum(p.controlPointsDone for p in profiles.values())

            # ── GeoAttemptsByUserByDay ───────────────────────────────
            exp_daily = expected_daily_counts()
            rows = {(r.user_id, r.date): r for r in GeoAttemptsByUserByDay.objects.all()}
            d_changed = d_created = d_deleted = 0
            for key, n in exp_daily.items():
                r = rows.get(key)
                if r is None:
                    d_created += 1
                    show(f"daily {key[0]} {key[1]}: missing -> {n}")
                    if apply:
                        GeoAttemptsByUserByDay.objects.create(user_id=key[0], date=key[1], numberGeoAttempts=n)
                elif r.numberGeoAttempts != n:
                    d_changed += 1
                    show(f"daily {key[0]} {key[1]}: {r.numberGeoAttempts} -> {n}")
                    if apply:
                        r.numberGeoAttempts = n
                        r.save(update_fields=['numberGeoAttempts'])
            for key, r in rows.items():
                if key not in exp_daily:
                    d_deleted += 1
                    show(f"daily {key[0]} {key[1]}: {r.numberGeoAttempts} -> delete")
                    if apply:
                        r.delete()
            summary['daily_changed'] = d_changed
            summary['daily_created'] = d_created
            summary['daily_deleted'] = d_deleted

            # ── ChallengeParticipant ─────────────────────────────────
            c_drift = 0
            for ch in Challenge.objects.all():
                for p in ch.participants.select_related('user'):
                    cp = expected_participant_cp(p, ch)
                    if cp != p.cached_cp_count:
                        c_drift += 1
                        show(f"challenge '{ch.name}' {p.user.username}: cp {p.cached_cp_count} -> {cp}")
                        if apply_ch:
                            p.cached_cp_count = cp
                            p.save(update_fields=['cached_cp_count'])
            summary['participants_drifted'] = c_drift
            summary['participants_applied'] = apply_ch

            if not apply:
                transaction.set_rollback(True)

        mode = 'APPLIED' if apply else 'DRY RUN'
        self.stdout.write(f"[{mode}] " + ' '.join(f"{k}={v}" for k, v in summary.items()))
        return None
