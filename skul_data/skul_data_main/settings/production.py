# skul_data_main/settings/production.py

from .base import *
from decouple import config, Csv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

DEBUG = False

# Update ALLOWED_HOSTS to include your Render domain
ALLOWED_HOSTS = config(
    "DJANGO_ALLOWED_HOSTS",
    default="skul-data.onrender.com,localhost,127.0.0.1",
    cast=Csv(),
)

SECRET_KEY = config("SECRET_KEY")

# Database
# DATABASES = {
#     "default": {
#         "ENGINE": "django.db.backends.postgresql",
#         "NAME": config("DATABASE_NAME"),
#         "USER": config("DATABASE_USER"),
#         "PASSWORD": config("DATABASE_PASSWORD"),
#         "HOST": config("DB_HOST", default="localhost"),
#         "PORT": config("DB_PORT", default="5432"),
#     }
# }

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Static files
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "mediafiles"

# Security settings for production
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# CSRF trusted origins - add your frontend domains
CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS",
    cast=Csv(),
    default="https://skul-data-frontend.onrender.com,'https://skul-data.onrender.com',",
)

# CORS settings - IMPORTANT: Update these for security
CORS_ALLOW_ALL_ORIGINS = False  # Change this to False for production
CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    cast=Csv(),
    default="https://skul-data-frontend.onrender.com",
)

# Additional CORS settings
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]

# Logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}

# # Email backend (you can configure SMTP for production emails)
# EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
# EMAIL_HOST = config("EMAIL_HOST", default="smtp.gmail.com")
# EMAIL_PORT = config("EMAIL_PORT", cast=int, default=587)
# EMAIL_USE_TLS = True
# EMAIL_HOST_USER = config("EMAIL_HOST_USER")
# EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD")

# # Celery broker in production (e.g., Redis on Render)
# CELERY_BROKER_URL = config("CELERY_BROKER_URL")
# CELERY_RESULT_BACKEND = config("CELERY_RESULT_BACKEND", default=CELERY_BROKER_URL)
