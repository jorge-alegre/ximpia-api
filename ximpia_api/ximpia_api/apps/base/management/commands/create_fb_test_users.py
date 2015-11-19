import logging
import json

from django.core.management.base import BaseCommand
from django.conf import settings

from base.tests import create_fb_test_user_login

__author__ = 'jorgealegre'

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Create logged in test users for facebook with persistence'
    can_import_settings = True

    def handle(self, *args, **options):
        """
        Create fb test users, make action to login for them.

        We associate test users with features, so they will be used attached to feature

        :param args:
        :param options:
        :return:
        """
        feature = options.get('feature', 'base')
        size = options.get('size', 5)
        # Create and log in fb users
        with open('{}apps/base/tests/data/fb_test_users.json'.format(settings.BASE_DICT)) as f:
            users = json.loads(f.read())
        for user_counter in range(size):
            user_data = create_fb_test_user_login()
            users[feature].append(user_data)
