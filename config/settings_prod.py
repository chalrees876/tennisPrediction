import os
from .settings_base import *
import os

ALLOWED_HOSTS = [
    "127.0.0.1", "localhost",
    "18.216.90.98",        # your public IP
    ".compute-1.amazonaws.com",
"tennisml.duckdns.org"  # EC2 public DNS
]

def _csv(name, default=""):
    raw = os.getenv(name, default)
    # Return list, stripping whitespace and dropping empties
    return [x.strip() for x in raw.split(",") if x.strip()]

CSRF_TRUSTED_ORIGINS = [
    o for o in _csv("DJANGO_CSRF_TRUSTED_ORIGINS")
    if o.startswith("http://") or o.startswith("https://")
]
SECRET_KEY = os.environ["SECRET_KEY"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME"),
        "USER": os.getenv("DB_USER"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "HOST": os.getenv("DB_HOST"),
        "PORT": os.getenv("DB_PORT"),
    }
}

# Make sure logs go to ~/tennisapp/logs
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        },
    },
    "handlers": {
        "app_file": {
            "class": "logging.FileHandler",
            "filename": str(LOG_DIR / "django.log"),
            "formatter": "verbose",
        },
    },
    "loggers": {
        # your custom logger used by views
        "tennis": {"handlers": ["app_file"], "level": "INFO", "propagate": False},

        # CRITICAL: log 500s/tracebacks raised by views/middleware
        "django.request": {"handlers": ["app_file"], "level": "ERROR", "propagate": False},

        # Optional: DB errors
        "django.db.backends": {"handlers": ["app_file"], "level": "ERROR", "propagate": False},
    },
}