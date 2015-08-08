from django.core.management.base import BaseCommand

__author__ = 'jorgealegre'

"""

Command or web access???

Ideal world....

1. User connects to http://api_host/setup
2. Connects to Twitter, Facebook, Gmail
3. Name, optional username: Would create user attached to admin group

"""


class Command(BaseCommand):
    help = ''
    can_import_settings = True

    def handle(self, *args, **options):
        # 1. Input user info about admin: username??? password
        pass
