import environ
import os
import sys
from pathlib import Path
# Initialize environ
ROOT_URLCONF = 'config.urls'
env = environ.Env(
    # set casting, default value
    DEBUG=(bool, True)
)
ALLOWED_HOSTS = ['127.0.0.1', 'localhost']

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Read the .env file
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

# Now use the variables
SECRET_KEY = env('SECRET_KEY')
DEBUG = env('DEBUG')

RUNNING_TESTS = 'pytest' in sys.modules or 'test' in sys.argv
USE_SQLITE = env.bool('USE_SQLITE', default=False)

# Use SQLite for tests so test runs do not depend on a manually created
# database. Local development can also opt into SQLite with USE_SQLITE=True.
if RUNNING_TESTS or USE_SQLITE:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / ('test_db.sqlite3' if RUNNING_TESTS else 'db.sqlite3'),
        }
    }
else:
    DATABASES = {
        'default': env.db(
            'DATABASE_URL',
            default='postgres://postgres:postgres@127.0.0.1:5678/subscription_db',
        )
    }
    DATABASES['default']['CONN_MAX_AGE'] = env.int('DB_CONN_MAX_AGE', default=0)

# ... at the bottom for Huey ...
HUEY = {
    'huey_class': 'huey.RedisHuey',
    'name': 'subtrack_tasks',
    'connection': {'host': 'localhost', 'port': 6379},
    'immediate': RUNNING_TESTS,
}
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware', # E410 fix
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware', # E408 fix
    'django.contrib.messages.middleware.MessageMiddleware', # E409 fix
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]
AUTH_USER_MODEL = 'users.User'
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',


    # Your Apps - Add these lines:
    'users.apps.UsersConfig',  # Change 'users' to this
    'subscriptions.apps.SubscriptionsConfig',

    # Third Party
    'huey.contrib.djhuey',
]
AUTH_PASSWORD_VALIDATORS = [
    # ... keep the default ones ...
    {
        'NAME': 'users.auth.validators.ComplexPasswordValidator',
    },
]


# The URL to use when referring to static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'

# This tells Django where to look for static files in your project folders
import os
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]

# This is where Django will "collect" all files for production (good to have now)
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE_BACKEND = 'django.contrib.staticfiles.storage.StaticFilesStorage'
if not DEBUG and not RUNNING_TESTS:
    STATICFILES_STORAGE_BACKEND = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': STATICFILES_STORAGE_BACKEND,
    },
}

# Add this to the bottom of settings.py
EMAIL_BACKEND = env(
    'EMAIL_BACKEND',
    default='django.core.mail.backends.console.EmailBackend',
)
DEFAULT_FROM_EMAIL = env(
    'DEFAULT_FROM_EMAIL',
    default='noreply@subscriptionintelligence.com',
)
EMAIL_HOST = env('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = env.int('EMAIL_PORT', default=587)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
EMAIL_USE_SSL = env.bool('EMAIL_USE_SSL', default=False)
IMAP_HOST = env('IMAP_HOST', default='imap.gmail.com')
IMAP_PORT = env.int('IMAP_PORT', default=993)
IMAP_USERNAME = env('IMAP_USERNAME', default=EMAIL_HOST_USER)
IMAP_PASSWORD = env('IMAP_PASSWORD', default=EMAIL_HOST_PASSWORD)
IMAP_MAILBOX = env('IMAP_MAILBOX', default='INBOX')
EMAIL_SCAN_LOOKBACK_DAYS = env.int('EMAIL_SCAN_LOOKBACK_DAYS', default=180)
EMAIL_SCAN_MAX_MESSAGES = env.int('EMAIL_SCAN_MAX_MESSAGES', default=200)
GMAIL_OAUTH_CLIENT_ID = env('GMAIL_OAUTH_CLIENT_ID', default='')
GMAIL_OAUTH_CLIENT_SECRET = env('GMAIL_OAUTH_CLIENT_SECRET', default='')
GMAIL_OAUTH_REDIRECT_URI = env('GMAIL_OAUTH_REDIRECT_URI', default='')
SHOW_LOGIN_TOKEN_IN_UI = env.bool('SHOW_LOGIN_TOKEN_IN_UI', default=DEBUG and not RUNNING_TESTS)
LOGIN_URL = '/accounts/login/'
CSRF_FAILURE_VIEW = 'users.auth.views.csrf_failure_view'
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
