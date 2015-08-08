from django.core.management.base import BaseCommand
# import requests

__author__ = 'jorgealegre'


class Command(BaseCommand):
    help = 'System command to setup site'
    can_import_settings = True

    def handle(self, *args, **options):
        name = raw_input(u'Your Name')
        # Call API and POST data to setup site
        # Created indices, create groups staff and admin, add permissions is_admin and is_staff to user permissions
