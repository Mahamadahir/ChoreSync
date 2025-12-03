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
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'chore_sync.django_app.ChoreSyncConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
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
# Base frontend URL for redirects after OAuth/connect flows
FRONTEND_APP_URL = env('FRONTEND_APP_URL', default='http://localhost:5173')
# ---------------------------

# CORS / DRF
CORS_ALLOWED_ORIGINS = env.list(
    'CORS_ALLOWED_ORIGINS',
    default=['http://localhost:5173', 'http://127.0.0.1:5173']
)
CORS_ALLOW_CREDENTIALS = True
# Development convenience; tighten in production
CORS_ALLOW_ALL_ORIGINS = env.bool('CORS_ALLOW_ALL_ORIGINS', default=True)

CSRF_TRUSTED_ORIGINS = env.list(
    'CSRF_TRUSTED_ORIGINS',
    default=['http://localhost:5173', 'http://127.0.0.1:5173']
)

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
}

# Celery (placeholder; configure broker/url in environment)
CELERY_BROKER_URL = env('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND', default='redis://localhost:6379/0')

# Google OAuth
GOOGLE_OAUTH_CLIENT_ID = env('GOOGLE_OAUTH_CLIENT_ID', default='')
GOOGLE_OAUTH_CLIENT_SECRET = env('GOOGLE_OAUTH_CLIENT_SECRET', default='')
GOOGLE_OAUTH_REDIRECT_URI = env('GOOGLE_OAUTH_REDIRECT_URI', default='http://localhost:8000/api/calendar/google/callback/')
# Microsoft OAuth
MICROSOFT_CLIENT_ID = env('MICROSOFT_CLIENT_ID', default='')
MICROSOFT_TENANT_ID = env('MICROSOFT_TENANT_ID', default='common')

# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = 'static/'

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'chore_sync.User'
