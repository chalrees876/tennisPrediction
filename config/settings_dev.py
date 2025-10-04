from .settings_base import *
from django.core.management.utils import get_random_secret_key

DEBUG = True
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

SECRET_KEY = "dev-secret-key-not-for-production"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "myproject",
        "USER": "myprojectuser",
        "PASSWORD": "devpassword",
        "HOST": "127.0.0.1",
        "PORT": "5432",
    }
}

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
CSRF_TRUSTED_ORIGINS = ["http://127.0.0.1:8000", "http://localhost:8000"]
