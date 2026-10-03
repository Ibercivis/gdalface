from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from georeferencing import timeseries as ts
from georeferencing.models import Batch, DailyMetric, GeoAttempt, GeoAttemptsByUserByDay, Image

User = get_user_model()


class BucketTests(TestCase):
    def test_ranges_and_buckets(self):
        today = date(2026, 10, 3)  # a Saturday
        s, e, b, labels = ts.buckets_for('7d', today)
        self.assertEqual((b, len(labels), labels[0], labels[-1]), ('day', 7, date(2026, 9, 27), today))
        s, e, b, labels = ts.buckets_for('1y', today)
        self.assertEqual(b, 'week'); self.assertEqual(labels[0].weekday(), 0); self.assertEqual(len(labels), 53)
        s, e, b, labels = ts.buckets_for('4y', today)
        self.assertEqual(b, 'month'); self.assertEqual(labels[0], date(2022, 10, 1)); self.assertEqual(len(labels), 49)
        self.assertEqual(ts.buckets_for('bogus', today)[2], 'day')


class SeriesTests(TestCase):
    def setUp(self):
        staff = User.objects.create_user('s', 's@x.org', 'pw', is_staff=True)
        self.u = User.objects.create_user('u', 'u@x.org', 'pw')
        img = Image.objects.create(name='i.JPG', batch=Batch.objects.create(name='B', user=staff))
        now = timezone.now()
        for days_ago, who in ((0, self.u), (1, self.u), (1, None), (10, self.u), (400, self.u)):
            GeoAttempt.objects.create(image=img, status='DONE', assignedUser=who,
                                      finishedDateTime=now - timedelta(days=days_ago), controlPoints=[{'lat': 1, 'lon': 1}])
        GeoAttempt.objects.create(image=img, status='PENDING')
        GeoAttemptsByUserByDay.objects.create(user=self.u, date=now.date(), numberGeoAttempts=1)
        GeoAttemptsByUserByDay.objects.create(user=self.u, date=now.date() - timedelta(days=1), numberGeoAttempts=1)

    def test_event_series_by_day(self):
        s = ts.series('7d')
        self.assertEqual(sum(s['events']['contributions']), 3)
        self.assertEqual(s['events']['contributions'][-1], 1)
        self.assertEqual(s['events']['contributions_anonymous'][-2], 1)
        self.assertEqual(s['events']['active_users'][-1], 1)
        self.assertEqual(s['totals']['contributions'], 3)
        self.assertEqual(s['prev_totals']['contributions'], 1)   # the 10-day-old one is in the previous week
        self.assertEqual(ts.series('30d')['prev_totals']['contributions'], 0)
        self.assertEqual(ts.series('30d')['totals']['contributions'], 4)

    def test_weekly_and_monthly_buckets_sum_everything_in_range(self):
        self.assertEqual(sum(ts.series('1y')['events']['contributions']), 4)
        self.assertEqual(sum(ts.series('4y')['events']['contributions']), 5)

    def test_record_and_state_series(self):
        today = timezone.now().date()
        n = ts.record_daily_metrics(today)
        self.assertEqual(n, len(ts.STATE_KEYS))
        row = DailyMetric.objects.get(date=today, key='tasks_pending')
        self.assertEqual(row.value, 1)
        ts.record_daily_metrics(today)  # idempotent upsert
        self.assertEqual(DailyMetric.objects.filter(date=today, key='tasks_pending').count(), 1)
        self.assertFalse(ts.record_daily_metrics_if_missing(today))
        s = ts.series('7d')
        self.assertEqual(s['states']['tasks_pending'][-1], 1)
        self.assertEqual(s['states']['tasks_done'][-1], 5)
        self.assertIsNone(s['states']['tasks_pending'][0])

    def test_backfill_reconstructs_history(self):
        yesterday = timezone.now().date() - timedelta(days=1)
        n = ts.backfill_daily_metrics(start=yesterday - timedelta(days=2), end=yesterday)
        self.assertEqual(n, 3 * 8)
        self.assertEqual(DailyMetric.objects.get(date=yesterday, key='tasks_done').value, 4)  # all but today's
        self.assertEqual(DailyMetric.objects.get(date=yesterday, key='active_7').value, 1)
        self.assertEqual(DailyMetric.objects.get(date=yesterday, key='users_total').value, 0)  # both joined today


class SeriesEndpointTests(TestCase):
    def test_staff_only_json(self):
        staff = User.objects.create_user('s', 's@x.org', 'pw', is_staff=True)
        self.assertEqual(self.client.get(reverse('staff_stats_series')).status_code, 302)
        self.client.force_login(staff)
        r = self.client.get(reverse('staff_stats_series'), {'range': '1y'})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body['bucket'], 'week')
        self.assertEqual(len(body['labels']), len(body['events']['contributions']))
        self.assertIn('tasks_pending', body['states'])


class CohortTests(TestCase):
    def test_weekly_cohorts(self):
        from georeferencing.models import GeoAttemptsByUserByDay
        today = timezone.now().date()
        joined = timezone.now() - timedelta(days=20)
        a = User.objects.create_user('a', 'a@x.org', 'pw'); b = User.objects.create_user('b', 'b@x.org', 'pw')
        User.objects.filter(pk__in=[a.pk, b.pk]).update(date_joined=joined)
        GeoAttemptsByUserByDay.objects.create(user=a, date=joined.date() + timedelta(days=2), numberGeoAttempts=1)   # P1
        GeoAttemptsByUserByDay.objects.create(user=a, date=joined.date() + timedelta(days=9), numberGeoAttempts=1)   # P2
        c = ts.cohorts('30d', today)
        self.assertEqual(c['unit'], 'week')
        row = next(r for r in c['rows'] if r['size'] == 2)
        self.assertEqual((row['ever_pct'], row['first_pct']), (50, 50))
        self.assertEqual(row['periods'][0], 50)
        self.assertEqual(row['periods'][1], 50)
        self.assertIsNone(row['periods'][3])  # 4th week not elapsed for the whole cohort
        self.assertIn('cohorts', ts.series('30d', today))

    def test_monthly_cohorts_for_long_ranges(self):
        self.assertEqual(ts.cohorts('1y')['unit'], 'month')
