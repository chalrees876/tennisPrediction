from .settings_dev import *

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