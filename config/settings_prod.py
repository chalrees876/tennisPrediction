import os
from .settings_base import *
import os

ALLOWED_HOSTS = [
    "127.0.0.1", "localhost",
    "18.225.10.194",        # your public IP
    ".compute-1.amazonaws.com",
"tennisml.duckdns.org"  # EC2 public DNS
]

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
        "NAME": "tennisiqdatabase",
        "USER": "masteruser",
        "PASSWORD": "password",
        "HOST": "tennisiqdatabase.c7sgmciq2ehf.us-east-2.rds.amazonaws.com",
        "PORT": "5432",
    }
}
