"""
Seed a small local dataset for development.

**No data is copied from production, and none is needed.** The dataset has two
halves, and only one of them is real:

* **The imagery and its coordinates are real and public.** The frames below are
  actual ISS night photographs from NASA's Gateway to Astronaut Photography of
  Earth, which places them in the public domain, and the nadir coordinates are
  the ones NASA publishes for each frame. The files are fetched from
  `eol.jsc.nasa.gov`, which serves them without an API key.

* **Every person is invented.** The accounts, their names, their addresses
  (all on the reserved `.invalid` domain, so none of them can receive mail) and
  their statistics are made up by this command. No account, address, profile or
  contribution belongs to a real volunteer.

That split is the point: in this application the only personal data lives in
`auth_user`, `account_emailaddress` and `user_profile_userprofile`. Batches,
images and georeferencing attempts carry none, so the realistic half of a
development dataset is exactly the half that can be rebuilt from a public
source — and the half that would have carried personal data is the half that is
cheapest to invent.

Usage:

    python manage.py seed_local
    python manage.py seed_local --images 4 --volunteers 2
    python manage.py seed_local --reset
"""
# pylint: disable=too-many-locals,too-many-statements,broad-exception-caught

import os
import random
from datetime import timedelta

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from georeferencing.models import Batch, GeoAttempt, GeoAttemptsByUserByDay, Image
from user_profile.models import UserProfile

# Real ISS frames, with the nadir coordinates NASA publishes for them.
#
# Every frame here is a genuine *night* photograph showing city lights, which
# is what this application exists to georeference. They were picked by
# measuring the images rather than by trusting their captions: a night frame is
# mostly black with bright points in it, and `local_dev/find_night_frames.py`
# is the script that applies that test. Most of NASA's archive is daylight, and
# a daylight frame makes a useless sample here.
#
# Three separate night passes, so the map does not open in the same place every
# time: northern Spain, the sea off Andalusia, and the Kantō region of Japan.
#
# directory: the folder under https://eol.jsc.nasa.gov/DatabaseImages/
FRAMES = [
    ("ISS026-E-14782", "ESC/large/ISS026", 42.3, -5.9, "Spain at night"),
    ("ISS026-E-14783", "ESC/large/ISS026", 42.2, -5.8, "Spain at night"),
    ("ISS026-E-14784", "ESC/large/ISS026", 42.2, -5.7, "Spain at night"),
    ("ISS030-E-10008", "ESC/large/ISS030", 36.6, -13.9, "Southern Spain at night"),
    ("ISS030-E-10009", "ESC/large/ISS030", 36.7, -13.7, "Southern Spain at night"),
    ("ISS030-E-10010", "ESC/large/ISS030", 36.8, -13.6, "Southern Spain at night"),
    ("ISS064-E-28418", "ESC/large/ISS064", 36.5, 140.4, "Kantō, Japan, at night"),
    ("ISS064-E-28420", "ESC/large/ISS064", 36.4, 140.5, "Kantō, Japan, at night"),
    ("ISS064-E-28422", "ESC/large/ISS064", 36.0, 141.0, "Kantō, Japan, at night"),
]

IMAGE_BASE = "https://eol.jsc.nasa.gov/DatabaseImages"

# Invented people. The `.invalid` top-level domain is reserved by RFC 2606 and
# can never resolve, so none of these addresses can reach a mailbox.
EMAIL_DOMAIN = "lostatnight.invalid"

SUPERUSER = ("admin", "Local", "Admin")
RESEARCHER = ("researcher", "Rosalind", "Vera")
VOLUNTEERS = [
    ("volunteer1", "Ada", "Nocturna", "ES", "Zaragoza"),
    ("volunteer2", "Bruno", "Estrella", "PT", "Porto"),
    ("volunteer3", "Chiara", "Luce", "IT", "Bologna"),
]

BATCH_NAME = "Local sample — ISS night frames"


class Command(BaseCommand):
    """Create a small, entirely local development dataset."""

    help = (
        "Seed a small local dataset: invented accounts plus real public-domain "
        "ISS frames from NASA. Copies nothing from production."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--images",
            type=int,
            default=6,
            help=f"How many frames to seed (1-{len(FRAMES)}). Default 6.",
        )
        parser.add_argument(
            "--volunteers",
            type=int,
            default=len(VOLUNTEERS),
            help=f"How many invented volunteers (0-{len(VOLUNTEERS)}).",
        )
        parser.add_argument(
            "--replicas",
            type=int,
            default=3,
            help="GeoAttempts per image. Default 3 (production uses 5).",
        )
        parser.add_argument(
            "--password",
            default="devpass12345",
            help="Password for every seeded account. Default 'devpass12345'.",
        )
        parser.add_argument(
            "--no-download",
            action="store_true",
            help="Create the rows but do not fetch the JPEGs from NASA.",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete what a previous run of this command created, then stop.",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "Refusing to run with DEBUG=False. This command writes invented "
                "accounts and is for local development only."
            )

        if options["reset"]:
            self._reset()
            return

        count = max(1, min(options["images"], len(FRAMES)))
        n_volunteers = max(0, min(options["volunteers"], len(VOLUNTEERS)))
        frames = FRAMES[:count]

        random.seed(20261111)  # a repeatable dataset run after run

        with transaction.atomic():
            self._ensure_site()
            superuser = self._create_superuser(options["password"])
            researcher = self._create_researcher(options["password"])
            volunteers = self._create_volunteers(n_volunteers, options["password"])
            batch = self._create_batch(researcher, frames, options["replicas"])
            images = self._create_images(batch, frames, options["replicas"])
            self._create_geoattempts(images, volunteers, options["replicas"])
            self._create_calendar(volunteers)

        if not options["no_download"]:
            self._download(frames)

        self._report(superuser, researcher, volunteers, batch, options["password"])

    # ------------------------------------------------------------------ setup

    def _ensure_site(self):
        """`settings.SITE_ID` is 2, which `migrate` does not create."""
        site, created = Site.objects.update_or_create(
            pk=settings.SITE_ID,
            defaults={"domain": "localhost:8000", "name": "LostAtNight (local)"},
        )
        self.stdout.write(
            f"{'Created' if created else 'Updated'} Site {site.pk}: {site.domain}"
        )

    def _verified_email(self, user):
        """Mark the address confirmed so the account can sign in at once.

        `ACCOUNT_EMAIL_VERIFICATION` is 'mandatory', and nothing can confirm an
        address locally because no mail is sent anywhere.
        """
        try:
            from allauth.account.models import EmailAddress  # noqa: PLC0415
        except ImportError:  # pragma: no cover
            return
        EmailAddress.objects.update_or_create(
            user=user,
            email=user.email,
            defaults={"verified": True, "primary": True},
        )

    def _make_user(self, handle, first, last, password, **flags):
        user_model = get_user_model()
        email = f"{handle}@{EMAIL_DOMAIN}"
        user, created = user_model.objects.get_or_create(
            username=handle,
            defaults={"email": email, "first_name": first, "last_name": last, **flags},
        )
        if not created:
            user.email = email
            user.first_name = first
            user.last_name = last
            for key, value in flags.items():
                setattr(user, key, value)
        user.set_password(password)
        user.save()
        self._verified_email(user)
        return user

    def _create_superuser(self, password):
        user = self._make_user(*SUPERUSER, password, is_staff=True, is_superuser=True)
        self.stdout.write(f"Superuser: {user.email}")
        return user

    def _create_researcher(self, password):
        user = self._make_user(*RESEARCHER, password, is_staff=True)
        self.stdout.write(f"Batch owner (staff): {user.email}")
        return user

    def _create_volunteers(self, how_many, password):
        volunteers = []
        for handle, first, last, country, city in VOLUNTEERS[:how_many]:
            user = self._make_user(handle, first, last, password)
            # The post_save signal on User already made the profile.
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.bio = f"Invented {first} from {city}. Local development only."
            profile.country = country
            profile.location = city
            profile.visible = True
            profile.save()
            volunteers.append(user)
            self.stdout.write(f"Volunteer: {user.email}")
        return volunteers

    # ------------------------------------------------------------------- data

    def _create_batch(self, owner, frames, replicas):
        batch, _ = Batch.objects.update_or_create(
            name=BATCH_NAME,
            defaults={
                "type": "LIST",
                "user": owner,
                "originalImages": ",".join(name for name, *_ in frames),
                "numberImages": len(frames),
                "replicas": replicas,
                "processing_status": "COMPLETED",
                "processing_start_time": timezone.now() - timedelta(minutes=12),
                "processing_end_time": timezone.now() - timedelta(minutes=2),
                "log": "\n[II] Seeded locally by seed_local; no batch job was run.",
            },
        )
        self.stdout.write(f"Batch: {batch.name} ({len(frames)} images)")
        return batch

    def _create_images(self, batch, frames, replicas):
        images = []
        for index, (name, directory, lat, lon, caption) in enumerate(frames):
            filename = f"{name}.JPG"
            large = f"{IMAGE_BASE}/{directory}/{filename}"
            image, _ = Image.objects.update_or_create(
                name=filename,
                defaults={
                    "taken": timezone.now() - timedelta(days=400 + index),
                    "camera": "Nikon D4",
                    # focalLength and spaceCraftAltitude are display-only and
                    # come from an API that needs a key, so they stay empty
                    # rather than being invented.
                    "spacecraftNadirPoint": f"{lat}, {lon}",
                    "photoCenterPoint": f"{lat}, {lon}",
                    "photoCenterByMachineLearning": None,
                    "link": f"{IMAGE_BASE}/{directory}/{filename}",
                    "largeImageURL": large,
                    "smallImageURL": large.replace("large", "small"),
                    "batch": batch,
                    "replicas": replicas,
                },
            )
            images.append(image)
            self.stdout.write(f"  Image: {filename} — {caption} ({lat}, {lon})")
        return images

    def _control_points(self, image):
        """Three invented control points near the frame's own coordinates."""
        lat, lon = (float(part) for part in image.photoCenterPoint.split(","))
        points = []
        for _ in range(3):
            points.append(
                {
                    "actualPx": random.randint(200, 1800),
                    "actualPy": random.randint(200, 1200),
                    "lat": round(lat + random.uniform(-0.25, 0.25), 5),
                    "lon": round(lon + random.uniform(-0.25, 0.25), 5),
                }
            )
        return points

    def _create_geoattempts(self, images, volunteers, replicas):
        """A spread of statuses, so every screen has something to show."""
        GeoAttempt.objects.filter(image__in=images).delete()

        done = assigned = pending = 0
        for index, image in enumerate(images):
            for replica in range(replicas):
                slot = (index + replica) % 3
                attempt = GeoAttempt(image=image, numberTries=0)

                if slot == 0 and volunteers:
                    # Finished by a volunteer.
                    volunteer = volunteers[(index + replica) % len(volunteers)]
                    started = timezone.now() - timedelta(
                        days=random.randint(1, 40), minutes=random.randint(0, 600)
                    )
                    attempt.status = "DONE"
                    attempt.assignedUser = volunteer
                    attempt.assignedDateTime = started
                    attempt.finishedDateTime = started + timedelta(
                        seconds=random.randint(90, 900)
                    )
                    attempt.numberTries = random.randint(1, 3)
                    attempt.controlPoints = self._control_points(image)
                    done += 1
                elif slot == 1 and volunteers:
                    # Handed out and still open.
                    attempt.status = "ASSIGNED"
                    attempt.assignedUser = volunteers[index % len(volunteers)]
                    attempt.assignedDateTime = timezone.now() - timedelta(
                        minutes=random.randint(5, 120)
                    )
                    assigned += 1
                else:
                    # Waiting in the queue, which is what the task page needs.
                    attempt.status = "PENDING"
                    pending += 1

                attempt.save()

        self.stdout.write(
            f"GeoAttempts: {done} DONE, {assigned} ASSIGNED, {pending} PENDING"
        )
        self._refresh_profiles(volunteers)

    def _refresh_profiles(self, volunteers):
        """Make the rankings agree with the attempts that were just created."""
        for user in volunteers:
            finished = GeoAttempt.objects.filter(assignedUser=user, status="DONE")
            points = 0
            seconds = 0
            for attempt in finished:
                if isinstance(attempt.controlPoints, list):
                    points += len(attempt.controlPoints)
                if attempt.finishedDateTime and attempt.assignedDateTime:
                    seconds += int(
                        (attempt.finishedDateTime - attempt.assignedDateTime).total_seconds()
                    )
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.geoattempts_done = finished.count()
            profile.controlPointsDone = points
            profile.time_spent = seconds
            profile.save()

    def _create_calendar(self, volunteers):
        """Rows for the contribution heat map on the profile page."""
        if not volunteers:
            return
        today = timezone.now().date()
        GeoAttemptsByUserByDay.objects.filter(user__in=volunteers).delete()
        rows = 0
        for user in volunteers:
            for days_ago in range(0, 90, random.randint(2, 6)):
                GeoAttemptsByUserByDay.objects.create(
                    user=user,
                    date=today - timedelta(days=days_ago),
                    numberGeoAttempts=random.randint(1, 7),
                )
                rows += 1
        self.stdout.write(f"Calendar rows: {rows}")

    # --------------------------------------------------------------- download

    def _download(self, frames):
        """Fetch the public JPEGs into media/original/ and media/small/."""
        self.stdout.write("Fetching frames from eol.jsc.nasa.gov ...")
        for name, directory, *_ in frames:
            filename = f"{name}.JPG"
            for size, folder in (("large", "original"), ("small", "small")):
                target_dir = os.path.join(settings.MEDIA_ROOT, folder)
                os.makedirs(target_dir, exist_ok=True)
                target = os.path.join(target_dir, filename)
                if os.path.exists(target) and os.path.getsize(target) > 0:
                    self.stdout.write(f"  have {folder}/{filename}")
                    continue
                url = f"{IMAGE_BASE}/{directory.replace('large', size)}/{filename}"
                try:
                    response = requests.get(url, timeout=120)
                    response.raise_for_status()
                    if not response.headers.get("Content-Type", "").startswith("image/"):
                        raise ValueError("response was not an image")
                    with open(target, "wb") as handle:
                        handle.write(response.content)
                    kib = len(response.content) // 1024
                    self.stdout.write(
                        self.style.SUCCESS(f"  got  {folder}/{filename} ({kib} KiB)")
                    )
                except Exception as error:
                    self.stdout.write(
                        self.style.WARNING(f"  FAILED {folder}/{filename}: {error}")
                    )

    # ------------------------------------------------------------------ reset

    def _reset(self):
        """Remove what this command created, and nothing else."""
        user_model = get_user_model()
        batches = Batch.objects.filter(name=BATCH_NAME)
        images = Image.objects.filter(batch__in=batches).count()
        attempts = GeoAttempt.objects.filter(image__batch__in=batches).count()
        batches_deleted = batches.count()
        batches.delete()  # cascades to Image, and Image cascades to GeoAttempt

        seeded = user_model.objects.filter(email__endswith=f"@{EMAIL_DOMAIN}")
        users_deleted = seeded.count()
        GeoAttempt.objects.filter(assignedUser__in=seeded).update(assignedUser=None)
        seeded.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Removed {batches_deleted} batch(es), {images} image(s), "
                f"{attempts} attempt(s) and {users_deleted} invented account(s)."
            )
        )
        self.stdout.write("Files under media/ were left alone.")

    # ----------------------------------------------------------------- report

    def _report(self, superuser, researcher, volunteers, batch, password):
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Local dataset ready."))
        self.stdout.write("")
        port = os.environ.get("WEB_PORT", "8000")
        base = f"http://localhost:{port}"
        self.stdout.write(f"  Site          {base}/")
        self.stdout.write(f"  Admin         {base}/admin/")
        self.stdout.write(f"  Task page     {base}/gettask/{batch.pk}")
        self.stdout.write("")
        self.stdout.write(f"  Every account's password: {password}")
        self.stdout.write(f"  Superuser:   {superuser.email}")
        self.stdout.write(f"  Batch owner: {researcher.email}")
        for user in volunteers:
            self.stdout.write(f"  Volunteer:   {user.email}")
        self.stdout.write("")
        self.stdout.write(
            "Accounts and statistics are invented. Imagery and coordinates are "
            "NASA's, public domain. Nothing came from production."
        )
