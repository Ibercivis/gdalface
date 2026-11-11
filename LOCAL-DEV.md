# Running LostAtNight locally

A local instance with a small sample of data, using **no data from production**.

Everything here is additive: `Dockerfile.local`, `docker-compose.local.yml`,
`gdalface/settings_local.py`, `local_dev/` and one management command. No file the
production deployment reads has been changed.

## Why there is no production data in here

The only personal data this application holds lives in three tables — `auth_user`,
`account_emailaddress` and `user_profile_userprofile`. Everything else (batches, images,
georeferencing attempts) is NASA imagery metadata and coordinates, and carries nothing about
anybody.

That split is what makes a production extract unnecessary rather than merely undesirable:

- **The realistic half can be rebuilt from the public source.** The photographs are ISS night
  frames from NASA's Gateway to Astronaut Photography of Earth. They are public domain and
  `eol.jsc.nasa.gov` serves the JPEGs without an API key, so the sample uses the real images with
  their real published coordinates.
- **The half that would have carried personal data is the half that is cheapest to invent.**
  Accounts exist here only as actors: somebody has to own a batch, and somebody has to have
  completed attempts so the rankings are not empty. Any five made-up people do that job as well as
  five real ones.

So there is nothing to anonymise, because nothing personal is copied in the first place. GDPR does
not come into it.

## What you need

Docker. Nothing else — Python 3.12, PostgreSQL 16, Redis and the GDAL binaries all live in the
containers.

## Start it

```bash
docker compose -f docker-compose.local.yml up -d --build
docker compose -f docker-compose.local.yml exec web python manage.py migrate
docker compose -f docker-compose.local.yml exec web python manage.py seed_local
```

Then open <http://localhost:8000/>. The caught-mail inbox is at <http://localhost:8025/>.

If something already holds port 8000, set `WEB_PORT` for every command in the session (and
`MAIL_UI_PORT` if 8025 is taken too):

```bash
export WEB_PORT=8010
docker compose -f docker-compose.local.yml up -d
```

## What the sample contains

`seed_local` creates, by default, 6 images, 3 volunteers and 18 attempts:

| | |
|---|---|
| **Images** | Real ISS night frames with city lights, over northern Spain, the sea off Andalusia and the Kantō region of Japan. Their `photoCenterPoint` and `spacecraftNadirPoint` are the coordinates NASA publishes for those frames. |
| **Batch** | One, of type `LIST`, owned by the invented researcher account. |
| **Attempts** | A third `DONE` (with control points and timings), a third `ASSIGNED`, a third `PENDING`, so the task page always has something to hand out. |
| **People** | One superuser, one batch owner, three volunteers — all invented, with profiles, countries and statistics that agree with their attempts. |

The frames are genuine *night* photographs, which matters: most of NASA's archive is daylight, and
a daylight frame is a useless sample for an application that georeferences city lights. They were
chosen by measuring the images, not by trusting their captions — `local_dev/find_night_frames.py`
is the script that applies the test (mostly black, with bright points in it) and can find more.

Options:

```bash
python manage.py seed_local --images 9 --volunteers 3 --replicas 5
python manage.py seed_local --no-download     # rows only, no JPEGs
python manage.py seed_local --reset           # remove what a previous run created
```

Re-running it is safe, and is how you refill the `PENDING` queue after draining it.

## Accounts

Every account's password is `devpass12345` (`--password` changes it). The addresses are on the
reserved `.invalid` domain, so none of them can reach a mailbox.

| Account | Role |
|---|---|
| `admin@lostatnight.invalid` | superuser, for `/admin/` |
| `researcher@lostatnight.invalid` | staff, owns the batch |
| `volunteer1@lostatnight.invalid` … `volunteer3@` | volunteers with contributions |

`ACCOUNT_EMAIL_VERIFICATION` stays `'mandatory'` as in production, so the seeded accounts are
given confirmed `EmailAddress` rows and can sign in at once.

## Mail

**No mail leaves the machine, and none of it reaches a real mailbox.** The flows themselves are
unchanged — sign-up really does demand a confirmation, password reset really does send a link — but
every message is caught by the `mailpit` container.

Open the inbox at **<http://localhost:8025/>** and click the link in the message. That is the whole
loop: sign up, open the inbox, confirm, sign in. Set `MAIL_UI_PORT` if 8025 is taken.

This matters beyond convenience. `ACCOUNT_EMAIL_VERIFICATION` is `'mandatory'`, so typing a real
address into a local sign-up form would, with a working mail backend, send a real person a real
message from a development machine. The catcher makes that impossible rather than unlikely.

If you run `manage.py` outside compose, `EMAIL_HOST` is unset and mail is printed to the console
instead, so nothing fails for want of an SMTP server. To read mail from the log that way:

```bash
docker compose -f docker-compose.local.yml logs -f web
```

## What `settings_local.py` changes, and why

| Override | Reason |
|---|---|
| `DEBUG`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` | Serve on localhost. |
| `EMAIL_BACKEND` → SMTP to mailpit, else console | No AWS SES credentials locally, and no message should ever reach a real mailbox. |
| `STATICFILES_STORAGE` → plain | `ManifestStaticFilesStorage` needs a `collectstatic` manifest. |
| `STATICFILES_DIRS` → `[]` | `settings.py` lists `BASE_DIR/'static'`, which is not in the repository. |
| `SECRET_KEY` | A value local to that file. |
| `RQ_QUEUES[*]['HOST']` | Redis is a container, not `localhost`. |
| `TEMPLATES[0]['DIRS']` | See the first known issue below. |

## Known issues in the application, found while setting this up

These are pre-existing and reproduce on a fresh clone of `main`. None of them is caused by this
setup, and none is fixed by it — the local environment works around the first one only.

1. **`/batchs` and `/contact` return 500 on any fresh clone.** Both templates do
   `{% include '_google_analytics.html' %}`, but that template is not in the repository; it exists
   only on the production host, untracked. `local_dev/templates/` holds a no-op stand-in that is
   reachable only through `settings_local`, so the two pages work here while the gap stays visible.
   Note for whoever fixes it properly: adding a tracked copy will collide with the untracked file
   already on the server, and that deploy needs a hand.

2. **`GET /api/v1/geoattempt/` returns 500.** `MiniGeoAttemptSerializer` declares a field named
   `created`; the model's field is `createdDateTime`. Django REST Framework raises
   `ImproperlyConfigured` on every request. This fails in production too.

3. **The `PENDING` queue drains as you work.** Handing a task out moves it off `PENDING`, so a short
   sample runs out sooner than you expect. Re-run `seed_local` to refill it, or seed with
   `--replicas 5` as production does.

4. **`Image.save()` prints `self.focalLength` to stdout** on every save, so seeding prints a column
   of `None`. Harmless, and it is the application's own line, not this tooling's.

5. **`drf-yasg` 1.21.7 imports `pkg_resources`**, which pip no longer installs by default on Python
   3.12. `Dockerfile.local` asks for `setuptools<81` explicitly. A production venv created before
   this change still has it, so the matching deployment has not noticed yet.

## Limits of the local instance

- **The map's base and overlay tiles are fetched from the internet** — OpenStreetMap, and the VIIRS
  and SDGSAT layers from `lostatnight.org`. Both answer fine from a laptop, so the map works, but
  the instance is not fully offline. (OpenStreetMap blocks headless browsers; in a normal browser
  it loads.)
- **Georeferencing a task end to end** runs `gdal_translate` and `gdalwarp`, which are in the
  image, but has not been exercised here beyond the task page rendering.
- **The batch-creation flow through the UI needs a `NASA_API_KEY`**, because it searches NASA's
  metadata API, which does require a key. `seed_local` sidesteps it: the static image files need no
  key, and the coordinates are baked into the command.
