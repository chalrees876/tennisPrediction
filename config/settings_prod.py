import os
from .settings_base import *

DEBUG = False
import os

def _split_env(name):
    return [x.strip() for x in os.environ.get(name, "").split(",") if x.strip()]

ALLOWED_HOSTS = _split_env("ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = _split_env("CSRF_TRUSTED_ORIGINS")

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