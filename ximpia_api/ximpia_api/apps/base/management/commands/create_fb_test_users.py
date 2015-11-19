import logging
import json
from optparse import make_option
import pprint
import os

from django.core.management.base import BaseCommand
from django.conf import settings

from base.tests import create_fb_test_user_login

__author__ = 'jorgealegre'

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Create logged in test users for facebook with persistence'
    can_import_settings = True

    option_list = BaseCommand.option_list + (
        make_option('--feature',
                    action='store',
                    dest='feature',
                    default='base',
                    help='Feature'),
        make_option('--size',
                    action='store',
                    dest='size',
                    default=5,
                    help='Number users'),
    )

    def handle(self, *args, **options):
        """
        Create fb test users, make action to login for them.

        We associate test users with features, so they will be used attached to feature

        :param args:
        :param options:
        :return:
        """
        feature = options['feature']
        size = options['size']
        # Create and log in fb users
        path = '{}/apps/base/tests/data/fb_test_users.json'.format(settings.BASE_DIR)
        if os.path.isfile(path):
            f = open(path)
            users = json.loads(f.read())
            f.close()
        else:
            users = {
                'base': []
            }
        for user_counter in range(size):
            user_data = create_fb_test_user_login()
            if 'verbosity' in options and options['verbosity'] != '0':
                self.stdout.write(u'{}. {}'.format(
                    user_counter+1,
                    user_data.get('email', '')
                ))
            users.setdefault(feature, [])
            users[feature].append(user_data)
        if 'verbosity' in options and options['verbosity'] != '0':
            self.stdout.write(pprint.PrettyPrinter(indent=2).pformat(users))
        f = open(path, 'w')
        f.write(json.dumps(users, indent=2))
        f.close()
