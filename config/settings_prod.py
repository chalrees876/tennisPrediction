import os
from .settings_base import *
import os

def _csv(name, default=""):
    raw = os.getenv(name, default)
    # Return list, stripping whitespace and dropping empties
    return [x.strip() for x in raw.split(",") if x.strip()]


import dj_database_url
DATABASES = {
    'default': dj_database_url.config(default=os.getenv("DATABASE_URL"))
}


ALLOWED_HOSTS = _csv(
    "DJANGO_ALLOWED_HOSTS",
    "tennisbetsmart.com,www.tennisbetsmart.com,tennisml.duckdns.org,localhost,127.0.0.1",
)


CSRF_TRUSTED_ORIGINS = _csv(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    "https://tennisbetsmart.com,https://www.tennisbetsmart.com,https://tennisml.duckdns.org",
)

SECRET_KEY = os.environ["SECRET_KEY"]

if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY env var is not set")

DEBUG = True


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": True},
        "django.template": {"handlers": ["console"], "level": "ERROR", "propagate": True},
    },
}
