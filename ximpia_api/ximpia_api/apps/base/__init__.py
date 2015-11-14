import requests
from requests.adapters import HTTPAdapter
import json
import logging
import os

from django.utils.translation import ugettext as _
from django.test.runner import DiscoverRunner
from django.core.management import call_command
from django.conf import settings

from constants import *
import exceptions

__author__ = 'jorgealegre'

logger = logging.getLogger(__name__)

req_session = requests.Session()
req_session.mount('https://graph.facebook.com', HTTPAdapter(max_retries=3))


class SocialNetworkResolution(object):

    @classmethod
    def get_app_access_token(cls, app_id, app_secret):
        """
        Get app access token

        :param app_id:
        :param app_secret:
        :return:
        """
        from document import Document
        from exceptions import DocumentNotFound
        if hasattr(settings, 'XIMPIA_FACEBOOK_APP_TOKEN') and settings.XIMPIA_FACEBOOK_APP_TOKEN:
            app_access_token = settings.XIMPIA_FACEBOOK_APP_TOKEN
        else:
            try:
                app = Document.objects.get('app', id=settings.APP_ID)
                app_access_token = app['social']['facebook']['access_token']
            except DocumentNotFound:
                response_raw = req_session.get('https://graph.facebook.com/oauth/access_token?'
                                               'client_id={app_id}&'
                                               'client_secret={app_secret}&'
                                               'grant_type=client_credentials'.format(
                                                   app_id=app_id,
                                                   app_secret=app_secret,
                                               ))
                if response_raw.status_code != 200:
                    raise exceptions.XimpiaAPIException(u'Error in validating Facebook response',
                                                        code=exceptions.SOCIAL_NETWORK_AUTH_ERROR)
                app_access_token = response_raw.content.split('|')[1]
        logger.info('SocialNetworkResolution :: app_access_token: {}'.format(app_access_token))
        return app_access_token

    @classmethod
    def _process_facebook(cls, *args, **kwargs):
        """
        Process facebook having access_token:
        1. Verify access token
        2. Get user data

        We need to get app access token

        :param args:
        :param kwargs:
        :return:
        """
        from document import Document
        from exceptions import DocumentNotFound

        request_access_token = kwargs.get('access_token', '')
        skip_auth_social = kwargs.get('skip_auth_social', False)

        # this is executed in case we don't have app access token in ximpia app data
        if hasattr(settings, 'XIMPIA_FACEBOOK_APP_TOKEN') and settings.XIMPIA_FACEBOOK_APP_TOKEN:
            app_access_token = settings.XIMPIA_FACEBOOK_APP_TOKEN
        else:
            try:
                app = Document.objects.get('app', id=settings.APP_ID)
                app_access_token = app['social']['facebook']['access_token']
            except DocumentNotFound:
                response_raw = req_session.get('https://graph.facebook.com/oauth/access_token?'
                                               'client_id={app_id}&'
                                               'client_secret={app_secret}&'
                                               'grant_type=client_credentials'.format(
                                                   app_id=kwargs.get('app_id', settings.XIMPIA_FACEBOOK_APP_ID),
                                                   app_secret=kwargs.get('app_secret',
                                                                         settings.XIMPIA_FACEBOOK_APP_SECRET),
                                               ))
                if response_raw.status_code != 200:
                    raise exceptions.XimpiaAPIException(u'Error in validating Facebook response',
                                                        code=exceptions.SOCIAL_NETWORK_AUTH_ERROR)
                print u'app access token response: {}'.format(response_raw.content)
                app_access_token = response_raw.content.split('access_token=')[1]
        logger.info('SocialNetworkResolution :: app_access_token: {}'.format(app_access_token))

        """
        {
            "data": {
                "app_id": 000000000000000,
                "application": "Social Cafe",
                "expires_at": 1352419328,
                "is_valid": true,
                "issued_at": 1347235328,
                "scopes": [
                    "email",
                    "publish_actions"
                ],
                "user_id": 1207059
            }
        }
        """
        request_url = 'https://graph.facebook.com/v2.5/debug_token?' \
                      'input_token={access_token}&access_token={app_token}'.format(
                          access_token=request_access_token,
                          app_token=app_access_token)
        print u'request_url: {}'.format(request_url)
        response = req_session.get(request_url)
        if response.status_code != 200:
            raise exceptions.XimpiaAPIException(u'Error in validating Facebook response :: {}'.format(
                response.content
            ),
                code=exceptions.SOCIAL_NETWORK_AUTH_ERROR)
        fb_data = response.json()
        print u'token data: {}'.format(fb_data)
        if skip_auth_social:
            # We don't need to require user has logged in, for tests. We simply verify token and user_id
            return {
                'user_id': fb_data['data']['user_id'],
                'scopes': fb_data['data']['scopes'],
                'access_token': request_access_token,
                'email': None,
                'name': str(fb_data['data']['user_id']),
                'link': None,
                'profile_picture': None
            }
        if fb_data['data']['app_id'] != settings.FACEBOOK_APP_ID or not fb_data['data']['is_valid']:
            raise exceptions.XimpiaAPIException(u'Error in validating Facebook response :: token is not valid',
                                                code=exceptions.SOCIAL_NETWORK_AUTH_ERROR)
        user_data = {
            'user_id': fb_data['data']['user_id'],
            'scopes': fb_data['data']['scopes'],
            'access_token': request_access_token
        }
        # call facebook for user name and email
        response = req_session.get('https://graph.facebook.com/v2.5/'
                                   'me?'
                                   'access_token={access_token}&fields=email,link,name'.format(
                                       user_id=user_data['user_id'],
                                       access_token=request_access_token
                                   ))
        if response.status_code != 200:
            raise exceptions.XimpiaAPIException(u'Error in validating Facebook response',
                                                code=exceptions.SOCIAL_NETWORK_AUTH_ERROR)
        detail_user_data = response.json()
        user_data.update({
            'email': detail_user_data.get('email', None),
            'name': detail_user_data.get('name', None),
            'link': detail_user_data.get('link', None),
        })
        response = req_session.get('https://graph.facebook.com/v2.5/'
                                   '{user_id}/picture?'
                                   'access_token={access_token}'.format(
                                       user_id=user_data['user_id'],
                                       access_token=request_access_token
                                   ))
        if response.status_code == 302:
            user_data.update({
                'profile_picture': response.url,
            })
        else:
            user_data.update({
                'profile_picture': None,
            })
        return user_data

    @classmethod
    def get_network_user_data(cls, social_network, *args, **kwargs):
        """
        Get normalized social network user data

        :param social_network:
        :param args:
        :param kwargs:
        :return:
        """
        if social_network == SOCIAL_NETWORK_FACEBOOK:
            return cls._process_facebook(*args, **kwargs)


def get_path_by_id(document_type, id_):
    """
    Get ES path by index, document type and id

    :param document_type:
    :param id_:
    :return:
    """
    return 'http://{host}/{index}/{document_type}/{_id}'.format(
        host=settings.ELASTIC_SEARCH_HOST,
        index=settings.SITE_BASE_INDEX,
        document_type=document_type,
        _id=id_)


def get_path_site(id_):
    """
    Get site by id

    :param id_:
    :return:
    """
    return 'http://{host}/{index}/{document_type}/{_id}'.format(
        host=settings.ELASTIC_SEARCH_HOST,
        index='ximpia_api__base',
        document_type='site',
        _id=id_)


def get_path_search(document_type, **kwargs):
    """
    Get ES path by index, document type for search

    :param document_type:
    :param id_:
    :param query_cache:
    :return:
    """
    query_cache = kwargs.get('query_cache', True)
    return 'http://{host}/{index}/{document_type}/_search?query_cache={query_cache}'.format(
        host=settings.ELASTIC_SEARCH_HOST,
        index=settings.SITE_BASE_INDEX,
        document_type=document_type,
        query_cache=query_cache)


def get_es_response(request_object, skip_exception=False):
    """
    Process request, get json and parse errors

    :param request_object:
    :return:
    """
    es_response_raw = request_object
    if es_response_raw.status_code != 200 or 'status' in es_response_raw and es_response_raw['status'] != 200:
        if skip_exception:
            pass
        else:
            raise exceptions.XimpiaAPIException(_(u'Error networking with database'))
    return es_response_raw.json()


def get_setting_value(value_node):
    """

    :param value_node:
    :return:
    """
    if value_node['int']:
        return value_node['int']
    if value_node['date']:
        return value_node['date']
    return value_node['value']


def get_setting_table_value(value_node):
    """

    :param value_node:
    :return:
    """
    table = {}
    for field, value in value_node.items():
        if value['int']:
            table[field] = value['int']
        if value['date']:
            table[field] = value['date']
        else:
            table[field] = value['value']
    return table


class XimpiaDiscoverRunner(DiscoverRunner):

    def __init__(self, *args, **kwargs):
        super(XimpiaDiscoverRunner, self).__init__(*args, **kwargs)

    def setup_databases(self, **kwargs):
        if self.verbosity >= 1:
            print 'Creating test indexes...'
        old_names = []
        mirrors = []
        # Call create_ximpia
        call_command('create_ximpia',
                     access_token=settings.XIMPIA_FACEBOOK_TOKENS[0],
                     social_network='facebook',
                     invite_only=False,
                     skip_auth_social=True)
        return old_names, mirrors

    def teardown_databases(self, old_config, **kwargs):
        if self.verbosity >= 1:
            print 'Destroying test indexes...'
        # delete ximpia_api index

    def setup_test_environment(self, **kwargs):
        os.environ['DJANGO_SETTINGS_MODULE'] = 'settings.test'
        super(XimpiaDiscoverRunner, self).setup_test_environment(**kwargs)
