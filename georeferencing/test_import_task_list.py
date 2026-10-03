"""import_task_list: resolution from cached mission tables, CSV filters and
cross-check, idempotent import. No network: the cache is pre-filled and the
downloader is patched."""
import csv
import json
import os
import tempfile
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TransactionTestCase

from georeferencing.management.commands import import_task_list as cmd
from georeferencing.models import Batch, FailedImage, GeoAttempt, Image

User = get_user_model()


def write_cache(root, mission, **tables):
    os.makedirs(os.path.join(root, mission), exist_ok=True)
    for t in cmd.TABLES:
        with open(os.path.join(root, mission, f'{t}.json'), 'w') as fh:
            json.dump(tables.get(t, []), fh)


class ImportTaskListTests(TransactionTestCase):
    def setUp(self):
        User.objects.create_user('s', 's@x.org', 'pw', is_staff=True)
        self.tmp = tempfile.mkdtemp()
        self.cache = os.path.join(self.tmp, 'cache')
        write_cache(self.cache, 'ISS057',
                    images=[{'images.frame': '61', 'images.filename': 'ISS057-E-61.JPG', 'images.directory': 'ESC/large/ISS057'},
                            {'images.frame': '62', 'images.filename': 'ISS057-E-62.JPG', 'images.directory': 'ESC/large/ISS057'},
                            {'images.frame': '64', 'images.filename': 'ISS057-E-64.JPG', 'images.directory': 'ESC/large/ISS057'}],
                    nadir=[{'nadir.frame': '61', 'nadir.lat': '51.4', 'nadir.lon': '12.5', 'nadir.pdate': '20181004', 'nadir.ptime': '174538'},
                           {'nadir.frame': '62', 'nadir.lat': '40.0', 'nadir.lon': '-3.0', 'nadir.pdate': '20181004', 'nadir.ptime': '174600'}],
                    camera=[{'camera.frame': '61', 'camera.camera': 'NIKON D4', 'camera.fclt': '56'}],
                    mlcoord=[{'mlcoord.frame': '61', 'mlcoord.lat': '51.3', 'mlcoord.lon': '12.4'}],
                    frames=[{'frames.frame': '64', 'frames.lat': '10.0', 'frames.lon': '20.0', 'frames.nlat': '10.5', 'frames.nlon': '20.5',
                             'frames.camera': 'N4', 'frames.fclt': '400', 'frames.pdate': '20181005', 'frames.ptime': '010203'}])
        self.csv = os.path.join(self.tmp, 'list.csv')
        with open(self.csv, 'w', newline='') as fh:
            w = csv.writer(fh); w.writerow(['nasa_id', 'lat', 'lon', 'elev', 'fclt'])
            w.writerow(['ISS057-E-61', '51.4', '12.5', '-11.0', '56.0'])     # ok
            w.writerow(['ISS057-E-62', '45.0', '-3.0', '-20.0', '50.0'])     # nadir mismatch (5°)
            w.writerow(['ISS057-E-63', '1.0', '1.0', '-30.0', '50.0'])       # no large file → NOT_FOUND
            w.writerow(['ISS057-E-64', '10.5', '20.5', '-30.0', ''])         # cataloged (frames only)
            w.writerow(['ISS057-E-65', '1.0', '1.0', '5.0', '50.0'])         # daylight → dropped

    def _run(self, *extra):
        out = StringIO()
        with mock.patch.object(cmd, '_dl', return_value=True):
            call_command('import_task_list', self.csv, '--batch', 'ISS057', '--replicas', '3',
                         '--min-sun-elev', '-6', '--cache-dir', self.cache, *extra, stdout=out)
        return out.getvalue()

    def test_resolve_fields(self):
        idx = cmd.NasaCache(self.cache, 'k').index('ISS057')
        f, reason = cmd.resolve('ISS057-E-61', idx)
        self.assertIsNone(reason)
        self.assertEqual(f['name'], 'ISS057-E-61.JPG')
        self.assertEqual(f['spacecraftNadirPoint'], '51.4, 12.5')
        self.assertEqual(f['photoCenterByMachineLearning'], '51.3, 12.4')
        self.assertEqual((f['camera'], f['focalLength']), ('NIKON D4', 56))
        self.assertEqual(f['taken'].isoformat(), '2018-10-04T17:45:38+00:00')
        self.assertEqual(f['largeImageURL'], 'https://eol.jsc.nasa.gov/DatabaseImages/ESC/large/ISS057/ISS057-E-61.JPG')
        self.assertEqual(f['smallImageURL'], 'https://eol.jsc.nasa.gov/DatabaseImages/ESC/small/ISS057/ISS057-E-61.JPG')
        f64, _ = cmd.resolve('ISS057-E-64', idx)
        self.assertEqual((f64['photoCenterPoint'], f64['spacecraftNadirPoint'], f64['focalLength']), ('10.0, 20.0', '10.5, 20.5', 400))
        self.assertEqual(cmd.resolve('ISS057-E-63', idx), (None, 'NOT_FOUND'))

    def test_dry_run_reports_and_writes_nothing(self):
        out = self._run('--dry-run')
        self.assertIn('dropped_daylight=1', out)
        self.assertIn('to_import=4', out)
        self.assertIn('resolved=3 unresolved=1 csv/api nadir mismatches=1', out)
        self.assertIn('mismatch ISS057-E-62', out)
        self.assertEqual(Image.objects.count(), 0)
        self.assertEqual(Batch.objects.count(), 0)

    def test_import_creates_batch_images_tasks_and_is_idempotent(self):
        out = self._run()
        self.assertIn('imported=3', out)
        batch = Batch.objects.get(name='ISS057')
        self.assertEqual(batch.processing_status, 'COMPLETED')
        self.assertEqual(Image.objects.filter(batch=batch).count(), 3)
        self.assertEqual(GeoAttempt.objects.filter(status='PENDING').count(), 9)
        img = Image.objects.get(name='ISS057-E-61.JPG')
        self.assertEqual((img.status, img.photoCenterLat, img.photoCenterLon), ('DOWNLOADED_GENERATED', 51.3, 12.4))  # ML centre wins
        self.assertEqual(FailedImage.objects.get(batch=batch, name='ISS057-E-63').reason, 'NOT_FOUND')
        self.assertIn('ISS057-E-61', batch.originalImages)
        # second run: only the unresolved id is retried, nothing is duplicated
        out2 = self._run()
        self.assertIn('already_in_db=3 to_import=1', out2)
        self.assertIn('unresolved=1', out2)
        self.assertEqual(Image.objects.count(), 3)
        self.assertEqual(GeoAttempt.objects.count(), 9)

    def test_download_failure_marks_image_and_creates_no_tasks(self):
        out = StringIO()
        with mock.patch.object(cmd, '_dl', return_value=False):
            call_command('import_task_list', self.csv, '--batch', 'ISS057', '--min-sun-elev', '-6',
                         '--cache-dir', self.cache, stdout=out)
        self.assertEqual(GeoAttempt.objects.count(), 0)
        self.assertEqual(Image.objects.filter(status='FAILED_DOWNLOADED').count(), 3)
        self.assertEqual(FailedImage.objects.filter(reason='DOWNLOAD_FAILED').count(), 3)


class EnrichImagesTests(TransactionTestCase):
    def test_fills_only_gaps(self):
        from georeferencing.models import Batch
        staff = User.objects.create_user('s', 's@x.org', 'pw', is_staff=True)
        tmp = tempfile.mkdtemp(); cache = os.path.join(tmp, 'cache')
        write_cache(cache, 'ISS057',
                    images=[{'images.frame': '61', 'images.filename': 'ISS057-E-61.JPG', 'images.directory': 'ESC/large/ISS057'}],
                    nadir=[{'nadir.frame': '61', 'nadir.lat': '51.4', 'nadir.lon': '12.5', 'nadir.pdate': '20181004', 'nadir.ptime': '174538'}],
                    camera=[{'camera.frame': '61', 'camera.camera': 'NIKON D4', 'camera.fclt': '56'}],
                    mlcoord=[{'mlcoord.frame': '61', 'mlcoord.lat': '51.3', 'mlcoord.lon': '12.4'}])
        b = Batch.objects.create(name='B', user=staff)
        img = Image.objects.create(name='ISS057-E-61.JPG', batch=b, spacecraftNadirPoint='50.0, 10.0', camera=None, focalLength=0)
        out = StringIO()
        call_command('enrich_images', '--cache-dir', cache, stdout=out)
        self.assertIn('[DRY RUN] images_touched=1', out.getvalue())
        img.refresh_from_db(); self.assertIsNone(img.camera)
        call_command('enrich_images', '--apply', '--cache-dir', cache, stdout=out)
        img.refresh_from_db()
        self.assertEqual(img.spacecraftNadirPoint, '50.0, 10.0')          # existing value kept
        self.assertEqual((img.camera, img.focalLength), ('NIKON D4', 56))
        self.assertEqual(img.photoCenterByMachineLearning, '51.3, 12.4')
        self.assertEqual((img.photoCenterLat, img.photoCenterLon), (51.3, 12.4))  # recomputed from ML centre
        self.assertEqual(img.taken.year, 2018)


class CatalogSyncTests(TransactionTestCase):
    def test_sync_builds_rows_tiers_night_and_links(self):
        from georeferencing.models import Batch, GeoAttempt, NasaPhoto
        from georeferencing.management.commands.nasa_catalog_report import summarize
        staff = User.objects.create_user('s', 's@x.org', 'pw', is_staff=True)
        tmp = tempfile.mkdtemp(); cache = os.path.join(tmp, 'cache')
        write_cache(cache, 'ISS057',
                    images=[{'images.frame': '61', 'images.filename': 'ISS057-E-61.JPG', 'images.directory': 'ESC/large/ISS057'},
                            {'images.frame': '62', 'images.filename': 'ISS057-E-62.JPG', 'images.directory': 'ESC/large/ISS057'},
                            {'images.frame': '63', 'images.filename': 'ISS057-E-63.JPG', 'images.directory': 'ESC/large/ISS057'},
                            {'images.frame': '64', 'images.filename': 'ISS057-E-64.JPG', 'images.directory': 'ESC/large/ISS057'}],
                    # 61: night over Leipzig (17:45 UTC Oct) long lens → tier C ; 62: ML centre → B ; 63: daytime (12:00 UTC) ; 64: catalogued → A
                    nadir=[{'nadir.frame': '61', 'nadir.lat': '51.4', 'nadir.lon': '12.5', 'nadir.pdate': '20181004', 'nadir.ptime': '174538'},
                           {'nadir.frame': '62', 'nadir.lat': '40.0', 'nadir.lon': '-3.0', 'nadir.pdate': '20181004', 'nadir.ptime': '220000'},
                           {'nadir.frame': '63', 'nadir.lat': '40.0', 'nadir.lon': '-3.0', 'nadir.pdate': '20180704', 'nadir.ptime': '120000'}],
                    camera=[{'camera.frame': '61', 'camera.camera': 'NIKON D4', 'camera.fclt': '56'},
                            {'camera.frame': '62', 'camera.camera': 'NIKON D4', 'camera.fclt': '24'}],
                    mlcoord=[{'mlcoord.frame': '62', 'mlcoord.lat': '40.4', 'mlcoord.lon': '-3.7'}],
                    frames=[{'frames.frame': '64', 'frames.lat': '10.0', 'frames.lon': '20.0', 'frames.nlat': '10.5', 'frames.nlon': '20.5',
                             'frames.camera': 'N4', 'frames.fclt': '400', 'frames.pdate': '20181005', 'frames.ptime': '010203',
                             'frames.tilt': 'LO', 'frames.feat': 'CITY LIGHTS', 'frames.cldp': '10', 'frames.elev': '-40', 'frames.geon': 'SUDAN'}])
        b = Batch.objects.create(name='B', user=staff)
        img = Image.objects.create(name='ISS057-E-61.JPG', batch=b)
        for st in ('DONE', 'DONE', 'PENDING'):
            GeoAttempt.objects.create(image=img, status=st)
        out = StringIO()
        call_command('sync_nasa_catalog', '--cache-dir', cache, stdout=out)
        self.assertEqual(NasaPhoto.objects.count(), 4)
        p61 = NasaPhoto.objects.get(frame=61)
        self.assertTrue(p61.night); self.assertEqual(p61.tier, 'C'); self.assertEqual(p61.image_id, img.id)
        self.assertEqual((p61.done_count, p61.pending_count), (2, 1))
        self.assertEqual(NasaPhoto.objects.get(frame=62).tier, 'B')
        self.assertFalse(NasaPhoto.objects.get(frame=63).night)
        p64 = NasaPhoto.objects.get(frame=64)
        self.assertEqual((p64.tier, p64.features, p64.region, p64.cloud_pct, p64.sun_elev_nasa), ('A', 'CITY LIGHTS', 'SUDAN', 10, -40.0))
        rep = summarize()
        m = next(r for r in rep if r['mission'] == 'ISS057')
        self.assertEqual((m['photos'], m['night'], m['catalogued_centre'], m['ml_centre'], m['in_our_db'], m['located_once']), (4, 3, 1, 1, 1, 1))
        # re-sync is idempotent
        call_command('sync_nasa_catalog', '--cache-dir', cache, stdout=out)
        self.assertEqual(NasaPhoto.objects.count(), 4)


class ImportFromCatalogTests(TransactionTestCase):
    def test_selection_and_import(self):
        from datetime import datetime, timezone as tz
        from georeferencing.models import GeoAttempt, NasaPhoto
        from georeferencing.management.commands import import_from_catalog as cmd
        User.objects.create_user('s', 's@x.org', 'pw', is_staff=True)
        mk = lambda fr, **kw: NasaPhoto.objects.create(mission='ISS060', frame=fr, has_large=True, filename=f'ISS060-E-{fr}.JPG', directory='ESC/large/ISS060',
                                                       taken=datetime(2019, 8, 1, 23, 0, tzinfo=tz.utc), **kw)
        mk(1, nadir_lat=-20.0, nadir_lon=-45.0, focal=85, night=True, tier='C')          # Brazil, selected
        mk(2, nadir_lat=-20.1, nadir_lon=-45.1, focal=85, night=True, tier='C')          # same 0.5° cell → dedup
        mk(3, nadir_lat=-20.0, nadir_lon=-45.0, focal=24, night=True, tier='D')          # wide → out
        mk(4, nadir_lat=-20.0, nadir_lon=-45.0, focal=85, night=False, tier='C')         # day → out
        mk(5, nadir_lat=48.0, nadir_lon=2.0, focal=85, night=True, tier='C')             # Paris → out
        mk(6, nadir_lat=-10.0, nadir_lon=-50.0, center_lat=-10.2, center_lon=-50.3, focal=400, night=True, tier='A')
        sel = cmd.select({'bbox': (-33.8, 5.3, -74.0, -34.8), 'night': True, 'min_focal': 50, 'tiers': ['A', 'B', 'C'], 'dedup': 0.5})
        self.assertEqual(sorted(p.frame for p in sel), [1, 6])
        out = StringIO()
        with mock.patch.object(cmd, '_dl', return_value=True):
            call_command('import_from_catalog', '--batch', 'Brazil', '--bbox', '-33.8', '5.3', '-74.0', '-34.8', '--night', '--min-focal', '50',
                         '--tiers', 'A', 'B', 'C', '--dedup', '0.5', '--replicas', '3', stdout=out)
        self.assertIn('imported=2', out.getvalue())
        self.assertEqual(Image.objects.filter(batch__name='Brazil').count(), 2)
        self.assertEqual(GeoAttempt.objects.count(), 6)
        self.assertEqual(NasaPhoto.objects.filter(image__isnull=False).count(), 2)
        self.assertEqual(NasaPhoto.objects.get(frame=1).pending_count, 3)
        # already imported rows are excluded next time
        self.assertEqual(sorted(p.frame for p in cmd.select({'bbox': (-33.8, 5.3, -74.0, -34.8), 'night': True})), [2, 3])  # 2 was deduped away, 3 is wide; both still unimported
