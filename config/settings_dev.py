from .settings_base import *
from django.core.management.utils import get_random_secret_key # type: ignore
import dj_database_url # type: ignore

DEBUG = True
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

SECRET_KEY = "dev-secret-key-not-for-production"

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://neondb_owner:npg_7nfYRuq8GiTZ@ep-proud-tooth-ahsdsq47-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require')

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
CSRF_TRUSTED_ORIGINS = ["http://127.0.0.1:8000", "http://localhost:8000"]
