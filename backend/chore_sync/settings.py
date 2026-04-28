"""
Django settings for chore_sync project.
...
"""

from pathlib import Path
import environ  # ⬅️ Import django-environ

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# --- ENVIRONMENT VARIABLE SETUP ---
env = environ.Env(
    # Set default values and cast types
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
    EMAIL_USE_TLS=(bool, True),
)

# Read the .env file (named secrets.env in your case)
# It should be in the BASE_DIR
environ.Env.read_env(BASE_DIR / 'secrets.env')
# ----------------------------------


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env.bool('DEBUG')

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS')


# Application definition

INSTALLED_APPS = [
    'daphne',  # must be first — overrides runserver with Daphne's ASGI server
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    # TikTok dev tip: enable blacklisting so rotated refresh tokens can't be reused if stolen
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_celery_beat',
    'django_celery_results',
    'auditlog',
    'chore_sync.django_app.ChoreSyncConfig',
    'channels',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'auditlog.middleware.AuditlogMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'chore_sync.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'chore_sync.wsgi.application'
ASGI_APPLICATION = 'chore_sync.asgi.application'

# Use Redis-backed channel layer when a broker URL is configured (staging/production).
# Falls back to InMemoryChannelLayer for local development (no Redis required).
_redis_url = env('CELERY_BROKER_URL', default='')
if _redis_url:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [_redis_url],
            },
        },
    }
else:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        },
    }

# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases
# Now loaded from the DATABASE_URL environment variable
DATABASES = {
    'default': env.db(
        'DATABASE_URL',
        default='postgres://choresync_user:choreSync@localhost:5432/choresync'
    )
}


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        "OPTIONS": {"min_length": 8},
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# --- EMAIL CONFIGURATION ---
# Static settings
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
# Sensitive settings loaded from environment
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS')
EMAIL_HOST_USER = env('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = f"ChoreSync Team <{EMAIL_HOST_USER}>"
# -----------------------------


# --- CUSTOM APP SETTINGS ---
# For your verification email links
FRONTEND_VERIFY_EMAIL_URL = env(
    'FRONTEND_VERIFY_EMAIL_URL',
    default='http://localhost:5173/verify-email' # Default for development
)
FRONTEND_RESET_PASSWORD_URL = env(
    'FRONTEND_RESET_PASSWORD_URL',
    default='http://localhost:5173/reset-password'
)
# Base frontend URL for redirects after OAuth/connect flows
FRONTEND_APP_URL = env('FRONTEND_APP_URL', default='http://localhost:5173')
# ---------------------------

# AI Assistant (Gemini)
GEMINI_API_KEY = env('GEMINI_API_KEY', default='')
GEMINI_MODEL = env('GEMINI_MODEL', default='gemma-4-31b-it')
GEMINI_FALLBACK_MODEL = env('GEMINI_FALLBACK_MODEL', default='gemma-3-27b-it')

# CORS / DRF
CORS_ALLOWED_ORIGINS = env.list(
    'CORS_ALLOWED_ORIGINS',
    default=['http://localhost:5173', 'http://127.0.0.1:5173',]
)
CORS_ALLOW_CREDENTIALS = True
# Development convenience; tighten in production
CORS_ALLOW_ALL_ORIGINS = env.bool('CORS_ALLOW_ALL_ORIGINS', default=False)
CORS_ALLOWED_ORIGIN_REGEXES = [
    r'^http://localhost:\d+$',
    r'^http://127\.0\.0\.1:\d+$',
]

CSRF_TRUSTED_ORIGINS = env.list(
    'CSRF_TRUSTED_ORIGINS',
    default=[
        'http://localhost:5173', 'http://127.0.0.1:5173',
    ]
)

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        # Session auth — used by the Vue web app (cookie-based)
        "rest_framework.authentication.SessionAuthentication",
        # JWT auth — used by the React Native mobile app (Bearer token)
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

from datetime import timedelta  # noqa: E402

SIMPLE_JWT = {
    # Short-lived access token; the RN app auto-refreshes silently
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    # Long-lived refresh token — user stays "logged in" for 90 days of inactivity
    "REFRESH_TOKEN_LIFETIME": timedelta(days=90),
    # Rotate refresh tokens on every refresh call so each token is single-use
    "ROTATE_REFRESH_TOKENS": True,
    # TikTok dev tip: blacklist the old refresh token after rotation — stolen tokens become useless after first use
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    # Include email + username in the token payload for convenience
    "TOKEN_OBTAIN_SERIALIZER": "chore_sync.api.jwt_views.ChoresSyncTokenObtainSerializer",
}

# Allow Google OAuth popup to communicate back via postMessage
SECURE_CROSS_ORIGIN_OPENER_POLICY = None

# Celery
CELERY_BROKER_URL = env('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = 'django-db'
CELERY_CACHE_BACKEND = 'django-cache'
CELERY_TASK_TRACK_STARTED = True

from celery.schedules import crontab  # noqa: E402

CELERY_BEAT_SCHEDULE = {
    'generate-daily-occurrences': {
        'task': 'chore_sync.tasks.generate_daily_occurrences',
        'schedule': crontab(hour=0, minute=0),
    },
    'dispatch-deadline-reminders': {
        'task': 'chore_sync.tasks.dispatch_deadline_reminders',
        'schedule': 900,  # every 15 minutes
    },
    'mark-overdue-tasks': {
        'task': 'chore_sync.tasks.mark_overdue_tasks',
        'schedule': 900,  # every 15 minutes
    },
    'cleanup-expired-swaps': {
        'task': 'chore_sync.tasks.cleanup_expired_swaps',
        'schedule': crontab(hour=2, minute=0),
    },
    'recalculate-leaderboard': {
        'task': 'chore_sync.tasks.recalculate_leaderboard',
        'schedule': 3600,  # every hour
    },
    'renew-google-watch-channels': {
        'task': 'chore_sync.tasks.renew_google_watch_channels',
        'schedule': crontab(hour=3, minute=0),  # daily at 03:00
    },
    'catchup-google-calendar-sync': {
        'task': 'chore_sync.tasks.catchup_google_calendar_sync',
        'schedule': 6 * 3600,  # every 6 hours
    },
    # Outlook / Microsoft Graph
    'refresh-outlook-tokens': {
        'task': 'chore_sync.tasks.refresh_outlook_tokens',
        'schedule': 30 * 60,  # every 30 minutes
    },
    'catchup-outlook-calendar-sync': {
        'task': 'chore_sync.tasks.catchup_outlook_calendar_sync',
        'schedule': 6 * 3600,  # every 6 hours
    },
    'renew-outlook-subscriptions': {
        'task': 'chore_sync.tasks.renew_outlook_subscriptions',
        'schedule': 2 * 3600,  # every 2 hours
    },
    'cleanup-expired-marketplace-listings': {
        'task': 'chore_sync.tasks.cleanup_expired_marketplace_listings',
        'schedule': 3600,  # every hour
    },
    'generate-smart-suggestions': {
        'task': 'chore_sync.tasks.generate_smart_suggestions',
        'schedule': crontab(hour=8, minute=0),  # daily at 08:00
    },
    'cleanup-stale-chatbot-sessions': {
        'task': 'chore_sync.tasks.cleanup_stale_chatbot_sessions',
        'schedule': crontab(hour=3, minute=30),  # daily at 03:30
    },
    'close-expired-vote-windows': {
        'task': 'chore_sync.tasks.close_expired_vote_windows',
        'schedule': 900,  # every 15 minutes
    },
    # TikTok dev tip: prune the OutstandingToken table nightly or it grows forever
    'flush-expired-jwt-tokens': {
        'task': 'chore_sync.tasks.flush_expired_jwt_tokens',
        'schedule': crontab(hour=4, minute=0),  # daily at 04:00
    },
}

# Route initial calendar syncs to a dedicated low-concurrency queue.
CELERY_TASK_ROUTES = {
    'chore_sync.tasks.initial_google_sync_task': {'queue': 'calendar_sync'},
    'chore_sync.tasks.initial_outlook_sync_task': {'queue': 'calendar_sync'},
}

# Google OAuth
GOOGLE_OAUTH_CLIENT_ID = env('GOOGLE_OAUTH_CLIENT_ID', default='')
# Additional Google OAuth client IDs for mobile (iOS + Android) — used for ID token audience validation
GOOGLE_MOBILE_CLIENT_IDS = env.list('GOOGLE_MOBILE_CLIENT_IDS', default=[])
GOOGLE_OAUTH_CLIENT_SECRET = env('GOOGLE_OAUTH_CLIENT_SECRET', default='')
GOOGLE_OAUTH_REDIRECT_URI = env('GOOGLE_OAUTH_REDIRECT_URI', default='http://localhost:8000/api/calendar/google/callback/')
GOOGLE_WEBHOOK_CALLBACK_URL = env('GOOGLE_WEBHOOK_CALLBACK_URL', default='')
# Microsoft OAuth
MICROSOFT_CLIENT_ID = env('MICROSOFT_CLIENT_ID', default='')
MICROSOFT_TENANT_ID = env('MICROSOFT_TENANT_ID', default='common')
MICROSOFT_CLIENT_SECRET = env('MICROSOFT_CLIENT_SECRET', default='')
OUTLOOK_OAUTH_REDIRECT_URI = env('OUTLOOK_OAUTH_REDIRECT_URI', default='http://localhost:8000/api/calendar/outlook/callback/')
# Public-facing base URL of this backend (must be HTTPS and internet-reachable for Graph webhooks to fire)
BACKEND_BASE_URL = env('BACKEND_BASE_URL', default='http://localhost:8000')
# Custom URI scheme for mobile OAuth redirects (deep link back into the app after calendar connect)
MOBILE_CALENDAR_REDIRECT_URI = env('MOBILE_CALENDAR_REDIRECT_URI', default='choresync://calendar/connected')
# Shared secret sent in every Graph change-notification; validated in the webhook receiver
OUTLOOK_WEBHOOK_SECRET = env('OUTLOOK_WEBHOOK_SECRET', default='')

# AI Assistant — Ollama-compatible endpoint and model
# Override in staging/production to point at OpenRouter, Groq, or any OpenAI-compatible API
OLLAMA_URL = env('OLLAMA_URL', default='http://localhost:11434/api/chat')
OLLAMA_MODEL = env('OLLAMA_MODEL', default='phi3:mini')
OPENROUTER_API_KEY = env('OPENROUTER_API_KEY', default='')

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "loggers": {
        "chore_sync": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
        "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}

# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files (user-uploaded content such as photo proofs)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'chore_sync.User'

FIELD_ENCRYPTION_KEY = env('FIELD_ENCRYPTION_KEY')
