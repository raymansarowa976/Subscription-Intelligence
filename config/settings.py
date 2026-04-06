import environ
import os
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

# ... down in the Database section ...
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'Subscription_Tracker',
        'USER': 'postgres',
        'PASSWORD': 'postgres',
        'HOST': '127.0.0.1',
        'PORT': '5678',
        'CONN_MAX_AGE': 0, # This prevents hanging connections
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
        'DIRS': [],
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
AUTH_USER_MODEL = 'users.CustomUser'
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
        'NAME': 'users.validators.ComplexPasswordValidator',
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