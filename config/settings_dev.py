from .settings_base import *
from django.core.management.utils import get_random_secret_key

DEBUG = True
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

# A committed, harmless dev key. (Fine for local only.)
SECRET_KEY = "dev-secret-key-not-for-production"

# Zero-setup DB locally so you can just run the site
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Dev niceties
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
CSRF_TRUSTED_ORIGINS = ["http://127.0.0.1:8000", "http://localhost:8000"]
