import os
from .settings_base import *

DEBUG = False
ALLOWED_HOSTS = [os.environ.get("PUBLIC_HOST", "")]

# Real secrets only from environment (set on the server)
SECRET_KEY = os.environ["SECRET_KEY"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["DB_NAME"],
        "USER": os.environ["DB_USER"],
        "PASSWORD": os.environ["DB_PASSWORD"],
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
    }
}

CSRF_TRUSTED_ORIGINS = [f'https://{os.environ.get("PUBLIC_HOST", "")}']
