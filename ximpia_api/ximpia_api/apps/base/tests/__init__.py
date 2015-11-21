import requests
import os
import json
import time

from requests.adapters import HTTPAdapter

from django.conf import settings
from django.test.runner import DiscoverRunner
from django.core.management import call_command
from django.utils.translation import ugettext as _

from base import exceptions

__author__ = 'jorgealegre'

req_session = requests.Session()
req_session.mount('https://graph.facebook.com', HTTPAdapter(max_retries=3))


def create_fb_test_user():
    """
    Create Facebook test user

    :return:
    """
    app_access_token = settings.XIMPIA_FACEBOOK_APP_TOKEN
    # /v2.5/{app-id}/accounts/test-users
    request_url = 'https://graph.facebook.com/v2.5/{app_id}/accounts/test-users?access_token={app_token}&' \
                  'permissions=email'.format(
                      app_token=app_access_token,
                      app_id=settings.XIMPIA_FACEBOOK_APP_ID)
    response = req_session.post(request_url,
                                data=json.dumps({
                                    'installed': True
                                }))
    if response.status_code != 200:
        raise exceptions.XimpiaAPIException(u'Error in validating Facebook response :: {}'.format(
            response.content
        ),
            code=exceptions.SOCIAL_NETWORK_AUTH_ERROR)
    fb_data = response.json()
    return fb_data


def create_fb_test_user_login():
    """
    Create and login FB user data

    :return:
    """
    user_data = create_fb_test_user()
    # login user
    session_fb = requests.Session()
    session_fb.get("https://www.facebook.com/", allow_redirects=True)
    response = session_fb.get(
        'https://www.facebook.com/login.php'
    )
    response = session_fb.post("https://www.facebook.com/login.php",
                               data={
                                   'email': user_data["email"],
                                   'pass': user_data["password"]
                               })
    if response.status_code != 200:
        raise exceptions.XimpiaAPIException(u'Error in validating Facebook response',
                                            code=exceptions.SOCIAL_NETWORK_AUTH_ERROR)
    return user_data


def fb_test_user_login(user_data):
    """
    Login fb test user

    :return:
    """
    # login user
    session_fb = requests.Session()
    session_fb.get("https://www.facebook.com/", allow_redirects=True)
    response = session_fb.get(
        'https://www.facebook.com/login.php'
    )
    response = session_fb.post("https://www.facebook.com/login.php",
                               data={
                                   'email': user_data["email"],
                                   'pass': user_data["password"]
                               })
    if response.status_code != 200:
        raise exceptions.XimpiaAPIException(u'Error in validating Facebook response',
                                            code=exceptions.SOCIAL_NETWORK_AUTH_ERROR)
    return user_data


def delete_fb_test_user(user_id):
    """
    Delete facebook test user

    :param user_id:
    :return:
    """
    app_access_token = settings.XIMPIA_FACEBOOK_APP_TOKEN
    # /v2.5/{app-id}/accounts/test-users
    request_url = 'https://graph.facebook.com/v2.5/{app_id}/accounts/test-users?' \
                  'access_token={app_token}&uid={user_id}'.format(
                      app_token=app_access_token,
                      app_id=settings.XIMPIA_FACEBOOK_APP_ID,
                      user_id=user_id)
    response = req_session.delete(request_url)
    if response.status_code != 200:
        raise exceptions.XimpiaAPIException(u'Error in validating Facebook response :: {}'.format(
            response.content
        ),
            code=exceptions.SOCIAL_NETWORK_AUTH_ERROR)
    data = response.json()
    if 'success' not in data and not data['success']:
        raise exceptions.XimpiaAPIException(u'Error in validating Facebook response :: {}'.format(
            response.content
        ),
            code=exceptions.SOCIAL_NETWORK_AUTH_ERROR)


def get_fb_test_user_local(feature):
    """
    Get local fb test user random

    :param feature:
    :return:
    """
    from random import choice
    path = '{}/apps/base/tests/data/fb_test_users.json'.format(settings.BASE_DIR)
    with open(path) as f:
        users = json.loads(f.read())
        if feature in users:
            return choice(users[feature])
        else:
            raise exceptions.XimpiaAPIException(u'feature not found in local test users')


class XimpiaDiscoverRunner(DiscoverRunner):

    def __init__(self, *args, **kwargs):
        super(XimpiaDiscoverRunner, self).__init__(*args, **kwargs)
        self.admin_user = None

    def setup_databases(self, **kwargs):
        """
        Create indices with mappings and Ximpia API site with user, groups, settings

        :param kwargs:
        :return:
        """
        old_names = []
        mirrors = []
        # get test user
        user_data = get_fb_test_user_local('admin')
        if self.verbosity >= 1:
            print u'Creating test indexes...'
        # Call create_ximpia
        call_command('create_ximpia',
                     access_token=user_data['access_token'],
                     social_network='facebook',
                     invite_only=False,
                     verbosity=self.verbosity)
        return old_names, mirrors

    def teardown_databases(self, old_config, **kwargs):
        """
        Drop indices

        :param old_config:
        :param kwargs:
        :return:
        """
        if self.verbosity >= 1:
            print u'Destroying test indexes...'
        # delete ximpia_api index
        # Get all indices
        # curl -XGET 'http://192.168.99.100:9201/_recovery?pretty'
        es_response_raw = requests.get('{}/_recovery'.format(settings.ELASTIC_SEARCH_HOST))
        if es_response_raw.status_code not in [200, 201]:
            raise exceptions.XimpiaAPIException(_(u'Could not get indices :: {}'.format(
                es_response_raw.content
            )))
        es_response = es_response_raw.json()
        indices = es_response.keys()
        for index in indices:
            # curl -XDELETE 'http://localhost:9200/twitter/'
            es_response_raw = requests.delete('{}/{}/'.format(
                settings.ELASTIC_SEARCH_HOST,
                index
            ))
            if es_response_raw.status_code not in [200, 201]:
                raise exceptions.XimpiaAPIException(_(u'Could not delete index "{}" :: {}'.format(
                    index,
                    es_response_raw.content,
                )))

    @classmethod
    def _create_test_users(cls):
        """
        Create all test users

        :return:
        """
        call_command('create_fb_test_users', feature='admin', size=1)
        call_command('create_fb_test_users', feature='registration', size=5)

    def setup_test_environment(self, **kwargs):
        """
        Setup test environment

        :param kwargs:
        :return:
        """
        import shutil
        os.environ['DJANGO_SETTINGS_MODULE'] = 'settings.test'
        # Create fb_test_users.json
        path = '{}apps/base/tests/data/fb_test_users.json'.format(settings.BASE_DIR)
        path_src = '{}apps/base/tests/data/fb_test_users-src.json'.format(settings.BASE_DIR)
        if not os.path.isfile(path):
            if self.verbosity >= 1:
                print 'Creating test users file...'
            data = {}
            f = open(path, 'w')
            # create expires 3600 seconds
            data['expires'] = int(time.time()) + 5000
            f.write(json.dumps(data, indent=2))
            f.close()
            # call command create users for features
            self._create_test_users()
        else:
            # login users again
            f = open(path)
            data = json.loads(f.read())
            f.close()
            # check expires
            if int(time.time()) > int(data['expires']):
                if self.verbosity >= 1:
                    print 'Will login test users...'
                f = open(path, 'r')
                data = json.loads(f.read())
                f.close()
                # login users again
                for feature in data.keys():
                    if feature == 'expires':
                        continue
                    for user_data in data[feature]:
                        if self.verbosity >= 1:
                            print 'logging [{}] {}...'.format(
                                feature,
                                user_data['email'],
                            )
                        fb_test_user_login(user_data)
                # create expires 3600 seconds
                f = open(path, 'w')
                data['expires'] = int(time.time()) + 5000
                f.write(json.dumps(data, indent=2))
                f.close()
        super(XimpiaDiscoverRunner, self).setup_test_environment(**kwargs)

    def teardown_test_environment(self, **kwargs):
        """
        TearDown environment

        :param kwargs:
        :return:
        """
        super(XimpiaDiscoverRunner, self).teardown_test_environment(**kwargs)
