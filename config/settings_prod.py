import os
from .settings_base import *
import os

ALLOWED_HOSTS = ["127.0.0.1", "localhost", "18.225.10.194", ".compute-1.amazonaws.com"]


def _csv(name, default=""):
    raw = os.getenv(name, default)
    # Return list, stripping whitespace and dropping empties
    return [x.strip() for x in raw.split(",") if x.strip()]

CSRF_TRUSTED_ORIGINS = _csv(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    "http://127.0.0.1:8000,http://localhost:8000,https://tennisml.duckdns.org",
)

SECRET_KEY = os.environ["SECRET_KEY"]

if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY env var is not set")

DEBUG = os.getenv("DEBUG", "0") in ("1", "true", "True")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME"),
        "USER": os.getenv("DB_USER"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "HOST": os.getenv("DB_HOST"),
        "PORT": os.getenv("DB_PORT"),
        "OPTIONS": {"connect_timeout": 5}
    }
}
