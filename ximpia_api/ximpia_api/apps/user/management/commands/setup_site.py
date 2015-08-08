from django.core.management.base import BaseCommand

__author__ = 'jorgealegre'


class Command(BaseCommand):
    help = ''
    can_import_settings = True

    def handle(self, *args, **options):
        # 1. Input user info about admin
        pass
