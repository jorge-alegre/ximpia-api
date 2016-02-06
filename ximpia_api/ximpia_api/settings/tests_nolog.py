from tests import *


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
    },
    'loggers': {
        'django': {
            'handlers': ['logfile'],
            'propagate': True,
            'level': 'DEBUG',
        },
        'xp_user': {
            'handlers': ['logfile'],
            'propagate': True,
            'level': 'DEBUG',
        },
        'base': {
            'handlers': ['logfile'],
            'propagate': True,
            'level': 'DEBUG',
        },
        'document': {
            'handlers': ['logfile'],
            'propagate': True,
            'level': 'DEBUG',
        },
        'patterns': {
            'handlers': ['logfile'],
            'propagate': True,
            'level': 'DEBUG',
        },
        'query_build': {
            'handlers': ['logfile'],
            'propagate': True,
            'level': 'DEBUG',
        },
        'xp_sessions': {
            'handlers': ['logfile'],
            'propagate': True,
            'level': 'DEBUG',
        }
    }
}
