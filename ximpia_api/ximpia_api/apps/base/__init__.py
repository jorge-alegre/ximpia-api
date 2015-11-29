import requests
from requests.adapters import HTTPAdapter
import logging
import json

from django.utils.translation import ugettext as _
from django.conf import settings

from constants import *
import exceptions

__author__ = 'jorgealegre'

logger = logging.getLogger(__name__)

req_session = requests.Session()
req_session.mount('https://graph.facebook.com', HTTPAdapter(max_retries=3))


class SocialNetworkResolution(object):

    @classmethod
    def get_app_access_token(cls, social_app_id, social_app_secret, app_id='ximpia_api__base'):
        """
        Get app access token

        :param social_app_id:
        :param social_app_secret:
        :return:
        """
        from document import Document
        from exceptions import DocumentNotFound
        try:
            app = Document.objects.get('app', id=app_id)
            app_access_token = app['social']['facebook']['access_token']
        except DocumentNotFound:
            response_raw = req_session.get('https://graph.facebook.com/oauth/access_token?'
                                           'client_id={social_app_id}&'
                                           'client_secret={social_app_secret}&'
                                           'grant_type=client_credentials'.format(
                                               social_app_id=social_app_id,
                                               social_app_secret=social_app_secret,
                                           ))
            if response_raw.status_code != 200:
                raise exceptions.XimpiaAPIException(u'Error in validating Facebook response',
                                                    code=exceptions.SOCIAL_NETWORK_AUTH_ERROR)
            app_access_token = response_raw.content.split('access_token=')[1]
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
        if 'app_id' not in kwargs and not kwargs['app_id']:
            raise exceptions.XimpiaAPIException(u'App Id not informed')

        # this is executed in case we don't have app access token in ximpia app data
        try:
            app = Document.objects.get('app', id=kwargs['app_id'], get_logical=True)
            app_access_token = app['social']['facebook']['access_token']
        except DocumentNotFound:
            response_raw = req_session.get('https://graph.facebook.com/oauth/access_token?'
                                           'client_id={app_id}&'
                                           'client_secret={app_secret}&'
                                           'grant_type=client_credentials'.format(
                                               app_id=kwargs['social_app_id'],
                                               app_secret=kwargs['social_app_secret'],
                                           ))
            if response_raw.status_code != 200:
                raise exceptions.XimpiaAPIException(u'Error in validating Facebook response',
                                                    code=exceptions.SOCIAL_NETWORK_AUTH_ERROR)
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
        response = req_session.get(request_url)
        if response.status_code != 200:
            raise exceptions.XimpiaAPIException(u'Error in validating Facebook response :: {}'.format(
                response.content
            ),
                code=exceptions.SOCIAL_NETWORK_AUTH_ERROR)
        fb_data = response.json()
        if fb_data['data']['app_id'] != settings.XIMPIA_FACEBOOK_APP_ID or not fb_data['data']['is_valid']:
            raise exceptions.XimpiaAPIException(u'Error in validating Facebook response :: token is not valid',
                                                code=exceptions.SOCIAL_NETWORK_AUTH_ERROR)
        user_data = {
            'user_id': fb_data['data']['user_id'],
            'scopes': fb_data['data']['scopes'],
            'access_token': request_access_token,
            'expires_at': fb_data['data']['expires_at']
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
            'first_name': detail_user_data.get('first_name', None),
            'last_name': detail_user_data.get('last_name', None),
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
    return '{host}/{index}/{document_type}/_search?query_cache={query_cache}'.format(
        host=settings.ELASTIC_SEARCH_HOST,
        index=kwargs.get('index', settings.SITE_BASE_INDEX),
        document_type=document_type,
        query_cache=query_cache)


def get_es_response(request_object, skip_exception=False):
    """
    Process request, get json and parse errors

    :param request_object:
    :return:
    """
    es_response_raw = request_object
    if es_response_raw.status_code != 200:
        if skip_exception:
            pass
        else:
            raise exceptions.XimpiaAPIException(_(u'Error networking with database'))
    es_response = es_response_raw.json()
    if 'status' in es_response and es_response['status'] != 200:
        if skip_exception:
            pass
        else:
            raise exceptions.XimpiaAPIException(_(u'Error networking with database'))
    return es_response


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


def get_base_app(site_slug):
    """
    Get base app for site

    We check for base app

    :param site_slug:
    :return:
    """
    from document import to_logical_doc
    es_path = get_path_search('app', index=u'{}__base'.format(site_slug))
    query_dsl = {
        'query': {
            'filtered': {
                'query': {
                    'bool': {
                        'must': [
                            {
                                'term': {
                                    'site__v1.slug__v1.raw__v1': site_slug
                                }
                            },
                            {
                                'term': {
                                    'slug__v1.raw__v1': 'base'
                                }
                            }
                        ]
                    }
                }
            }
        }
    }
    es_response_raw = req_session.get(es_path, data=json.dumps(query_dsl))
    if es_response_raw.status_code != 200:
        raise exceptions.DocumentNotFound(_(u'Error getting app "{}" :: {}'.format(
            u'{}.base'.format(site_slug),
            es_response_raw.content
        )))
    es_response = es_response_raw.json()
    if 'status' in es_response and es_response['status'] != 200:
        raise exceptions.DocumentNotFound(_(u'Error getting app "{}" :: {}'.format(
            u'{}.base'.format(site_slug),
            es_response_raw.content
        )))
    app = es_response['_source']
    app['id'] = es_response['_id']
    return to_logical_doc('app', app)


def refresh_index(index):
    """
    Refresh index

    :param index:
    :return:
    """
    req_session.post(
        '{}/{}/_refresh'.format(settings.ELASTIC_SEARCH_HOST, index)
    )
