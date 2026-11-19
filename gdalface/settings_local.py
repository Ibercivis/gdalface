"""
Local development settings.

This module exists so that running the application on a laptop needs no edit to
`gdalface/settings.py`: everything production-specific is overridden here, and
production keeps reading `gdalface.settings` exactly as before.

Select it with the environment variable, as docker-compose.local.yml does:

    DJANGO_SETTINGS_MODULE=gdalface.settings_local

or per command:

    python manage.py <command> --settings=gdalface.settings_local
"""
# pylint: disable=wildcard-import,unused-wildcard-import

from decouple import config

from .settings import *  # noqa: F401,F403
from .settings import BASE_DIR, CACHES, RQ_QUEUES, TEMPLATES  # noqa: F401

DEBUG = True

# `challenge_detail.html` and `contact.html` include `_google_analytics.html`,
# which is not in the repository, so both pages return 500 on a fresh clone. A no-op
# stand-in under local_dev/templates/ keeps them working here without changing
# the shared templates.
TEMPLATES[0]["DIRS"] = [BASE_DIR / "local_dev" / "templates", *TEMPLATES[0]["DIRS"]]

# A value that is local to this file and used nowhere else. Production reads its
# own key from the environment.
SECRET_KEY = "local-development-only-not-a-secret"  # nosec

# Both lists come from the environment, defaulting to the values this file
# always had, so `docker-compose.local.yml` behaves exactly as before.
#
# They are configurable because this is not the only compose file that starts
# the site: another one serves it behind a reverse proxy, at a hostname of its
# own and with no port published on localhost (LOCAL-DEV.md says where). An
# address written into this file cannot be the address in both.
#
# "testserver" is the host Django's own test client uses, which is why it is in
# the default: nothing passes ALLOWED_HOSTS when the test suite runs.


def _list(name, default):
    """A comma-separated environment value as a list, blanks dropped."""
    return [item.strip() for item in config(name, default=default).split(",") if item.strip()]


ALLOWED_HOSTS = _list("ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0,web,testserver")

CSRF_TRUSTED_ORIGINS = _list(
    "CSRF_TRUSTED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000"
)

# Mail never leaves the machine. ACCOUNT_EMAIL_VERIFICATION stays 'mandatory',
# as in production, so the sign-up and password-reset flows behave exactly the
# same; the messages just land somewhere local.
#
# With EMAIL_HOST set (docker-compose.local.yml points it at the mailpit
# container) everything is delivered to the catcher's web inbox at
# http://localhost:8025/. Without it — running manage.py outside compose, for
# instance — mail is printed to the console instead, so nothing ever fails for
# want of an SMTP server.
EMAIL_HOST = config("EMAIL_HOST", default="")
if EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_PORT = config("EMAIL_PORT", default=1025, cast=int)
    EMAIL_USE_TLS = False
    EMAIL_USE_SSL = False
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

DEFAULT_FROM_EMAIL = "lostatnight-local@example.invalid"
DEFAULT_TO_EMAIL = ("lostatnight-local@example.invalid",)

# ManifestStaticFilesStorage needs `collectstatic` to have run and a manifest to
# exist. Serve the files straight from the apps instead.
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"

# `gdalface/settings.py` lists BASE_DIR/'static', which does not exist in the
# repository; the apps' own static directories are found by the app-directories
# finder. Dropping it removes a startup warning.
STATICFILES_DIRS = []

# Redis runs in its own container, not on localhost. Two things reach it: the
# scheduler's queues, and the cache the homepage, the rankings and the metrics
# read through -- a page whose cache cannot be reached answers 500, so this is
# not optional here.
_REDIS_HOST = config("REDIS_HOST", default="localhost")
for _queue in RQ_QUEUES.values():
    _queue["HOST"] = _REDIS_HOST

CACHES = {
    "default": {
        **CACHES["default"],
        "LOCATION": f"redis://{_REDIS_HOST}:6379/3",
    }
}
