"""georeferencing.metrics: the single source for every user-facing number."""
from datetime import timedelta

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from georeferencing import metrics
from georeferencing.models import Batch, GeoAttempt, GeoAttemptsByUserByDay, Image
from user_profile.models import UserProfile

User = get_user_model()


def verify(user):
    EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)


class MetricsTests(TestCase):
    def setUp(self):
        staff = User.objects.create_user('s', 's@x.org', 'pw', is_staff=True)
        self.a = User.objects.create_user('a', 'a@x.org', 'pw'); verify(self.a)
        self.b = User.objects.create_user('b', 'b@x.org', 'pw'); verify(self.b)
        self.c = User.objects.create_user('c', 'c@x.org', 'pw')  # unverified
        UserProfile.objects.filter(user=self.a).update(geoattempts_done=5, controlPointsDone=50, time_spent=500)
        UserProfile.objects.filter(user=self.b).update(geoattempts_done=5, controlPointsDone=20, time_spent=900)
        UserProfile.objects.filter(user=self.c).update(geoattempts_done=99, controlPointsDone=999, time_spent=9)
        img = Image.objects.create(name='i.JPG', batch=Batch.objects.create(name='B', user=staff))
        now = timezone.now()
        for who, n in ((self.a, 3), (self.b, 4), (None, 2)):
            GeoAttempt.objects.create(image=img, status='DONE', assignedUser=who,
                                      assignedDateTime=now - timedelta(seconds=100), finishedDateTime=now,
                                      controlPoints=[{'lat': 1, 'lon': 1}] * n)
        GeoAttempt.objects.create(image=img, status='PENDING')

    def test_population_is_verified_users_only(self):
        self.assertEqual(metrics.participants(use_cache=False), 2)
        self.assertEqual(set(metrics.population().values_list('user_id', flat=True)), {self.a.id, self.b.id})

    def test_project_totals_include_anonymous(self):
        t = metrics.project_totals(use_cache=False)
        self.assertEqual(t['tasks_done'], 3)
        self.assertEqual(t['tasks_total'], 4)
        self.assertEqual(t['control_points'], 9)
        self.assertEqual(t['anonymous_done'], 1)
        self.assertEqual(t['contributors'], 2)
        self.assertEqual(t['seconds'], 300)
        self.assertEqual(t['images_georeferenced'], 1)
        self.assertEqual(t['participants'], 2)
        self.assertEqual(t['completion_pct'], 75.0)

    def test_rank_ignores_unverified_and_shares_ties(self):
        pa, pb, pc = (UserProfile.objects.get(user=u) for u in (self.a, self.b, self.c))
        self.assertEqual(metrics.global_rank(pa, 'cp')['rank'], 1)      # c (999) is not in population
        r = metrics.global_rank(pb, 'cp')
        self.assertEqual((r['rank'], r['total'], r['to_next'], r['to_first']), (2, 2, 30, 30))
        self.assertEqual(metrics.global_rank(pa, 'tasks')['rank'], 1)   # tie 5/5 → both #1
        self.assertEqual(metrics.global_rank(pb, 'tasks')['rank'], 1)
        self.assertEqual(metrics.global_rank(pa, 'time')['rank'], 2)
        rc = metrics.global_rank(pc, 'cp')
        self.assertEqual(rc['rank'], 1)
        self.assertFalse(rc['in_population'])

    def test_streak(self):
        today = timezone.now().date()
        for d in (1, 2, 3, 6):
            GeoAttemptsByUserByDay.objects.create(user=self.a, date=today - timedelta(days=d), numberGeoAttempts=1)
        self.assertEqual(metrics.streak(self.a), (3, 3))                       # yesterday..3 days ago, today tolerated
        self.assertEqual(metrics.streak(self.a, tolerate_today=False), (0, 3))
        GeoAttemptsByUserByDay.objects.create(user=self.a, date=today, numberGeoAttempts=1)
        self.assertEqual(metrics.streak(self.a), (4, 4))

    def test_active_users(self):
        today = timezone.now().date()
        GeoAttemptsByUserByDay.objects.create(user=self.a, date=today - timedelta(days=3), numberGeoAttempts=1)
        GeoAttemptsByUserByDay.objects.create(user=self.c, date=today, numberGeoAttempts=1)  # unverified
        GeoAttemptsByUserByDay.objects.create(user=self.b, date=today - timedelta(days=20), numberGeoAttempts=1)
        self.assertEqual(metrics.active_users(7), 1)
        self.assertEqual(metrics.active_users(30), 2)
