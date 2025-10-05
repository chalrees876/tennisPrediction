import os
from .settings_base import *

DEBUG = False
ALLOWED_HOSTS = [os.environ.get("PUBLIC_HOST", "")]

SECRET_KEY = os.environ["SECRET_KEY"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "myproject"),
        "USER": os.getenv("DB_USER", "myprojectuser"),
        "PASSWORD": os.getenv("DB_PASSWORD", "password"),
        "HOST": os.getenv("DB_HOST", "localhost"),
        "PORT": os.getenv("DB_PORT", "5432"),
    }
}

CSRF_TRUSTED_ORIGINS = [f'https://{os.environ.get("PUBLIC_HOST", "")}']
