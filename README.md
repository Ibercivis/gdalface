To be completed



## Instalation in development mode


## Instalation in production mode with gunicorn (in Ubuntu/Debian)
1. Install supervisord `sudo apt-get install supervisor`
2. Install gunicorn (already in requirements.txt)
4. Install `nginx`: `sudo apt install nginx`
5. Install WeasyPrint system libraries (needed to render the diploma PDFs):
   `sudo apt-get install libpango-1.0-0 libpangocairo-1.0-0 libpangoft2-1.0-0 libgdk-pixbuf-2.0-0 libffi-dev libharfbuzz-subset0`
   The Python package `weasyprint` is already in requirements.txt; these are the
   native libraries it loads at runtime. Without them PDF generation raises an
   `OSError` about a missing `libpango`/`libgobject`.






For detailed installation, see [INSTALL.md](INSTALL.md)


# Usage


## Public stats contract

Each project exposes a small, uniform JSON snapshot so external dashboards can
pull the same shape from every deployment. The contract is the schema below —
keep `schema_version`, `project`, `generated_at` and `metrics` stable; only add
new keys to `metrics`, never rename or repurpose old ones.

**Endpoint (pull):** `GET /.well-known/stats.json` — CORS-open
(`Access-Control-Allow-Origin: *`), `Cache-Control: public, max-age=3600`.

```json
{
  "schema_version": "1.0",
  "project": { "id": "lostatnight", "name": "Lost at Night", "url": "https://lostatnight.org" },
  "generated_at": "2026-05-30T00:00:00+00:00",
  "metrics": { "participants": 107 }
}
```

| Field | Meaning |
| ----- | ------- |
| `schema_version` | Contract version. Bump only on breaking changes. |
| `project.id` / `.name` / `.url` | Project identity, from `PROJECT_STATS_IDENTITY` in `settings.py`. |
| `generated_at` | UTC ISO-8601 timestamp of the snapshot. |
| `metrics.participants` | Distinct users with a verified email (matches the homepage count). |

**How it works:** `georeferencing/stats.py` is the single source of truth
(`build_stats`/`write_snapshot`). A daily `django-rq` job
(`georeferencing.tasks.write_stats_snapshot`, scheduled in `georeferencing/apps.py`)
writes `media/stats.json` atomically; the view serves that snapshot and falls
back to a live compute if the file is missing. Adopting the standard in another
project = copy `stats.py`, the job, the route, and set `PROJECT_STATS_IDENTITY`.

## Contact form anti-spam

`/contact` is the only endpoint that emails the team; `POST /` (where the form
used to live) now answers 405. Submissions pass through these layers, in order:

1. **Honeypot** – hidden `website` field must stay empty.
2. **Signed timestamp** – `started_at` is issued with `django.core.signing`;
   submits younger than `CONTACT_MIN_SECONDS` (3 s) or older than 6 h, or with
   a forged signature, are dropped.
3. **JS token** – `form_token` is filled by inline JavaScript from the form's
   `data-k` attribute; scrapers that POST without running JS never set it.
4. **URL heuristic** – `CONTACT_MAX_URLS` (3) or more links, or a link in the
   name/subject, is dropped.
5. **Rate limit** – `CONTACT_RATE_LIMIT` (5) submissions per client IP per hour,
   counted in the shared Redis cache (`CACHES`, DB 3).
6. **Cloudflare Turnstile** (optional) – enabled only when both
   `TURNSTILE_SITE_KEY` and `TURNSTILE_SECRET_KEY` are set in `.env`. Create
   them at https://dash.cloudflare.com → *Turnstile* → *Add widget* with the
   `lostatnight.org` hostname (managed / non-interactive mode).

Layers 1–5 fail *silently*: the bot sees a normal "thanks" page and no mail is
sent, so it gets no signal about which check caught it. Every drop is logged
by `frontend.views` as `contact spam dropped: reason=<...> ip=<...>`.

## License

