import logging

from django.core.management.base import BaseCommand

__author__ = 'jorgealegre'

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Create document types for Ximpia API'
    can_import_settings = True

    def handle(self, *args, **options):
        pass
