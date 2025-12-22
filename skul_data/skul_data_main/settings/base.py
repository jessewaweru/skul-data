from pathlib import Path
from decouple import config
from datetime import timedelta
from celery.schedules import crontab
import sys
import os


AUTH_USER_MODEL = "users.User"

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

PROJECT_ROOT = BASE_DIR.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config("SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []

# CORS Configuration - Update these sections
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
CORS_ALLOW_CREDENTIALS = True

# Session Configuration - Update these
SESSION_COOKIE_SAMESITE = "Lax"  # Changed from 'None'
SESSION_COOKIE_SECURE = False  # Changed for development (set to True in production)
CSRF_COOKIE_SECURE = False  # Changed for development (set to True in production)
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False

# Add these session settings
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = 86400  # 24 hours
SESSION_SAVE_EVERY_REQUEST = True

# Application definition

DJANGO_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]
PROJECT_APPS = [
    "skul_data.reports",
    "skul_data.schools",
    "skul_data.users",
    "skul_data.notifications",
    "skul_data.documents",
    "skul_data.students",
    "skul_data.action_logs",
    "skul_data.scheduler",
    "skul_data.analytics",
    "skul_data.school_timetables",
    "skul_data.fee_management",
    "skul_data.exams",
    "skul_data.kcse",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",  # Add this for token blacklisting
    "drf_yasg",
    "django_celery_results",
    "django_celery_beat",
    "corsheaders",
    "channels",
    "django_filters",
    "django_otp",
    "django_otp.plugins.otp_totp",
]

INSTALLED_APPS = DJANGO_APPS + PROJECT_APPS + THIRD_PARTY_APPS

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/hour",  # Anonymous users
        "user": "1000/hour",  # Authenticated users
        "password_reset": "3/hour",  # Password reset requests
    },
}

AUTHENTICATION_BACKENDS = [
    "skul_data.users.models.base_user.CustomUserModelBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# JWT Settings - Update token lifetime for testing
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),  # Increased for better UX
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
}

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "skul_data.action_logs.middleware.action_log.ActionLogMiddleware",
    "skul_data.users.models.base_user.CurrentUserMiddleware",
]

ROOT_URLCONF = "skul_data.skul_data_main.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "skul_data.skul_data_main.wsgi.application"

# Configure ASGI application
ASGI_APPLICATION = "skul_data.skul_data_main.asgi.application"

# Channel layers configuration (using Redis)
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [(config("REDIS_HOST", "localhost"), 6379)],
        },
    },
}

# Override channel layers for testing web sockets in notifications app
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}
# Database

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("DATABASE_NAME"),
        "USER": config("DATABASE_USER"),
        "PASSWORD": config("DATABASE_PASSWORD"),
        "HOST": config("DB_HOST", default="localhost"),
        "PORT": config("DB_PORT", default="5432"),
    }
}

# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {
            "min_length": 8,
        },
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/

STATIC_URL = "static/"
MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

# Verify it's correct
print(f"MEDIA_ROOT is set to: {MEDIA_ROOT}")

# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SWAGGER_SETTINGS = {
    "SECURITY_DEFINITIONS": {
        "Bearer": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": 'JWT authorization. Example: "Bearer {token}"',
        }
    },
    "USE_SESSION_AUTH": False,
    "JSON_EDITOR": True,
    "PERSIST_AUTH": True,
    "DEEP_LINKING": True,
}

REDOC_SETTINGS = {
    "LAZY_RENDERING": False,
}

# Celery Configuration
CELERY_BROKER_URL = config("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = "django-db"  # Using django_celery_results
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "Africa/Nairobi"  # Set your timezone
CELERY_ENABLE_UTC = True
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes timeout for tasks
CELERY_RESULT_EXPIRES = 7 * 24 * 60 * 60  # 7 days expiration for results

# Celery Beat Configuration
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_BEAT_SCHEDULE = {
    "process-pending-report-requests": {
        "task": "skul_data.reports.utils.tasks.process_pending_report_requests",
        "schedule": 300.0,  # Every 5 minutes
        "options": {
            "expires": 60.0,
        },
    },
    "generate-term-end-reports": {
        "task": "skul_data.reports.utils.tasks.generate_term_end_reports",
        "schedule": crontab(
            day_of_month=1, hour=3, minute=0
        ),  # Use crontab instead of dict
    },
    "cleanup-old-reports": {
        "task": "skul_data.reports.utils.tasks.cleanup_old_reports",
        "schedule": crontab(hour=4, minute=30),  # Daily at 4:30am
    },
    "check-overdue-fees": {
        "task": "skul_data.fee_management.tasks.check_overdue_fees",
        "schedule": crontab(hour=8, minute=0),  # Daily at 8:00 AM
    },
    "send-fee-reminders": {
        "task": "skul_data.fee_management.tasks.send_scheduled_fee_reminders",
        "schedule": crontab(
            hour=10, minute=0, day_of_week=1
        ),  # Every Monday at 10:00 AM
    },
    "cleanup-expired-otps": {
        "task": "skul_data.users.tasks.cleanup_expired_otps",
        "schedule": crontab(hour=2, minute=0),  # Daily at 2:00 AM
    },
}

# Add logging to debug authentication issues
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "django.contrib.auth": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": True,
        },
        "rest_framework_simplejwt": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": True,
        },
    },
}

X_FRAME_OPTIONS = "SAMEORIGIN"

# ============================================================================
# EMAIL CONFIGURATION
# ============================================================================

# Choose your email backend based on environment
# For development/testing: Use console backend (emails print to terminal)
# For production: Use SMTP backend with your email service

# DEVELOPMENT: Console Backend (prints emails to console)
# Uncomment this for development/testing
# EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# PRODUCTION: SMTP Backend
# Uncomment and configure one of the options below for production

# # Option 1: Gmail SMTP
# EMAIL_BACKEND = config("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
# EMAIL_HOST = config("EMAIL_HOST", "smtp.gmail.com")
# EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
# EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
# EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
# EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
# DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", "Skul Data <noreply@skuldata.com>")

# Option 2: Zoho ZeptoMail SMTP (uncomment to use)
EMAIL_BACKEND = config("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = config("EMAIL_HOST", "smtp.zeptomail.com")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_HOST_USER = config(
    "EMAIL_HOST_USER", "emailapikey"
)  # ZeptoMail uses 'emailapikey' as username
EMAIL_HOST_PASSWORD = config(
    "EMAIL_HOST_PASSWORD", default=""
)  # Your ZeptoMail API key
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", "Skul Data <noreply@yourdomain.com>")

# Email timeout settings
EMAIL_TIMEOUT = 10  # seconds

# For production, also consider:
# EMAIL_USE_SSL = False  # Use TLS instead of SSL for port 587
# EMAIL_SSL_CERTFILE = None
# EMAIL_SSL_KEYFILE = None

# ============================================================================
# SMS CONFIGURATION
# ============================================================================

# SMS Configuration
AFRICASTALKING_USERNAME = config("AFRICASTALKING_USERNAME", default="")
AFRICASTALKING_API_KEY = config("AFRICASTALKING_API_KEY", default="")

# Enable SMS notifications
ENABLE_SMS_NOTIFICATIONS = True

# Frontend URL (for activation links)
FRONTEND_URL = config("FRONTEND_URL", default="http://localhost:5173")

# ============================================================================
# NOTIFICATION SETTINGS
# ============================================================================

# Control which notification channels are active
NOTIFICATION_CHANNELS = {
    "database": True,  # Always enabled - stores notifications in DB
    "websocket": True,  # Real-time notifications (already working)
    "email": True,  # Email notifications (now configured)
    "sms": False,  # SMS notifications (disabled until Twilio is configured)
}

# ============================================================================
# SECURITY SETTINGS
# ============================================================================

# Password Reset Settings
PASSWORD_RESET_TIMEOUT = 600  # 10 minutes (in seconds)
PASSWORD_RESET_MAX_ATTEMPTS = 3  # Max OTP verification attempts

# Account Lockout Settings (for future implementation)
ACCOUNT_LOCKOUT_THRESHOLD = 5  # Failed login attempts before lockout
ACCOUNT_LOCKOUT_DURATION = 1800  # 30 minutes (in seconds)

# Session Security
SESSION_COOKIE_AGE = 86400  # 24 hours
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# For production, set these to True:
# SESSION_COOKIE_SECURE = True
# CSRF_COOKIE_SECURE = True
# SECURE_SSL_REDIRECT = True
# SECURE_HSTS_SECONDS = 31536000
# SECURE_HSTS_INCLUDE_SUBDOMAINS = True
# SECURE_HSTS_PRELOAD = True
