import requests
from requests.adapters import HTTPAdapter
import json

from django.utils.translation import ugettext as _
from django.conf import settings

from constants import *
import exceptions

__author__ = 'jorgealegre'


class SocialNetworkResolution(object):

    @classmethod
    def _process_facebook(cls, *args, **kwargs):
        """
        Process facebook having access_token:
        1. Verify access token
        2. Get user data

        :param args:
        :param kwargs:
        :return:
        """
        req_session = requests.Session()
        req_session.mount('https://graph.facebook.com', HTTPAdapter(max_retries=3))
        access_token = kwargs.get('access_token', '')
        response = req_session.get('https://graph.facebook.com/debug_token?'
                                   'input_token={access_token}&'
                                   'access_token={app_token}'.format(
                                       access_token,
                                       app_token=settings.FACEBOOK_APP_TOKEN
                                    ))
        if response.status_code != 200:
            raise exceptions.XimpiaAPIException(u'Error in validating Facebook response',
                                                code=exceptions.SOCIAL_NETWORK_AUTH_ERROR)
        fb_data = json.loads(response.content)
        if fb_data['data']['app_id'] != settings.FACEBOOK_APP_ID or not fb_data['data']['is_valid']:
            raise exceptions.XimpiaAPIException(u'Error in validating Facebook response',
                                                code=exceptions.SOCIAL_NETWORK_AUTH_ERROR)
        user_data = {
            'user_id': fb_data['data']['user_id'],
            'scopes': fb_data['data']['scopes'],
            'access_token': access_token
        }
        # call facebook for user name and email
        response = req_session.get('https://graph.facebook.com/v2.4/'
                                   '{user_id}?'
                                   'access_token={access_token}'.format(
                                       user_id=user_data['user_id'],
                                       access_token=kwargs.get('access_token', '')
                                   ))
        if response.status_code != 200:
            raise exceptions.XimpiaAPIException(u'Error in validating Facebook response',
                                                code=exceptions.SOCIAL_NETWORK_AUTH_ERROR)
        detail_user_data = json.loads(response.content)
        user_data.update({
            'email': detail_user_data.get('email', None),
            'name': detail_user_data.get('name', None),
            'link': detail_user_data.get('link', None),
        })
        response = req_session.get('https://graph.facebook.com/v2.4/'
                                   '{user_id}/picture?'
                                   'access_token={access_token}'.format(
                                       user_id=user_data['user_id'],
                                       access_token=kwargs.get('access_token', '')
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
