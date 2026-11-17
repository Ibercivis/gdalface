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


class NewsletterUnsubscribeTests(TestCase):
    """Per-recipient unsubscribe link and the bulk sender honouring it."""

    def _profile(self, username, **fields):
        user = make_user(username)
        p = UserProfile.objects.get(user=user)
        p.ensure_newsletter_token()
        for k, v in fields.items():
            setattr(p, k, v)
        p.save()
        return p

    def test_get_only_confirms(self):
        p = self._profile('a', newsletter_subscribed=True)
        r = self.client.get(f'/newsletter/unsubscribe/{p.newsletter_token}/')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context['confirm'])
        p.refresh_from_db()
        self.assertTrue(p.newsletter_subscribed)
        self.assertIsNone(p.newsletter_unsubscribed_at)

    def test_post_unsubscribes_even_if_never_subscribed(self):
        p = self._profile('b')  # newsletter_subscribed defaults to False
        old = p.newsletter_token
        r = self.client.post(f'/newsletter/unsubscribe/{old}/')
        self.assertEqual(r.status_code, 200)
        p.refresh_from_db()
        self.assertIsNotNone(p.newsletter_unsubscribed_at)
        self.assertNotEqual(p.newsletter_token, old)

    def test_one_click_post_without_csrf(self):
        from django.test import Client
        p = self._profile('c', newsletter_subscribed=True)
        r = Client(enforce_csrf_checks=True).post(
            f'/newsletter/unsubscribe/{p.newsletter_token}/',
            data='List-Unsubscribe=One-Click', content_type='application/x-www-form-urlencoded')
        self.assertEqual(r.status_code, 200)
        p.refresh_from_db()
        self.assertFalse(p.newsletter_subscribed)

    def test_unknown_token(self):
        r = self.client.post('/newsletter/unsubscribe/nope/')
        self.assertTrue(r.context['unknown'])

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_bulk_skips_unsubscribed_filters_team_and_sets_headers(self):
        import tempfile, os
        from django.core import mail
        from django.core.management import call_command
        from django.utils import timezone
        from teams.models import Team, TeamMembership

        keep = self._profile('keep')
        gone = self._profile('gone', newsletter_unsubscribed_at=timezone.now())
        back = self._profile('back', newsletter_unsubscribed_at=timezone.now(), newsletter_subscribed=True)
        outsider = self._profile('outsider')
        team = Team.objects.create(name='T', creator=keep.user)
        for p in (keep, gone, back):
            TeamMembership.objects.create(team=team, user=p.user)

        with tempfile.NamedTemporaryFile('w', suffix='.html', delete=False) as f:
            f.write('<html><body><a href="[unsubscribe_url]">x</a></body></html>')
        try:
            call_command('send_bulk_email', f.name, '--subject', 's', '--team', team.slug, '--sleep', '0')
        finally:
            os.unlink(f.name)

        self.assertEqual(sorted(m.to[0] for m in mail.outbox), ['back@example.com', 'keep@example.com'])
        m = next(m for m in mail.outbox if m.to[0] == 'keep@example.com')
        self.assertIn(f'/newsletter/unsubscribe/{keep.newsletter_token}/', m.alternatives[0][0])
        self.assertIn(keep.newsletter_token, m.extra_headers['List-Unsubscribe'])
        self.assertEqual(m.extra_headers['List-Unsubscribe-Post'], 'List-Unsubscribe=One-Click')
