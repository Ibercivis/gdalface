"""Staff-only export API (token auth) and the related access changes."""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from georeferencing.models import Batch, GeoAttempt, Image
from user_profile.models import ApiToken

User = get_user_model()

LOCMEM = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                      'LOCATION': 'export-tests'}}

PTS = [
    {'id': 'Point 1', 'px': 1, 'py': 2, 'actualPx': 100.5, 'actualPy': 200.5,
     'text': {'px': 100.5}, 'lat': 40.0, 'lon': -3.0, 'complete': True},
    {'id': 'Point 2', 'px': 3, 'py': 4, 'actualPx': 300, 'actualPy': 400, 'lat': None, 'lon': -3.1},
]


@override_settings(CACHES=LOCMEM)
class ExportApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.staff = User.objects.create_user('staff', 's@x.org', 'pw', is_staff=True)
        self.user = User.objects.create_user('user', 'u@x.org', 'pw')
        self.batch = Batch.objects.create(name='B', user=self.staff)
        self.img = Image.objects.create(
            name='ISS030-E-83269.JPG', batch=self.batch,
            largeImageURL='https://eol.jsc.nasa.gov/DatabaseImages/ESC/large/ISS030/ISS030-E-83269.JPG')
        self.ga = GeoAttempt.objects.create(
            image=self.img, status='DONE', assignedUser=self.user,
            finishedDateTime=timezone.now(), controlPoints=PTS)
        _row, self.token = ApiToken.issue(self.staff)
        self.auth = {'HTTP_AUTHORIZATION': f'Bearer {self.token}'}

    # ── auth ──────────────────────────────────────────────────────────
    def test_no_token_is_401(self):
        r = self.client.get(reverse('export-images'))
        self.assertEqual(r.status_code, 401)

    def test_bad_token_is_401(self):
        r = self.client.get(reverse('export-images'), HTTP_AUTHORIZATION='Bearer nope')
        self.assertEqual(r.status_code, 401)

    def test_token_in_query_string_is_ignored(self):
        r = self.client.get(reverse('export-images') + f'?token={self.token}')
        self.assertEqual(r.status_code, 401)

    def test_non_staff_token_is_403(self):
        _row, raw = ApiToken.issue(self.user)
        r = self.client.get(reverse('export-images'), HTTP_AUTHORIZATION=f'Bearer {raw}')
        self.assertEqual(r.status_code, 403)

    def test_staff_removed_cuts_access(self):
        self.staff.is_staff = False
        self.staff.save()
        self.assertEqual(self.client.get(reverse('export-images'), **self.auth).status_code, 403)

    def test_inactive_user_is_401(self):
        self.staff.is_active = False
        self.staff.save()
        self.assertEqual(self.client.get(reverse('export-images'), **self.auth).status_code, 401)

    def test_regenerating_revokes_previous(self):
        ApiToken.issue(self.staff)
        self.assertEqual(self.client.get(reverse('export-images'), **self.auth).status_code, 401)
        self.assertEqual(ApiToken.objects.filter(user=self.staff, revoked=False).count(), 1)

    def test_only_hash_is_stored_and_last_used_updates(self):
        row = ApiToken.objects.get(user=self.staff, revoked=False)
        self.assertNotIn(self.token, (row.token_hash, row.prefix))
        self.assertIsNone(row.last_used)
        self.client.get(reverse('export-images'), **self.auth)
        row.refresh_from_db()
        self.assertIsNotNone(row.last_used)

    # ── payload ───────────────────────────────────────────────────────
    def test_image_payload_shape(self):
        r = self.client.get(reverse('export-image', args=[self.img.pk]), **self.auth)
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d['image']['name'], 'ISS030-E-83269.JPG')
        self.assertEqual(d['image']['nasa_page_url'],
                         'https://eol.jsc.nasa.gov/SearchPhotos/photo.pl?mission=ISS030&roll=E&frame=83269')
        self.assertTrue(d['image']['nasa_image_url'].endswith('ISS030-E-83269.JPG'))
        self.assertIsNone(d['image']['nasa_thumbnail_url'])
        self.assertEqual(len(d['geoattempts']), 1)
        ga = d['geoattempts'][0]
        self.assertEqual(ga['user_id'], self.user.pk)
        self.assertNotIn('username', str(d))
        # normalised; the point without lat is dropped; canvas px/py not exposed
        self.assertEqual(ga['control_points'],
                         [{'id': 'Point 1', 'x_px': 100.5, 'y_px': 200.5, 'lat': 40.0, 'lon': -3.0}])

    def test_anonymous_attempt_has_null_user(self):
        self.ga.assignedUser = None
        self.ga.save()
        d = self.client.get(reverse('export-image', args=[self.img.pk]), **self.auth).json()
        self.assertIsNone(d['geoattempts'][0]['user_id'])

    def test_image_without_large_url_and_with_link(self):
        self.img.largeImageURL = None
        self.img.link = 'https://example.org/page'
        self.img.save()
        d = self.client.get(reverse('export-image', args=[self.img.pk]), **self.auth).json()
        self.assertIsNone(d['image']['nasa_image_url'])
        self.assertEqual(d['image']['nasa_page_url'], 'https://example.org/page')

    def test_odd_control_points_do_not_break(self):
        for bad in ({}, None, [], 'x', [1, 'a']):
            GeoAttempt.objects.filter(pk=self.ga.pk).update(controlPoints=bad)
            r = self.client.get(reverse('export-images'), **self.auth)
            self.assertEqual(r.status_code, 200, bad)
            self.assertEqual(r.json()['results'], [], bad)
            self.assertEqual(self.client.get(reverse('export-image', args=[self.img.pk]), **self.auth).status_code, 404)

    def test_only_done_attempts_listed(self):
        other = Image.objects.create(name='ISS030-E-1.JPG', batch=self.batch)
        GeoAttempt.objects.create(image=other, status='PENDING', controlPoints=PTS)
        GeoAttempt.objects.create(image=other, status='ASSIGNED', controlPoints=PTS)
        r = self.client.get(reverse('export-images'), **self.auth).json()
        self.assertEqual([x['image']['id'] for x in r['results']], [self.img.pk])
        self.assertEqual(self.client.get(reverse('export-image', args=[other.pk]), **self.auth).status_code, 404)

    # ── pagination / incremental ──────────────────────────────────────
    def test_pagination_and_updated_since(self):
        imgs = [self.img]
        for i in range(2, 5):
            im = Image.objects.create(name=f'ISS030-E-{i}.JPG', batch=self.batch)
            GeoAttempt.objects.create(image=im, status='DONE', controlPoints=PTS,
                                      finishedDateTime=timezone.now())
            imgs.append(im)
        url = reverse('export-images')
        p1 = self.client.get(url + '?limit=2', **self.auth).json()
        self.assertEqual([x['image']['id'] for x in p1['results']], [imgs[0].pk, imgs[1].pk])
        self.assertIn(f'after={imgs[1].pk}', p1['next'])
        p2 = self.client.get(p1['next'], **self.auth).json()
        self.assertEqual([x['image']['id'] for x in p2['results']], [imgs[2].pk, imgs[3].pk])
        self.assertIsNone(p2['next'])

        future = (timezone.now() + timezone.timedelta(days=1)).isoformat().replace('+', '%2B')
        self.assertEqual(self.client.get(url + f'?updated_since={future}', **self.auth).json()['results'], [])
        self.assertEqual(self.client.get(url + '?updated_since=garbage', **self.auth).status_code, 400)
        self.assertEqual(self.client.get(url + '?limit=abc', **self.auth).status_code, 400)

    # ── related access changes ────────────────────────────────────────
    def test_geoattempt_individual_get_is_staff_only(self):
        url = reverse('geoattempt-individual', args=[self.ga.pk])
        self.assertIn(self.client.get(url).status_code, (401, 403))
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_geoattempt_list_no_longer_500(self):
        self.client.force_login(self.staff)  # list view is unchanged (still open); sanity only
        self.assertEqual(self.client.get(reverse('geoattempt')).status_code, 200)


class ApiAccessPageTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user('staff', 's@x.org', 'pw', is_staff=True)
        self.user = User.objects.create_user('user', 'u@x.org', 'pw')

    def test_non_staff_gets_404_anonymous_redirected(self):
        url = reverse('api_access')
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.assertFalse(ApiToken.objects.exists())

    def test_token_shown_once(self):
        self.client.force_login(self.staff)
        r = self.client.post(reverse('api_access'))
        self.assertEqual(r.status_code, 200)
        raw = r.context['token_plain']
        self.assertIn(f'Bearer {raw}', r.content.decode())
        self.assertIn('curl -H', r.content.decode())
        self.assertIn(f"export TOKEN='{raw}'", r.content.decode())  # script ready to run
        self.assertIn('Regenerate token', r.content.decode())  # also right after generating
        self.assertIn('no-cache', r['Cache-Control'])
        again = self.client.get(reverse('api_access'))
        self.assertNotIn(raw, again.content.decode())
        self.assertIn(ApiToken.objects.get().prefix, again.content.decode())

    def test_regenerate_button_only_when_active(self):
        self.client.force_login(self.staff)
        first = self.client.get(reverse('api_access')).content.decode()
        self.assertIn('Generate token', first)
        self.assertNotIn('Regenerate token', first)
        self.assertIn("export TOKEN='&lt;your-token&gt;'", first)
        self.client.post(reverse('api_access'))
        second = self.client.get(reverse('api_access')).content.decode()
        self.assertIn('Regenerate token', second)
        self.assertIn('confirm(', second)
