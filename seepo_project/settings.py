from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file.
# override=True prevents inherited shell vars from forcing stale local DB settings.
load_dotenv(BASE_DIR / '.env', override=True)

SECRET_KEY = os.getenv('SECRET_KEY', 'seepo-dev-secret-key-change-in-production-2024')

DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 'yes')

ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')

# Build ALLOWED_HOSTS from env
_allowed_hosts = os.getenv('ALLOWED_HOSTS', '*')
ALLOWED_HOSTS = [h.strip() for h in _allowed_hosts.split(',') if h.strip()]
# Always include these hosts
ALLOWED_HOSTS.extend(['seepo.co.ke', 'www.seepo.co.ke', 'staging.seepo.co.ke'])

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    # SEEPO apps
    'accounts',
    'groups',
    'members',
    'finance',
    'reports',
    'offline_sync',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'seepo_project.urls'

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
                'accounts.context_processors.notifications',
            ],
        },
    },
]

WSGI_APPLICATION = 'seepo_project.wsgi.application'

if ENVIRONMENT == 'development':
    default_db_engine = 'django.db.backends.mysql'
    default_db_name = 'seepo_dev'
    default_db_user = 'root'
    default_db_password = ''
    default_db_host = '127.0.0.1'
    default_db_port = '3306'
else:
    default_db_engine = 'django.db.backends.postgresql'
    default_db_name = 'seepocok_main'
    default_db_user = 'seepocok_devmain'
    default_db_password = ''
    default_db_host = 'localhost'
    default_db_port = '5432'

DATABASES = {
    'default': {
        'ENGINE': os.getenv('DB_ENGINE', default_db_engine),
        'NAME': os.getenv('DB_NAME', default_db_name),
        'USER': os.getenv('DB_USER', default_db_user),
        'PASSWORD': os.getenv('DB_PASSWORD', default_db_password),
        'HOST': os.getenv('DB_HOST', default_db_host),
        'PORT': os.getenv('DB_PORT', default_db_port),
    }
}

DATABASESx3 = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

AUTH_USER_MODEL = 'accounts.User'

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Nairobi'
USE_I18N = True
USE_TZ = True

# Don't redirect POST requests from /admin to /admin/ (prevents 500 errors)
APPEND_SLASH = False

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

# Additional static file handling for cPanel
STATIC_HOST = ''  # Will be empty for relative URLs
if 'seepo.co.ke' in os.getenv('ALLOWED_HOSTS', '*'):
    STATIC_HOST = 'https://seepo.co.ke'
elif 'staging.seepo.co.ke' in os.getenv('ALLOWED_HOSTS', '*'):
    STATIC_HOST = 'https://staging.seepo.co.ke'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

# ── Logging Configuration ─────────────────────────────────────────────────────
LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': LOG_DIR / 'django.log',
            'formatter': 'verbose',
        },
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': LOG_DIR / 'error.log',
            'formatter': 'verbose',
        },
        'static_file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': LOG_DIR / 'static.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'error_file'],
            'level': 'INFO',
            'propagate': True,
        },
        'django.request': {
            'handlers': ['error_file'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.staticfiles': {
            'handlers': ['static_file', 'console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'django.server': {
            'handlers': ['file', 'console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}
