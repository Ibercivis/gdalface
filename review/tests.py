import os
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image as PILImage

from georeferencing.models import Batch, GeoAttempt, Image
from review import build, overlays
from review.models import AttemptOverlay, AttemptReview

User = get_user_model()


DEFAULT = object()


def pts(shift=0.0):
    """5 points of a north-up photo 800x600 px: lon = -1 + x/1000, lat = 41.5 - y/1000."""
    out = []
    for i, (x, y) in enumerate([(100, 100), (700, 100), (100, 500), (700, 500), (400, 300)], 1):
        out.append({'id': f'Point {i}', 'px': 1, 'py': 1, 'actualPx': x, 'actualPy': y,
                    'lat': 41.5 - y / 1000 + shift, 'lon': -1 + x / 1000})
    return out


class ReviewTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media = tempfile.mkdtemp(prefix='review-test-')
        cls._override = override_settings(MEDIA_ROOT=cls.media)
        cls._override.enable()
        os.makedirs(os.path.join(cls.media, 'original'))
        PILImage.linear_gradient('L').resize((800, 600)).convert('RGB').save(
            os.path.join(cls.media, 'original', 'ISS000-E-1.JPG'))

    @classmethod
    def tearDownClass(cls):
        cls._override.disable()
        shutil.rmtree(cls.media, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.staff = User.objects.create_user('staff', 's@x.org', 'pw', is_staff=True)
        self.staff2 = User.objects.create_user('staff2', 's2@x.org', 'pw', is_staff=True)
        self.user = User.objects.create_user('user', 'u@x.org', 'pw')
        batch = Batch.objects.create(name='B', user=self.staff)
        self.image = Image.objects.create(name='ISS000-E-1.JPG', batch=batch)

    def attempt(self, points=DEFAULT, user=None, status='DONE'):
        return GeoAttempt.objects.create(image=self.image, status=status, assignedUser=user,
                                         controlPoints=pts() if points is DEFAULT else points)

    def build(self, ga, **kw):
        ga = GeoAttempt.objects.select_related('image', 'overlay').get(pk=ga.pk)
        job = build.plan(ga, **kw)
        if not job:
            return None
        points, digest, rel = job
        status, payload = build.run(ga, points, rel)
        return build.store(ga, points, digest, rel, status, payload)


class OverlayBuildTests(ReviewTestCase):
    def test_builds_overlay_with_footprint_around_the_points(self):
        o = self.build(self.attempt())
        self.assertEqual(o.status, 'ok', o.detail)
        path = os.path.join(self.media, o.file)
        self.assertTrue(os.path.isfile(path))
        with PILImage.open(path) as im:
            self.assertIn(im.mode, ('RGB', 'RGBA'))   # libwebp drops alpha when fully opaque
            self.assertLessEqual(im.size[0], overlays.MAX_WIDTH)
            self.assertEqual(im.size, (o.width, o.height))
        # every control point lies inside the warped photo's bounds
        for p in pts():
            self.assertTrue(o.south <= p['lat'] <= o.north and o.west <= p['lon'] <= o.east)
        ring = o.polygon
        self.assertEqual(ring[0], ring[-1])
        self.assertGreaterEqual(len(ring), 5)
        # 800x600 px at 1/1000° => 0.8° x 0.6° ≈ 67 km x 67 km at 41°N
        self.assertTrue(3500 < o.area_km2 < 5500, o.area_km2)
        self.assertEqual(o.n_points, 5)

    def test_up_to_date_overlay_is_not_rebuilt_and_changed_points_replace_the_file(self):
        ga = self.attempt()
        first = self.build(ga)
        self.assertIsNone(self.build(ga))                       # same hash and file present
        self.assertIsNotNone(self.build(ga, force=True))
        old_file = AttemptOverlay.objects.get(geoattempt=ga).file
        ga.controlPoints = pts(shift=0.01)
        ga.save()
        second = self.build(ga)
        self.assertNotEqual(first.points_hash, second.points_hash)
        self.assertNotEqual(old_file, second.file)
        self.assertFalse(os.path.exists(os.path.join(self.media, old_file)))
        self.assertTrue(os.path.exists(os.path.join(self.media, second.file)))

    def test_missing_file_is_rebuilt(self):
        o = self.build(self.attempt())
        os.remove(os.path.join(self.media, o.file))
        self.assertIsNotNone(self.build(GeoAttempt.objects.get(pk=o.geoattempt_id)))

    def test_too_few_points_is_skipped(self):
        o = self.build(self.attempt(points=pts()[:2]))
        self.assertEqual(o.status, 'skipped')
        self.assertIn('at least 3', o.detail)
        self.assertEqual(o.file, '')

    def test_odd_control_points_are_skipped_not_crashing(self):
        for bad in ({}, None, [], 'x', [1, 'a']):
            o = self.build(self.attempt(points=bad))
            self.assertEqual(o.status, 'skipped', bad)

    def test_antimeridian_and_polar_are_skipped(self):
        wide = pts(); wide[0]['lon'] = 179.9
        self.assertEqual(self.build(self.attempt(points=wide)).status, 'skipped')
        polar = pts(); polar[0]['lat'] = 85.0
        self.assertEqual(self.build(self.attempt(points=polar)).status, 'skipped')

    def test_missing_original_is_failed_and_only_retried_on_request(self):
        other = Image.objects.create(name='NOPE-E-1.JPG', batch=self.image.batch)
        ga = GeoAttempt.objects.create(image=other, status='DONE', controlPoints=pts())
        self.assertEqual(self.build(ga).status, 'failed')
        self.assertIsNone(self.build(ga))
        self.assertIsNotNone(self.build(ga, retry_failed=True))

    def test_collinear_points_fail_cleanly(self):
        line = [{'id': f'P{i}', 'actualPx': 100 * i, 'actualPy': 100 * i,
                 'lat': 41.0 + i / 100, 'lon': -1.0 + i / 100} for i in range(1, 5)]
        o = self.build(self.attempt(points=line))
        self.assertIn(o.status, ('failed', 'ok'))               # GDAL decides; it must not raise

    def test_image_name_without_extension_is_found(self):
        shutil.copyfile(os.path.join(self.media, 'original', 'ISS000-E-1.JPG'),
                        os.path.join(self.media, 'original', 'ISS000-E-9.JPG'))
        self.image.name = 'ISS000-E-9'
        self.image.save()
        self.assertEqual(self.build(self.attempt()).status, 'ok')

    def test_command_builds_everything_done(self):
        a, b = self.attempt(), self.attempt()
        self.attempt(status='PENDING')
        call_command('build_overlays', workers=2, stdout=open(os.devnull, 'w'))
        self.assertEqual(set(AttemptOverlay.objects.values_list('geoattempt_id', flat=True)), {a.pk, b.pk})
        self.assertEqual(AttemptOverlay.objects.filter(status='ok').count(), 2)


class ReviewApiTests(ReviewTestCase):
    def setUp(self):
        super().setUp()
        self.mine = self.attempt(user=self.staff)
        self.theirs = self.attempt(user=self.user)
        self.nobody = self.attempt()
        for ga in (self.mine, self.theirs, self.nobody):
            self.build(ga)

    def test_access_is_staff_only(self):
        for name in ('review-footprints',):
            self.assertEqual(self.client.get(reverse(name)).status_code, 403)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('review-footprints')).status_code, 403)
        self.assertEqual(self.client.post(reverse('review-vote'), {}, content_type='application/json').status_code, 403)
        self.assertEqual(self.client.get(reverse('review_map')).status_code, 404)

    @override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
    def test_page_for_staff_and_redirect_for_anonymous(self):
        self.assertEqual(self.client.get(reverse('review_map')).status_code, 302)
        self.client.force_login(self.staff)
        r = self.client.get(reverse('review_map'))
        self.assertEqual(r.status_code, 200)
        self.assertIn('csrftoken', r.cookies)      # the vote POST needs it
        self.assertIn(reverse('review-vote'), r.content.decode())

    def test_footprints_geojson(self):
        self.client.force_login(self.staff)
        r = self.client.get(reverse('review-footprints'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Cache-Control'], 'no-store')
        feats = {f['properties']['id']: f for f in r.json()['features']}
        self.assertEqual(set(feats), {self.mine.pk, self.theirs.pk, self.nobody.pk})
        p = feats[self.theirs.pk]['properties']
        self.assertEqual(p['name'], 'ISS000-E-1')
        self.assertEqual(p['user_id'], self.user.pk)
        self.assertFalse(p['own'])
        self.assertTrue(feats[self.mine.pk]['properties']['own'])
        self.assertTrue(p['overlay'].startswith('/media/overlays/'))
        self.assertEqual(len(p['bounds']), 2)
        self.assertEqual(feats[self.theirs.pk]['geometry']['type'], 'Polygon')
        self.assertEqual((p['ok'], p['not_ok'], p['mine']), (0, 0, None))

    def test_unbuilt_or_skipped_attempts_are_not_listed(self):
        short = self.build(self.attempt(points=pts()[:2]))
        self.attempt()                                         # no overlay row at all
        self.client.force_login(self.staff)
        ids = {f['properties']['id'] for f in self.client.get(reverse('review-footprints')).json()['features']}
        self.assertNotIn(short.geoattempt_id, ids)
        self.assertEqual(len(ids), 3)

    def vote(self, attempt, verdict):
        return self.client.post(reverse('review-vote'), {'geoattempt': attempt.pk, 'verdict': verdict},
                                content_type='application/json')

    def test_vote_counts_change_and_unique(self):
        self.client.force_login(self.staff)
        r = self.vote(self.theirs, 'ok')
        self.assertEqual((r.status_code, r.json()['ok'], r.json()['not_ok']), (200, 1, 0))
        r = self.vote(self.theirs, 'not_ok')                    # changing the vote, not adding one
        self.assertEqual((r.json()['ok'], r.json()['not_ok'], r.json()['mine']), (0, 1, 'not_ok'))
        self.assertEqual(AttemptReview.objects.filter(geoattempt=self.theirs).count(), 1)
        self.client.force_login(self.staff2)
        r = self.vote(self.theirs, 'ok')
        self.assertEqual((r.json()['ok'], r.json()['not_ok']), (1, 1))
        feats = {f['properties']['id']: f['properties']
                 for f in self.client.get(reverse('review-footprints')).json()['features']}
        self.assertEqual((feats[self.theirs.pk]['ok'], feats[self.theirs.pk]['not_ok'], feats[self.theirs.pk]['mine']),
                         (1, 1, 'ok'))

    def test_vote_rules(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.vote(self.mine, 'ok').status_code, 403)        # own attempt
        self.assertEqual(self.vote(self.theirs, 'maybe').status_code, 400)
        self.assertEqual(self.client.post(reverse('review-vote'), {'geoattempt': 'x', 'verdict': 'ok'},
                                          content_type='application/json').status_code, 400)
        self.assertEqual(self.client.post(reverse('review-vote'), {'geoattempt': 99999, 'verdict': 'ok'},
                                          content_type='application/json').status_code, 404)
        pending = self.attempt(status='PENDING')
        self.assertEqual(self.vote(pending, 'ok').status_code, 404)
        self.assertFalse(AttemptReview.objects.exists())

    def test_deleting_a_reviewer_keeps_the_vote(self):
        self.client.force_login(self.staff2)
        self.vote(self.theirs, 'ok')
        self.staff2.delete()
        self.assertEqual(AttemptReview.objects.filter(geoattempt=self.theirs, user__isnull=True).count(), 1)
