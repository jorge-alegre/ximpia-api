"""
Django settings for ximpia project.

Generated by 'django-admin startproject' using Django 1.8.3.

For more information on this file, see
https://docs.djangoproject.com/en/1.8/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.8/ref/settings/
"""

__author__ = 'jorgealegre'

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/'


sys.path.append('{}/ximpia_api/apps/'.format(os.getcwd()))
sys.path.append('{}/ximpia_api/'.format(os.getcwd()))
sys.path.append('{}'.format(os.getcwd()))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.8/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'wqmz=)2ac28dyt5&ox72i@t*bz5+8(36gkxuczb--@l$^c7vzc'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []


# Application definition


INSTALLED_APPS = (
    'xp_user',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'base',
    'document',
    'patterns',
    'query_build',
    'xp_sessions'
)

MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'base.middleware.XimpiaUrlsMiddleware',
)

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'xp_user.backends.XimpiaAuthBackend',
        'rest_framework.authentication.SessionAuthentication',
    )
}

ROOT_URLCONF = 'urls'

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

WSGI_APPLICATION = 'wsgi.application'


# Database
# https://docs.djangoproject.com/en/1.8/ref/settings/#databases

DATABASES = {}


# Internationalization
# https://docs.djangoproject.com/en/1.8/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.8/howto/static-files/

STATIC_URL = '/static/'

XIMPIA_FACEBOOK_APP_ID = '981166675280371'
XIMPIA_FACEBOOK_APP_SECRET = '01aa291d3f3e519d9430675af008deed'
XIMPIA_FACEBOOK_APP_TOKEN = '981166675280371|Dq76b80QKO9eSqcl2KvKgYrPGCI'

MY_SITE_FACEBOOK_APP_ID = '991722957558076'
MY_SITE_FACEBOOK_APP_SECRET = 'a8e8b03dc38cd3cecb77e3cfe895a598'
MY_SITE_APP_ACCESS_TOKEN = '991722957558076|si3sICvrZPEYsSnQawdYwsD1JRE'

ELASTIC_SEARCH_HOST = 'http://elasticsearch-test:9200'
# XIMPIA_IO_HOST = 'http://dev-web'
XIMPIA_IO_HOST = 'http://testserver'

SESSION_ENGINE = 'xp_sessions.backends.db'
AUTHENTICATION_BACKENDS = (
    'xp_user.backends.XimpiaAuthBackend',
)

XIMPIA_DOMAIN = 'ximpia.io'
SITE_BASE_INDEX = u'ximpia-api__base'
SITE = 'Ximpia API'

TEST_RUNNER = 'base.tests.XimpiaDiscoverRunner'

DEFAULT_GROUPS = [
    u'users',
    u'users-test',
    u'admin',
    u'staff'
]

DEFAULT_GROUPS_NORMAL_USER = [
    u'users',
]

DEFAULT_VERSION = 'v1'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': {
        'standard': {
            'format': "[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s",
            'datefmt': "%d/%b/%Y %H:%M:%S"
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse'
        }
    },
    'handlers': {
        'logfile': {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': 'DEBUG',
            'filename': '/home/ximpia/log/django-test.log',
            'maxBytes': 1024*1024*25,
            'backupCount': 5,
            'formatter': 'standard'
        },
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler'
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['logfile', 'console'],
            'propagate': True,
            'level': 'DEBUG',
        },
        'xp_user': {
            'handlers': ['logfile', 'console'],
            'propagate': True,
            'level': 'DEBUG',
        },
        'base': {
            'handlers': ['logfile', 'console'],
            'propagate': True,
            'level': 'DEBUG',
        },
        'document': {
            'handlers': ['logfile', 'console'],
            'propagate': True,
            'level': 'DEBUG',
        },
        'patterns': {
            'handlers': ['logfile', 'console'],
            'propagate': True,
            'level': 'DEBUG',
        },
        'query_build': {
            'handlers': ['logfile', 'console'],
            'propagate': True,
            'level': 'DEBUG',
        },
        'xp_sessions': {
            'handlers': ['logfile', 'console'],
            'propagate': True,
            'level': 'DEBUG',
        }
    }
}
