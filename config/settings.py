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

# Default to PostgreSQL for development, but use SQLite for tests so test runs
# do not depend on a manually created local database.
if RUNNING_TESTS:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'test_db.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': env('DB_ENGINE', default='django.db.backends.postgresql'),
            'NAME': env('DB_NAME', default='Subscription_Tracker'),
            'USER': env('DB_USER', default='postgres'),
            'PASSWORD': env('DB_PASSWORD', default='postgres'),
            'HOST': env('DB_HOST', default='127.0.0.1'),
            'PORT': env('DB_PORT', default='5678'),
            'CONN_MAX_AGE': env.int('DB_CONN_MAX_AGE', default=0),
        }
    }

# ... at the bottom for Huey ...
HUEY = {
    'huey_class': 'huey.RedisHuey',
    'name': 'subtrack_tasks',
    'connection': {'host': 'localhost', 'port': 6379},
}
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
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
    'subscriptions',

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

# Add this to the bottom of settings.py
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
