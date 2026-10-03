"""
Tests for the frontend app, mostly the contact-form anti-spam layers.
"""
import time
from unittest import mock

from django.core import mail, signing
from django.test import TestCase, override_settings
from django.urls import reverse

from frontend import views

LOCMEM_CACHE = {
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                'LOCATION': 'frontend-tests'}
}


def _tokens(age=10):
    """Signed token pair as the view would have issued ``age`` seconds ago."""
    t = time.time() - age
    return {
        'started_at': signing.dumps(t, salt=views._CONTACT_SALT),
        'form_token': signing.dumps(t, salt=views._CONTACT_JS_SALT),
    }


def _payload(**over):
    data = {
        'name': 'Ana', 'email': 'ana@example.org',
        'subject': 'Hola', 'message': 'Me gusta el proyecto.',
        'website': '',
    }
    data.update(_tokens())
    data.update(over)
    return data


@override_settings(CACHES=LOCMEM_CACHE, TURNSTILE_SITE_KEY='', TURNSTILE_SECRET_KEY='',
                   DEFAULT_TO_EMAIL=('to@example.org',), DEFAULT_FROM_EMAIL='from@example.org')
class ContactAntiSpamTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.url = reverse('contact')

    # ── the actual spam hole ─────────────────────────────────────────
    def test_index_rejects_post(self):
        r = self.client.post('/', _payload())
        self.assertEqual(r.status_code, 405)
        self.assertEqual(len(mail.outbox), 0)

    # ── happy path ───────────────────────────────────────────────────
    def test_get_renders_tokens(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'name="started_at"')
        self.assertContains(r, 'name="form_token"')
        self.assertContains(r, 'data-k="')
        self.assertNotContains(r, 'cf-turnstile')

    def test_valid_submission_sends_mail(self):
        r = self.client.post(self.url, _payload(), follow=True)
        self.assertEqual(len(mail.outbox), 1)
        m = mail.outbox[0]
        self.assertEqual(m.subject, '[Lost at Night] Hola')
        self.assertEqual(m.reply_to, ['ana@example.org'])
        self.assertEqual(m.to, ['to@example.org'])
        self.assertContains(r, 'sent successfully')

    def test_missing_field_shows_error(self):
        r = self.client.post(self.url, _payload(message=''))
        self.assertEqual(len(mail.outbox), 0)
        self.assertContains(r, 'Please fill all required fields')

    # ── silent drops: fake success, no mail ──────────────────────────
    def _assert_silently_dropped(self, data, **extra):
        r = self.client.post(self.url, data, follow=True, **extra)
        self.assertEqual(len(mail.outbox), 0)
        self.assertContains(r, 'be in touch soon')

    def test_honeypot(self):
        self._assert_silently_dropped(_payload(website='http://spam.example'))

    def test_too_fast(self):
        self._assert_silently_dropped(_payload(**_tokens(age=0.5)))

    def test_stale_token(self):
        self._assert_silently_dropped(_payload(**_tokens(age=7 * 3600)))

    def test_forged_timestamp(self):
        self._assert_silently_dropped(_payload(started_at=str(time.time() - 60)))

    def test_js_token_from_other_issue(self):
        a, b = _tokens(age=30), _tokens(age=10)
        self._assert_silently_dropped(_payload(started_at=a['started_at'], form_token=b['form_token']))

    def test_garbage_js_token(self):
        self._assert_silently_dropped(_payload(form_token='1'))

    def test_too_many_urls(self):
        self._assert_silently_dropped(_payload(
            message='see http://a.example and https://b.example and www.c.example'))

    def test_url_in_name(self):
        self._assert_silently_dropped(_payload(name='https://seo.example'))

    @override_settings(CONTACT_RATE_LIMIT=2)
    def test_rate_limit_per_ip(self):
        for _ in range(2):
            self.client.post(self.url, _payload(), REMOTE_ADDR='10.0.0.1')
        self.assertEqual(len(mail.outbox), 2)
        mail.outbox.clear()
        self._assert_silently_dropped(_payload(), REMOTE_ADDR='10.0.0.1')  # 3rd → dropped
        # A different client is unaffected.
        self.client.post(self.url, _payload(), HTTP_X_FORWARDED_FOR='10.0.0.2, 127.0.0.1')
        self.assertEqual(len(mail.outbox), 1)

    # ── explicit errors (humans can act on these) ────────────────────
    def test_no_js_gets_hint(self):
        r = self.client.post(self.url, _payload(form_token=''))
        self.assertEqual(len(mail.outbox), 0)
        self.assertContains(r, 'enable JavaScript')

    @override_settings(TURNSTILE_SITE_KEY='site', TURNSTILE_SECRET_KEY='secret')
    def test_turnstile_rendered_and_verified(self):
        r = self.client.get(self.url)
        self.assertContains(r, 'cf-turnstile')
        self.assertContains(r, 'data-sitekey="site"')

        with mock.patch('requests.post') as post:
            post.return_value.json.return_value = {'success': False}
            r = self.client.post(self.url, _payload(**{'cf-turnstile-response': 'tok'}))
            self.assertEqual(len(mail.outbox), 0)
            self.assertContains(r, 'Captcha verification failed')

            post.return_value.json.return_value = {'success': True}
            self.client.post(self.url, _payload(**{'cf-turnstile-response': 'tok'}))
            self.assertEqual(len(mail.outbox), 1)
            self.assertEqual(post.call_args.kwargs['data']['secret'], 'secret')

    @override_settings(TURNSTILE_SITE_KEY='site', TURNSTILE_SECRET_KEY='secret')
    def test_turnstile_missing_token_fails(self):
        r = self.client.post(self.url, _payload())
        self.assertEqual(len(mail.outbox), 0)
        self.assertContains(r, 'Captcha verification failed')


@override_settings(CACHES=LOCMEM_CACHE)
class StaffStatsTests(TestCase):
    """Access control + rendering of the staff control panel (/stats/)."""

    @classmethod
    def setUpTestData(cls):
        from datetime import timedelta
        from django.contrib.auth import get_user_model
        from django.utils import timezone
        from georeferencing.models import (
            Batch, Image, GeoAttempt, GeoAttemptsByUserByDay, Challenge,
            ChallengeParticipant, StatsEvent,
        )
        User = get_user_model()
        cls.staff = User.objects.create_user('staff', 's@example.org', 'pw', is_staff=True)
        cls.plain = User.objects.create_user('plain', 'p@example.org', 'pw')
        now = timezone.now()
        batch = Batch.objects.create(name='B1', user=cls.staff)
        img = Image.objects.create(name='ISS000-E-1', batch=batch,
                                   photoCenterPoint='40.0,-3.0', status='DOWNLOADED_GENERATED')
        done = GeoAttempt.objects.create(image=img, status='DONE', assignedUser=cls.plain,
                                         assignedDateTime=now - timedelta(minutes=10),
                                         finishedDateTime=now - timedelta(minutes=5))
        GeoAttempt.objects.create(image=img, status='DONE', finishedDateTime=now)  # anonymous
        GeoAttempt.objects.create(image=img, status='PENDING')
        GeoAttempt.objects.create(image=img, status='ASSIGNED',
                                  assignedDateTime=now - timedelta(hours=10))  # stale
        GeoAttemptsByUserByDay.objects.create(user=cls.plain, date=now.date(), numberGeoAttempts=1)
        cls.challenge = Challenge.objects.create(
            name='Open one', batch=batch, start_at=now - timedelta(days=3),
            end_at=now + timedelta(days=10), target_bronze=10, target_silver=20, target_gold=30,
        )
        ChallengeParticipant.objects.create(challenge=cls.challenge, user=cls.plain,
                                            cached_cp_count=12)
        # Backdate the enrollment so the DONE task above falls inside it.
        ChallengeParticipant.objects.filter(challenge=cls.challenge).update(
            joined_at=now - timedelta(days=2))
        Challenge.objects.create(
            name='Finished', start_at=now - timedelta(days=30), end_at=now - timedelta(days=1),
        )
        StatsEvent.objects.create(title='Newsletter sent', kind='email', created_by=cls.staff)

    def test_anonymous_is_redirected_to_login(self):
        r = self.client.get(reverse('staff_stats'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login', r['Location'])

    def test_non_staff_is_redirected(self):
        self.client.force_login(self.plain)
        self.assertEqual(self.client.get(reverse('staff_stats')).status_code, 302)
        self.assertEqual(self.client.get(reverse('staff_stats_csv')).status_code, 302)
        self.assertEqual(self.client.get(reverse('staff_stats_series')).status_code, 302)

    def test_staff_sees_dashboard_with_open_challenge(self):
        self.client.force_login(self.staff)
        r = self.client.get(reverse('staff_stats'), {'range': '30d'})
        self.assertEqual(r.status_code, 200)
        d = r.context['d']
        self.assertEqual(d['people']['active_7'], 1)
        self.assertEqual(d['contributions']['total'], 2)
        self.assertEqual(d['contributions']['anonymous_total'], 1)
        self.assertEqual(d['queue']['pending'], 1)
        self.assertEqual(d['health']['stale_assigned'], 1)
        self.assertEqual(len(d['challenges']['open']), 1)
        ch = d['challenges']['open'][0]
        self.assertEqual(ch['status'], 'active')
        self.assertEqual(ch['total_cp'], 12)
        self.assertEqual(ch['tasks_done'], 1)        # only the enrolled user's task
        self.assertEqual(ch['tasks_pending'], 1)
        self.assertEqual(ch['next_tier'], {'label': 'silver', 'remaining': 8})
        self.assertEqual(len(d['challenges']['finished']), 1)
        self.assertEqual(len(d['events']), 1)
        self.assertContains(r, 'Newsletter sent')
        self.assertContains(r, 'chart-ch-%d' % self.challenge.id)

    def test_staff_can_add_and_delete_events(self):
        from georeferencing.models import StatsEvent
        self.client.force_login(self.staff)
        r = self.client.post(reverse('staff_stats'), {
            'happened_at': '2026-09-30', 'kind': 'campaign', 'title': 'Launch',
            'url': 'https://example.org/post', 'note': 'first wave',
        })
        self.assertEqual(r.status_code, 302)
        ev = StatsEvent.objects.get(title='Launch')
        self.assertEqual(ev.kind, 'campaign')
        self.assertEqual(ev.happened_at.date().isoformat(), '2026-09-30')
        self.assertEqual(ev.created_by, self.staff)
        self.assertEqual(self.client.post(reverse('staff_stats'), {'title': ''}).status_code, 400)
        self.client.post(reverse('staff_stats'), {'action': 'delete', 'id': ev.id})
        self.assertFalse(StatsEvent.objects.filter(pk=ev.id).exists())

    def test_csv_export(self):
        self.client.force_login(self.staff)
        r = self.client.get(reverse('staff_stats_csv'), {'range': '30d'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'text/csv; charset=utf-8')
        lines = r.content.decode().strip().splitlines()
        self.assertEqual(lines[0], 'date,contributions,contributions_registered,contributions_anonymous,signups')
        self.assertEqual(len(lines), 31)
        self.assertTrue(lines[-1].endswith(',2,1,1,2'))  # today: 2 done (1 reg, 1 anon), 2 sign-ups


class RankingPageTests(TestCase):
    def test_public_and_scopes(self):
        for url in ('/ranking/', '/ranking/teams/', '/ranking/countries/?period=week'):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200, url)
            self.assertContains(r, 'id="rk-card"')
        self.assertEqual(self.client.get('/ranking/bogus/').status_code, 404)

    def test_state_is_passed_to_the_page(self):
        r = self.client.get('/ranking/teams/?period=month&ordering=tasks&focus=me')
        self.assertEqual(r.context['scope'], 'teams')
        self.assertEqual(r.context['period'], 'month')
        self.assertEqual(r.context['ordering'], 'tasks')
        self.assertTrue(r.context['focus_me'])
        self.assertContains(r, 'data-period="month"')

    def test_topbar_links_to_ranking(self):
        r = self.client.get('/')
        self.assertContains(r, 'href="/ranking/"')
        self.assertNotContains(r, 'href="/#statistics-section"')


class HomepageStructureTests(TestCase):
    def test_single_entry_point_no_batches_no_contact_form(self):
        r = self.client.get('/')
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertNotIn('id="batch-section"', html)
        self.assertNotIn('Available Batches', html)
        self.assertNotIn('id="contact-section"', html)
        self.assertNotIn('href="/#batch-section"', html)
        self.assertIn('id="challenges-section"', html)          # always rendered
        self.assertIn('No challenge is open right now', html)   # empty state
        self.assertIn('id="statistics-section"', html)
        self.assertIn('href="/ranking/"', html)
        self.assertEqual(html.count('class="ds-kpi__value"'), 0)  # numbers live in one place only
        self.assertIn('ds-nav-toggle', html)                    # mobile menu

    def test_hero_hint_counts_open_challenges(self):
        from datetime import timedelta
        from django.utils import timezone
        from georeferencing.models import Challenge
        now = timezone.now()
        Challenge.objects.create(name='Open', start_at=now - timedelta(days=1), end_at=now + timedelta(days=5))
        r = self.client.get('/')
        self.assertEqual(r.context['open_challenges'], 1)
        self.assertNotContains(r, 'No challenge is open right now')


class ChallengeCardRulesTests(TestCase):
    def setUp(self):
        from datetime import timedelta
        from django.contrib.auth import get_user_model
        from django.utils import timezone
        from georeferencing.models import Challenge, ChallengeParticipant
        now = timezone.now()
        self.u = get_user_model().objects.create_user('u', 'u@x.org', 'pw')
        self.other = get_user_model().objects.create_user('o', 'o@x.org', 'pw')
        self.upcoming = Challenge.objects.create(name='Soon', start_at=now + timedelta(days=2), end_at=now + timedelta(days=9))
        self.active = Challenge.objects.create(name='Now', start_at=now - timedelta(days=1), end_at=now + timedelta(days=9),
                                               bbox_min_lat=0, bbox_max_lat=1, bbox_min_lon=0, bbox_max_lon=1)
        ChallengeParticipant.objects.create(challenge=self.active, user=self.other, left_at=now)  # left → not counted

    def test_enrolled_in_upcoming_shows_pill_not_continue(self):
        from georeferencing.models import ChallengeParticipant
        ChallengeParticipant.objects.create(challenge=self.upcoming, user=self.u)
        self.client.force_login(self.u)
        html = self.client.get('/').content.decode()
        self.assertNotIn('>\n                Continue', html)
        self.assertIn('Enrolled', html)
        self.assertIn('data-challenge-name="Soon"', html)

    def test_enrolled_in_active_shows_continue_without_batch_url(self):
        from georeferencing.models import ChallengeParticipant
        ChallengeParticipant.objects.create(challenge=self.active, user=self.u)
        self.client.force_login(self.u)
        html = self.client.get('/').content.decode()
        self.assertIn('href="/gettask" class="ds-btn ds-btn--primary ds-btn--sm">', html)
        self.assertIn('Region', html)  # bbox indicator

    def test_participant_counts_exclude_left(self):
        r = self.client.get('/')
        ch = next(c for c in r.context['visible_challenges'] if c.id == self.active.id)
        self.assertEqual(ch.participants_count, 0)
        r = self.client.get(f'/challenges/{self.active.id}/')
        self.assertEqual(r.context['participants_count'], 0)
