"""
Tests for the task submit endpoint (PATCH /api/v1/geoattempt-individual/<pk>/).

Regression coverage for the 2026-05 → 2026-10 data loss: the client sends
`control_points`, the model field is `controlPoints`, and nothing mapped one to
the other, so every DONE submit persisted an empty list.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from georeferencing.models import (
    Batch, Image, GeoAttempt, GeoAttemptsByUserByDay, Challenge, ChallengeParticipant,
)
from user_profile.models import UserProfile

User = get_user_model()

POINTS = [
    {'id': 'Point 1', 'px': 10, 'py': 10, 'actualPx': 100, 'actualPy': 100, 'lat': 40.0, 'lon': -3.0},
    {'id': 'Point 2', 'px': 20, 'py': 20, 'actualPx': 200, 'actualPy': 200, 'lat': 40.1, 'lon': -3.1},
    {'id': 'Point 3', 'px': 30, 'py': 30, 'actualPx': 300, 'actualPy': 300, 'lat': 40.2, 'lon': -3.2},
]


class SubmitEndpointTests(TestCase):

    def setUp(self):
        self.staff = User.objects.create_user('staff', 's@example.org', 'pw', is_staff=True)
        self.alice = User.objects.create_user('alice', 'a@example.org', 'pw')
        self.bob = User.objects.create_user('bob', 'b@example.org', 'pw')
        self.batch = Batch.objects.create(name='B', user=self.staff)
        self.image = Image.objects.create(name='ISS000-E-1.JPG', batch=self.batch,
                                          photoCenterPoint='40.0,-3.0',
                                          status='DOWNLOADED_GENERATED')

    def _assigned(self, user=None, minutes_ago=5):
        return GeoAttempt.objects.create(
            image=self.image, status='ASSIGNED', assignedUser=user,
            assignedDateTime=timezone.now() - timedelta(minutes=minutes_ago),
            controlPoints=[],
        )

    def _url(self, ga):
        return reverse('geoattempt-individual', args=[ga.pk])

    def _submit(self, ga, key='control_points', points=POINTS):
        return self.client.patch(self._url(ga), {key: points, 'status': 'DONE'},
                                 content_type='application/json')

    # ── The regression ────────────────────────────────────────────────
    def test_control_points_snake_case_are_persisted(self):
        ga = self._assigned()
        r = self._submit(ga, key='control_points')
        self.assertEqual(r.status_code, 200, r.content)
        ga.refresh_from_db()
        self.assertEqual(ga.status, 'DONE')
        self.assertEqual(len(ga.controlPoints), 3)
        self.assertEqual(ga.controlPoints[0]['lat'], 40.0)
        self.assertIsNotNone(ga.finishedDateTime)

    def test_control_points_camel_case_still_accepted(self):
        ga = self._assigned()
        self.assertEqual(self._submit(ga, key='controlPoints').status_code, 200)
        ga.refresh_from_db()
        self.assertEqual(len(ga.controlPoints), 3)

    def test_profile_counters_match_persisted_points(self):
        self.client.force_login(self.alice)
        ga = self._assigned(self.alice)
        self.assertEqual(self._submit(ga).status_code, 200)
        p = UserProfile.objects.get(user=self.alice)
        self.assertEqual(p.geoattempts_done, 1)
        self.assertEqual(p.controlPointsDone, 3)
        self.assertGreater(p.time_spent, 0)
        self.assertEqual(GeoAttemptsByUserByDay.objects.get(user=self.alice).numberGeoAttempts, 1)

    # ── Idempotency / state guard ─────────────────────────────────────
    def test_second_submit_is_refused_and_does_not_inflate_counters(self):
        self.client.force_login(self.alice)
        ga = self._assigned(self.alice)
        self.assertEqual(self._submit(ga).status_code, 200)
        r = self._submit(ga)
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()['task_status'], 'DONE')
        p = UserProfile.objects.get(user=self.alice)
        self.assertEqual(p.geoattempts_done, 1)
        self.assertEqual(p.controlPointsDone, 3)

    def test_submit_on_released_task_is_refused(self):
        ga = self._assigned()
        ga.status = 'PENDING'
        ga.save()
        r = self._submit(ga)
        self.assertEqual(r.status_code, 409)
        ga.refresh_from_db()
        self.assertEqual(ga.status, 'PENDING')

    def test_skip_cannot_wipe_a_finished_task(self):
        ga = self._assigned()
        self.assertEqual(self._submit(ga).status_code, 200)
        r = self.client.patch(self._url(ga), {'status': 'PENDING'}, content_type='application/json')
        self.assertEqual(r.status_code, 409)
        ga.refresh_from_db()
        self.assertEqual(ga.status, 'DONE')
        self.assertEqual(len(ga.controlPoints), 3)

    def test_skip_releases_an_assigned_task(self):
        self.client.force_login(self.alice)
        ga = self._assigned(self.alice)
        r = self.client.patch(self._url(ga), {'status': 'PENDING'}, content_type='application/json')
        self.assertEqual(r.status_code, 200)
        ga.refresh_from_db()
        self.assertEqual(ga.status, 'PENDING')
        self.assertIsNone(ga.assignedUser)
        self.assertEqual(ga.skipped, 1)

    def test_done_without_points_is_refused(self):
        ga = self._assigned()
        r = self._submit(ga, points=[])
        self.assertEqual(r.status_code, 400)
        ga.refresh_from_db()
        self.assertEqual(ga.status, 'ASSIGNED')

    def test_invalid_status_is_400(self):
        ga = self._assigned()
        r = self.client.patch(self._url(ga), {'status': 'BOGUS'}, content_type='application/json')
        self.assertEqual(r.status_code, 400)

    # ── Ownership guard ───────────────────────────────────────────────
    def test_other_user_cannot_submit_my_task(self):
        ga = self._assigned(self.alice)
        self.client.force_login(self.bob)
        self.assertEqual(self._submit(ga).status_code, 403)
        ga.refresh_from_db()
        self.assertEqual(ga.status, 'ASSIGNED')

    def test_anonymous_cannot_submit_a_users_task(self):
        ga = self._assigned(self.alice)
        self.assertEqual(self._submit(ga).status_code, 403)

    def test_staff_can_submit_any_task(self):
        ga = self._assigned(self.alice)
        self.client.force_login(self.staff)
        self.assertEqual(self._submit(ga).status_code, 200)

    def test_anonymous_task_can_be_submitted_anonymously(self):
        ga = self._assigned(None)
        self.assertEqual(self._submit(ga).status_code, 200)
        ga.refresh_from_db()
        self.assertEqual(len(ga.controlPoints), 3)
        self.assertFalse(UserProfile.objects.filter(geoattempts_done__gt=0).exists())

    # ── Cheating check still runs first ───────────────────────────────
    def test_too_fast_submit_is_rejected_without_counters(self):
        self.client.force_login(self.alice)
        ga = self._assigned(self.alice, minutes_ago=0)
        r = self._submit(ga)
        self.assertEqual(r.status_code, 400)
        ga.refresh_from_db()
        self.assertEqual(ga.status, 'ASSIGNED')
        self.assertEqual(UserProfile.objects.get(user=self.alice).cheating, 1)
        self.assertEqual(UserProfile.objects.get(user=self.alice).geoattempts_done, 0)

    # ── Challenge credit respects bbox ────────────────────────────────
    def _challenge(self, **bbox):
        now = timezone.now()
        ch = Challenge.objects.create(
            name='C', batch=self.batch, start_at=now - timedelta(days=1),
            end_at=now + timedelta(days=1), **bbox,
        )
        ChallengeParticipant.objects.create(challenge=ch, user=self.alice)
        return ch

    def test_challenge_credit_when_image_inside_bbox(self):
        ch = self._challenge(bbox_min_lat=39, bbox_max_lat=41, bbox_min_lon=-4, bbox_max_lon=-2)
        self.client.force_login(self.alice)
        self.assertEqual(self._submit(self._assigned(self.alice)).status_code, 200)
        self.assertEqual(ChallengeParticipant.objects.get(challenge=ch).cached_cp_count, 3)

    def test_no_challenge_credit_when_image_outside_bbox(self):
        ch = self._challenge(bbox_min_lat=50, bbox_max_lat=60, bbox_min_lon=0, bbox_max_lon=10)
        self.client.force_login(self.alice)
        self.assertEqual(self._submit(self._assigned(self.alice)).status_code, 200)
        self.assertEqual(ChallengeParticipant.objects.get(challenge=ch).cached_cp_count, 0)


class ReleaseAbandonedTests(TestCase):
    def test_update_assigned_clears_user_and_timestamps(self):
        from georeferencing.tasks import update_assigned
        staff = User.objects.create_user('s', 's@example.org', 'pw', is_staff=True)
        u = User.objects.create_user('u', 'u@example.org', 'pw')
        img = Image.objects.create(name='x.JPG', batch=Batch.objects.create(name='B', user=staff))
        stale = GeoAttempt.objects.create(image=img, status='ASSIGNED', assignedUser=u,
                                          assignedDateTime=timezone.now() - timedelta(hours=7), numberTries=2)
        fresh = GeoAttempt.objects.create(image=img, status='ASSIGNED', assignedUser=u,
                                          assignedDateTime=timezone.now() - timedelta(hours=1))
        update_assigned()
        stale.refresh_from_db(); fresh.refresh_from_db()
        self.assertEqual((stale.status, stale.assignedUser, stale.assignedDateTime, stale.numberTries),
                         ('PENDING', None, None, 0))
        self.assertEqual(fresh.status, 'ASSIGNED')


class ReconcileCountersTests(TestCase):
    """The reconcile_counters command recomputes every cached counter from DONE rows."""

    def setUp(self):
        from io import StringIO
        self.out = StringIO()
        staff = User.objects.create_user('s', 's@example.org', 'pw', is_staff=True)
        self.u = User.objects.create_user('u', 'u@example.org', 'pw')
        self.batch = Batch.objects.create(name='B', user=staff)
        self.img_in = Image.objects.create(name='in.JPG', batch=self.batch, photoCenterPoint='40,-3')
        self.img_out = Image.objects.create(name='out.JPG', batch=self.batch, photoCenterPoint='55,5')
        now = timezone.now()
        self.ch = Challenge.objects.create(
            name='C', batch=self.batch, start_at=now - timedelta(days=5), end_at=now + timedelta(days=5),
            bbox_min_lat=39, bbox_max_lat=41, bbox_min_lon=-4, bbox_max_lon=-2,
        )
        self.part = ChallengeParticipant.objects.create(challenge=self.ch, user=self.u, cached_cp_count=999)
        ChallengeParticipant.objects.filter(pk=self.part.pk).update(joined_at=now - timedelta(days=2))

        def done(img, days_ago, n_points, secs=120):
            fin = now - timedelta(days=days_ago)
            return GeoAttempt.objects.create(
                image=img, status='DONE', assignedUser=self.u,
                assignedDateTime=fin - timedelta(seconds=secs), finishedDateTime=fin,
                controlPoints=[{'lat': 40.0, 'lon': -3.0}] * n_points,
            )
        done(self.img_in, 1, 4)          # counts for challenge (in window, in bbox)
        done(self.img_in, 3, 5)          # before joined_at → not for challenge
        done(self.img_out, 1, 6)         # outside bbox → not for challenge
        GeoAttempt.objects.create(image=self.img_in, status='DONE', finishedDateTime=now,
                                  controlPoints=[{'lat': 1, 'lon': 1}])  # anonymous, ignored
        # Drifted stored values
        UserProfile.objects.filter(user=self.u).update(geoattempts_done=1, controlPointsDone=0, time_spent=0)
        GeoAttemptsByUserByDay.objects.create(user=self.u, date=(now - timedelta(days=9)).date(), numberGeoAttempts=7)

    def _run(self, *args):
        from django.core.management import call_command
        call_command('reconcile_counters', *args, stdout=self.out)
        return self.out.getvalue()

    def test_dry_run_reports_but_does_not_write(self):
        out = self._run()
        self.assertIn('[DRY RUN]', out)
        self.assertIn('profiles_drifted=1', out)
        self.assertIn('participants_drifted=1', out)
        self.assertIn('daily_deleted=1', out)
        p = UserProfile.objects.get(user=self.u)
        self.assertEqual((p.geoattempts_done, p.controlPointsDone), (1, 0))
        self.assertEqual(ChallengeParticipant.objects.get(pk=self.part.pk).cached_cp_count, 999)

    def test_apply_without_challenges_flag_leaves_participants_alone(self):
        self._run('--apply')
        self.assertEqual(ChallengeParticipant.objects.get(pk=self.part.pk).cached_cp_count, 999)
        self.assertEqual(UserProfile.objects.get(user=self.u).controlPointsDone, 15)

    def test_apply_fixes_everything(self):
        out = self._run('--apply', '--challenges')
        self.assertIn('[APPLIED]', out)
        p = UserProfile.objects.get(user=self.u)
        self.assertEqual((p.geoattempts_done, p.controlPointsDone, p.time_spent), (3, 15, 360))
        self.assertEqual(ChallengeParticipant.objects.get(pk=self.part.pk).cached_cp_count, 4)
        daily = dict(GeoAttemptsByUserByDay.objects.filter(user=self.u).values_list('date', 'numberGeoAttempts'))
        self.assertEqual(sorted(daily.values()), [1, 2])      # 2 tasks one day ago, 1 three days ago
        self.assertEqual(len(daily), 2)                        # stale 9-days-ago row deleted
        # Second run: nothing left to fix
        out2 = self._run()
        self.assertIn('profiles_drifted=0', out2)
        self.assertIn('participants_drifted=0', out2)
        self.assertIn('daily_changed=0 daily_created=0 daily_deleted=0', out2)

    def test_task_counts_for_one_enrollment_only(self):
        # User moved from C to C2 36 h ago: C's period closed, C2's open.
        from georeferencing.models import ChallengeEnrollmentPeriod
        from georeferencing.reconcile import expected_participant_cp
        now = timezone.now()
        ch2 = Challenge.objects.create(name='C2', batch=self.batch, start_at=now - timedelta(days=5),
                                       end_at=now + timedelta(days=5))
        ChallengeParticipant.objects.filter(pk=self.part.pk).update(left_at=now - timedelta(hours=36))
        p2 = ChallengeParticipant.objects.create(challenge=ch2, user=self.u)
        ChallengeEnrollmentPeriod.objects.create(participant=self.part, joined_at=now - timedelta(days=2),
                                                 left_at=now - timedelta(hours=36))
        ChallengeEnrollmentPeriod.objects.create(participant=p2, joined_at=now - timedelta(hours=36))
        self.part.refresh_from_db()
        # The 4-point task finished 1 day ago is after joining C2 → counts for C2, not C.
        self.assertEqual(expected_participant_cp(self.part), 0)
        self.assertEqual(expected_participant_cp(p2), 4 + 6)  # C2 has no bbox: both images

    def test_admin_recompute_uses_same_rule(self):
        from georeferencing.reconcile import recompute_challenge
        self.assertEqual(recompute_challenge(self.ch), 1)
        self.assertEqual(ChallengeParticipant.objects.get(pk=self.part.pk).cached_cp_count, 4)


class SnapshotSafetyNetTests(TestCase):
    def test_refresh_when_stale_or_missing(self):
        import json, os, tempfile
        from unittest import mock
        from georeferencing import stats, tasks
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'stats.json')
            with mock.patch.object(stats, 'SNAPSHOT_PATH', path):
                self.assertTrue(tasks.refresh_snapshot_if_stale())        # missing → written
                self.assertTrue(os.path.exists(path))
                self.assertFalse(tasks.refresh_snapshot_if_stale())       # fresh → untouched
                old = json.load(open(path))
                old['generated_at'] = (timezone.now() - timedelta(hours=30)).isoformat()
                json.dump(old, open(path, 'w'))
                self.assertTrue(tasks.refresh_snapshot_if_stale())        # stale → rewritten


class EnrollmentPeriodTests(TestCase):
    """join / leave / re-join write ChallengeEnrollmentPeriod rows and the
    reconciliation rule sums CP over those periods."""

    def setUp(self):
        staff = User.objects.create_user('s', 's@example.org', 'pw', is_staff=True)
        self.u = User.objects.create_user('u', 'u@example.org', 'pw')
        self.batch = Batch.objects.create(name='B', user=staff)
        self.img = Image.objects.create(name='a.JPG', batch=self.batch, photoCenterPoint='40,-3')
        now = timezone.now()
        self.c1 = Challenge.objects.create(name='C1', start_at=now - timedelta(days=10), end_at=now + timedelta(days=10))
        self.c2 = Challenge.objects.create(name='C2', start_at=now - timedelta(days=10), end_at=now + timedelta(days=10))
        self.client.force_login(self.u)

    def _join(self, ch):
        return self.client.post(reverse('challenge-join', args=[ch.pk]))

    def _leave(self, ch):
        return self.client.post(reverse('challenge-leave', args=[ch.pk]))

    def _periods(self, ch):
        from georeferencing.models import ChallengeEnrollmentPeriod
        return list(ChallengeEnrollmentPeriod.objects.filter(
            participant__challenge=ch, participant__user=self.u).values_list('joined_at', 'left_at'))

    def test_join_leave_rejoin_keeps_history(self):
        self.assertEqual(self._join(self.c1).status_code, 200)
        self.assertEqual(len(self._periods(self.c1)), 1)
        self.assertIsNone(self._periods(self.c1)[0][1])
        self.assertEqual(self._leave(self.c1).status_code, 200)
        self.assertIsNotNone(self._periods(self.c1)[0][1])
        self.assertEqual(self._join(self.c1).status_code, 200)   # revive
        p = self._periods(self.c1)
        self.assertEqual(len(p), 2)
        self.assertIsNotNone(p[0][1]); self.assertIsNone(p[1][1])

    def test_joining_another_challenge_closes_previous_period(self):
        self._join(self.c1)
        self._join(self.c2)
        self.assertIsNotNone(self._periods(self.c1)[0][1])
        self.assertIsNone(self._periods(self.c2)[0][1])

    def test_reconcile_counts_each_stint_separately(self):
        from georeferencing.models import ChallengeEnrollmentPeriod
        from georeferencing.reconcile import expected_participant_cp
        now = timezone.now()
        p1 = ChallengeParticipant.objects.create(challenge=self.c1, user=self.u, left_at=now)
        # Two stints in C1: days -8..-6 and -3..-1, with a C2 stint in between.
        ChallengeEnrollmentPeriod.objects.create(participant=p1, joined_at=now - timedelta(days=8), left_at=now - timedelta(days=6))
        ChallengeEnrollmentPeriod.objects.create(participant=p1, joined_at=now - timedelta(days=3), left_at=now - timedelta(days=1))
        p2 = ChallengeParticipant.objects.create(challenge=self.c2, user=self.u, left_at=now - timedelta(days=3))
        ChallengeEnrollmentPeriod.objects.create(participant=p2, joined_at=now - timedelta(days=6), left_at=now - timedelta(days=3))

        def done(days_ago, n):
            GeoAttempt.objects.create(image=self.img, status='DONE', assignedUser=self.u,
                                      finishedDateTime=now - timedelta(days=days_ago),
                                      controlPoints=[{'lat': 1, 'lon': 1}] * n)
        done(7, 3)   # C1 first stint
        done(5, 5)   # C2
        done(4, 7)   # C2
        done(2, 11)  # C1 second stint
        done(0.5, 13)  # after leaving everything → nobody
        self.assertEqual(expected_participant_cp(p1), 14)
        self.assertEqual(expected_participant_cp(p2), 12)
