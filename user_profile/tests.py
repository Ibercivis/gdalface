from datetime import date, timedelta

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings

from georeferencing.models import GeoAttemptsByUserByDay
from user_profile.models import UserProfile

User = get_user_model()


def make_user(username, cp=0, tasks=0, country='', visible=True, verified=True):
    user = User.objects.create_user(
        username=username, email=f'{username}@example.com', password='x',
    )
    # A post_save signal may have created the profile already.
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.controlPointsDone = cp
    profile.geoattempts_done = tasks
    profile.country = country
    profile.visible = visible
    profile.save()
    if verified:
        EmailAddress.objects.create(
            user=user, email=user.email, verified=True, primary=True,
        )
    return user


LOCMEM_CACHE = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                            'LOCATION': 'user-profile-tests'}}


@override_settings(CACHES=LOCMEM_CACHE)
class CountryRankingApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.a = make_user('a', cp=100, tasks=10, country='ES')
        self.b = make_user('b', cp=60, tasks=20, country='ES')
        self.c = make_user('c', cp=120, tasks=5, country='IT')
        # Must not score: no country / unverified. Invisible users DO count
        # for their country (they are never named, only aggregated).
        make_user('d', cp=999, tasks=99)
        make_user('e', cp=50, tasks=1, country='FR', visible=False)
        make_user('f', cp=999, tasks=99, country='DE', verified=False)

    def test_aggregates_and_ordering_by_cp(self):
        data = self.client.get('/api/v1/ranking/countries/').json()
        self.assertEqual(data['total_countries'], 3)
        fr = next(r for r in data['rows'] if r['country_code'] == 'fr')
        self.assertEqual((fr['control_points'], fr['users']), (50, 1))
        es = next(r for r in data['rows'] if r['country_code'] == 'es')
        it = next(r for r in data['rows'] if r['country_code'] == 'it')
        self.assertEqual(es['control_points'], 160)
        self.assertEqual(es['users'], 2)
        self.assertEqual(es['cp_per_user'], 80.0)
        self.assertEqual(it['control_points'], 120)
        self.assertEqual(data['rows'][0]['country_code'], 'es')

    def test_ordering_per_user_puts_italy_first(self):
        data = self.client.get('/api/v1/ranking/countries/?ordering=cp_per_user').json()
        self.assertEqual(data['rows'][0]['country_code'], 'it')  # 120 > 80

    def test_my_country_flags(self):
        self.client.force_login(self.a)
        data = self.client.get('/api/v1/ranking/countries/').json()
        self.assertEqual(data['my_country_code'], 'es')
        self.assertEqual(data['my_country_rank'], 1)
        self.assertFalse(data['my_country_missing'])

        self.client.force_login(User.objects.get(username='d'))
        data = self.client.get('/api/v1/ranking/countries/').json()
        self.assertTrue(data['my_country_missing'])


@override_settings(CACHES=LOCMEM_CACHE)
class PeriodRankingApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.a = make_user('a', cp=100, tasks=1000)
        self.b = make_user('b', cp=50, tasks=2)
        today = date.today()
        # b did more than a *this week* despite a's huge lifetime counters.
        GeoAttemptsByUserByDay.objects.create(
            user=self.a, date=today, numberGeoAttempts=3)
        GeoAttemptsByUserByDay.objects.create(
            user=self.b, date=today, numberGeoAttempts=7)
        GeoAttemptsByUserByDay.objects.create(
            user=self.b, date=today - timedelta(days=40), numberGeoAttempts=100)

    def test_week_ranks_by_recent_tasks_only(self):
        data = self.client.get('/api/v1/ranking/?period=week').json()
        self.assertEqual(data['ordering'], 'tasks')
        self.assertEqual(data['rows'][0]['username'], 'b')
        self.assertEqual(data['rows'][0]['tasks'], 7)
        self.assertEqual(data['rows'][0]['control_points'], 0)  # per-day CP now tracked

    def test_week_can_rank_by_control_points(self):
        GeoAttemptsByUserByDay.objects.filter(user=self.a, date=date.today()).update(controlPoints=40)
        GeoAttemptsByUserByDay.objects.filter(user=self.b, date=date.today()).update(controlPoints=9)
        data = self.client.get('/api/v1/ranking/?period=week&ordering=cp').json()
        self.assertEqual(data['ordering'], 'cp')
        self.assertEqual(data['rows'][0]['username'], 'a')
        self.assertEqual(data['rows'][0]['control_points'], 40)

    def test_month_includes_only_window(self):
        data = self.client.get('/api/v1/ranking/?period=month').json()
        b_row = next(r for r in data['rows'] if r['username'] == 'b')
        self.assertEqual(b_row['tasks'], 7)  # the 40-day-old 100 is outside

    def test_jump_to_me_in_period(self):
        self.client.force_login(self.a)
        data = self.client.get('/api/v1/ranking/?period=week&jump_to_me=1').json()
        self.assertEqual(data['my_rank'], 2)
        self.assertEqual(data['my_metric'], 3)

    def test_all_time_still_works(self):
        data = self.client.get('/api/v1/ranking/').json()
        self.assertEqual(data['period'], 'all')
        self.assertEqual(data['rows'][0]['username'], 'a')
