from django.core.management.base import BaseCommand

__author__ = 'jorgealegre'

"""

Command or web access???

Ideal world....

1. User connects to http://api_host/setup

or https://{site}.ximpia.com/

2. Connects to Twitter, Facebook, Gmail: Using JS and social network buttons
3. Site name / Project name

"""


class Command(BaseCommand):
    help = ''
    can_import_settings = True

    def handle(self, *args, **options):
        # 1. Input user info about admin: username??? password
        pass
