import os
from .settings_base import *
import os

def _csv(name, default=""):
    raw = os.getenv(name, default)
    # Return list, stripping whitespace and dropping empties
    return [x.strip() for x in raw.split(",") if x.strip()]

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


SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# Tell Django the original scheme/IP when proxied
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Optional: tighten referrers for CSRF (leave off if you use cross-site POSTs)
CSRF_COOKIE_HTTPONLY = True