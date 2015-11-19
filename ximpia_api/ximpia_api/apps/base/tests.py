import requests
import os
import json

from requests.adapters import HTTPAdapter

from django.conf import settings
from django.test.runner import DiscoverRunner
from django.core.management import call_command
from django.utils.translation import ugettext as _

from . import exceptions

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
    request_url = 'https://graph.facebook.com/v2.5/{app_id}/accounts/test-users?access_token={app_token}'.format(
        app_token=app_access_token,
        app_id=settings.XIMPIA_FACEBOOK_APP_ID)
    response = req_session.post(request_url,
                                data=json.dumps({'installed': True}))
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


class XimpiaDiscoverRunner(DiscoverRunner):

    def __init__(self, *args, **kwargs):
        super(XimpiaDiscoverRunner, self).__init__(*args, **kwargs)

    def setup_databases(self, **kwargs):
        """
        Create indices with mappings and Ximpia API site with user, groups, settings

        :param kwargs:
        :return:
        """
        if self.verbosity >= 1:
            print 'Creating test indexes...'
        old_names = []
        mirrors = []
        # Call create_ximpia
        call_command('create_ximpia',
                     access_token=settings.XIMPIA_FACEBOOK_TOKENS[0],
                     social_network='facebook',
                     invite_only=False,
                     skip_auth_social=True,
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
            print 'Destroying test indexes...'
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

    def setup_test_environment(self, **kwargs):
        os.environ['DJANGO_SETTINGS_MODULE'] = 'settings.test'
        # Create sample of FB users ( 5 ), linked to test
        # Login all users by making form submission for user/password
        super(XimpiaDiscoverRunner, self).setup_test_environment(**kwargs)

    def teardown_test_environment(self, **kwargs):
        # Delete all users
        super(XimpiaDiscoverRunner, self).teardown_test_environment(**kwargs)
