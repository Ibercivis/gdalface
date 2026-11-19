# Running LostAtNight locally

A local instance with a small sample of data, using **no data from production**.

The environment itself is additive: `Dockerfile.local`, `docker-compose.local.yml`,
`gdalface/settings_local.py`, `local_dev/` and one management command. No file the production
deployment reads is changed by any of it.

Signing in with an Ibercivis account, further down, is not additive — it is a change to the site,
and it touches `gdalface/settings.py`, `requirements.txt`, the sign-in templates and the personal
area. That section says what it changes.

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

**What it does not create:** challenges, teams, diplomas, the review queue and the NASA photo
catalogue. Those pages render, empty, and the rankings show only what the seeded attempts add up
to. Signing in and reading a profile is what this environment is for; everything else is scenery,
and seeding it would mean inventing a plausible community rather than a handful of actors.

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
| `DEBUG`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` | Serve on localhost. The last two default to that and are read from the environment, so another compose file can serve this site at a hostname of its own — see below. |
| `EMAIL_BACKEND` → SMTP to mailpit, else console | No AWS SES credentials locally, and no message should ever reach a real mailbox. |
| `STATICFILES_STORAGE` → plain | `ManifestStaticFilesStorage` needs a `collectstatic` manifest. |
| `STATICFILES_DIRS` → `[]` | `settings.py` lists `BASE_DIR/'static'`, which is not in the repository. |
| `SECRET_KEY` | A value local to that file. |
| `RQ_QUEUES[*]['HOST']` | Redis is a container, not `localhost`. |
| `CACHES['default']['LOCATION']` | The same reason, and not optional: the homepage, `/ranking/` and the metrics read through this cache, and all three answer 500 when it cannot be reached. |
| `TEMPLATES[0]['DIRS']` | See the first known issue below. |

## Served at a hostname instead of a port

`ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` are read from the environment, as comma-separated
lists, and default to exactly what they were before: `localhost`, `127.0.0.1`, `0.0.0.0`, `web`,
`testserver`, and `http://localhost:8000`. `docker-compose.local.yml` sets neither, so nothing
above changes.

They exist because this site is also started by a second compose file, in
[`Ibercivis/citsci-federation`](https://github.com/Ibercivis/citsci-federation). That one runs this
application together with the other Ibercivis citizen science applications and a shared sign-in
service, behind one reverse proxy: every application is reached by a hostname of its own and
publishes no port on localhost, so that cookies, redirect URIs and CORS behave as they do in
production rather than only on a laptop. That repository's `docs/adr/0009-the-pilot-is-one-docker-composition.md`
is where the reasoning lives. Nothing in this repository depends on it, and none of it runs unless
you start it.

## Signing in with an Ibercivis account

The site accepts a second way in: an account held by the sign-in service the Ibercivis citizen
science sites share, reached over OpenID Connect. `django-allauth` ships that provider, so the
whole hook is configuration in `gdalface/settings.py` — three values read from the environment:

| | |
|---|---|
| `IBERCIVIS_ACCOUNT_ISSUER` | the service's address |
| `IBERCIVIS_ACCOUNT_CLIENT_ID` | the name this site is registered there under |
| `IBERCIVIS_ACCOUNT_CLIENT_SECRET` | what authenticates this site when it exchanges the code |

**The stack in this file declares none of them, so no button appears here.** That is deliberate:
this stack starts the site on its own, and there is no sign-in service beside it to reach. The
composition in [`Ibercivis/citsci-federation`](https://github.com/Ibercivis/citsci-federation)
starts both, and that is where signing in this way is tried — its README says how.

What it changes in the site:

- **Local sign-up is closed.** `/accounts/signup/` no longer creates an account; it sends a
  newcomer to the Ibercivis button instead. Two adapters in `gdalface/adapters.py` do it, and both
  are needed: allauth's social adapter answers "may this person sign up?" by asking the account
  adapter, so closing the form without the second class would close the Ibercivis door with it.
- **Nothing about the accounts that already exist.** Email and password still sign in, address
  confirmation is still mandatory for them, password reset is untouched, and there is no date on
  which any of it stops working.
- **No address is confirmed twice, and none is confirmed here.**
  `SOCIALACCOUNT_EMAIL_VERIFICATION` is `'none'` in `gdalface/settings.py`: the site sends no
  confirmation of its own for an account arriving from a provider, which is right for Google,
  because Google has confirmed the address before it says so. The Ibercivis service answers the
  same question in `email_verified`, and when it answers no, the account is still created and
  signed in on an address nobody checked. allauth offers no per-provider override of that setting,
  so holding the Ibercivis door to the stricter rule would take code in
  `gdalface/adapters.py`; it is not written, and the case in
  `gdalface/tests_ibercivis_account.py` says plainly what the site does today.
- **The personal area shows the identifier** the Ibercivis account is known by. It is the same
  string on every Ibercivis site, which is the point of it, and it is the only thing the site
  stores about the account: nothing says which Google, ORCID or password the person used.
- An account created this way has **no password on this site** to recover or to lose.
- **An address already in use here gets no second account, and no first one either.** An address
  is one account on this site, so somebody who already signs in with a password cannot arrive at
  the same address from Ibercivis and be handed a second one: nobody is signed in, nothing is
  created, and allauth writes to the address itself — the only party entitled to know it exists —
  rather than saying so on screen. `/accounts/signup/` says this, and a case pins it.

  This is the one place where the Ibercivis provider is configured away from the site's own
  default. `SOCIALACCOUNT_EMAIL_AUTHENTICATION` is `True` here: an address a provider affirms,
  already held by an account on this site, signs into that account — and allauth wipes that
  account's password when it does. That is the decision this site made for Google, which has
  worked that way for years, and nothing changes it. It is not extended to this provider:
  `'email_authentication': False` sits in the provider's own `settings` block, which allauth reads
  before the global one. Linking an account that already exists here to an Ibercivis account is an
  act for whoever owns both, not something a matching address does by itself.
- **Nothing anonymous changes.** Measured on 19 November 2026 against `main`'s latest commit:
  `/`, `/gettask`, `/contact`, `/ranking/`, `GET /api/v1/image/` and `GET /api/v1/geoattempt/`
  answer without an account, `/api/v1/geoattempts-calendar/` answers 403 as it always did, and
  `/user-profile/` still answers 302 to the sign-in pages.
- **Nothing outside the web registered an account before this change, and nothing does now.**
  `api/v1/` is the georeferencing surface only: `georeferencing/urls.py` carries no registration
  route and no token endpoint, and no `dj-rest-auth` or equivalent is installed. So closing the
  form closes the only door there was.

The cases are in `gdalface/tests_ibercivis_account.py` and `user_profile/tests.py`:

```bash
docker compose -f docker-compose.local.yml exec web python manage.py test
```

They talk to no network and need no sign-in service, so they run in this stack as they stand.

## Known issues in the application, found while setting this up

These are pre-existing and reproduce on a fresh clone of `main`. None of them is caused by this
setup, and none is fixed by it — the local environment works around the first two only.

1. **A challenge page and `/contact` return 500 on any fresh clone.** Both templates do
   `{% include '_google_analytics.html' %}`, but that template is not in the repository; it exists
   only on the production host, untracked. `local_dev/templates/` holds a no-op stand-in that is
   reachable only through `settings_local`, so the two pages work here while the gap stays visible.
   Note for whoever fixes it properly: adding a tracked copy will collide with the untracked file
   already on the server, and that deploy needs a hand.

2. **`NASA_API_KEY` has no default**, so four of the application's own tests in
   `georeferencing/test_import_task_list.py` error out where the variable is unset — including in
   CI, if CI ever reaches them. They build the cache directory they read and make no request, so
   `docker-compose.local.yml` hands them a placeholder and the whole suite runs green here. The
   catalogue commands (`fetch_nasa_cache`, `enrich_images`, `import_task_list`) do make real
   requests and need a real key.

3. **The Django CI workflow fails before it runs anything.** `.github/workflows/django.yml` passes
   `${{ matrix.python-version }}` to `actions/setup-python` without declaring a matrix, so the job
   dies in "Set up job" and neither `pylint` nor the test suite has run on `main` — the run for
   `main`'s latest commit is red for that reason alone. Both pass locally on this branch:
   `pylint $(git ls-files '*.py')` scores 8.00 against the `fail-under=7.5` in `.pylintrc`.

4. **The `PENDING` queue drains as you work.** Handing a task out moves it off `PENDING`, so a
   short sample runs out sooner than you expect. Re-run `seed_local` to refill it, or seed with
   `--replicas 5` as production does.

5. **`drf-yasg` 1.21.7 imports `pkg_resources`**, which pip no longer installs by default on Python
   3.12. `Dockerfile.local` asks for `setuptools<81` explicitly. A production venv created before
   this change still has it, so the matching deployment has not noticed yet.

## Limits of the local instance

- **The map's base and overlay tiles are fetched from the internet** — Esri World Dark Gray as the
  basemap, the VIIRS night-lights layer from `lostatnight.org` and NASA's Black Marble from GIBS.
  All three answer fine from a laptop, so the map works, but the instance is not fully offline.
- **Georeferencing a task end to end** runs `gdal_translate` and `gdalwarp`, which are in the
  image, but has not been exercised here beyond the task page rendering.
- **The batch-creation flow through the UI needs a `NASA_API_KEY`**, because it searches NASA's
  metadata API, which does require a key. `seed_local` sidesteps it: the static image files need no
  key, and the coordinates are baked into the command.
