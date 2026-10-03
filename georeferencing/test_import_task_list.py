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
