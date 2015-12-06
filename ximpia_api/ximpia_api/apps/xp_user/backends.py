import requests
from requests.adapters import HTTPAdapter
import logging
import json
import string
from datetime import datetime

from rest_framework import authentication

from django.utils.translation import ugettext as _
from django.contrib.auth.models import User
from django.utils.crypto import get_random_string

from django.conf import settings

from base import SocialNetworkResolution, get_es_response, exceptions
from document import to_logical_doc, to_physical_doc


__author__ = 'jorgealegre'


MAX_RETRIES = 3
FLUSH_LIMIT = 1000

req_session = requests.Session()
req_session.mount('{}'.format(settings.ELASTIC_SEARCH_HOST),
                  HTTPAdapter(max_retries=MAX_RETRIES))

VALID_KEY_CHARS = string.ascii_lowercase + string.digits

logger = logging.getLogger(__name__)


class XimpiaAuthBackend(authentication.BaseAuthentication):

    @classmethod
    def authenticate(cls,
                     access_token=None,
                     provider=None,
                     social_app_id=settings.XIMPIA_FACEBOOK_APP_ID,
                     social_app_secret=settings.XIMPIA_FACEBOOK_APP_SECRET,
                     app_id=None,
                     index=None):
        """
        Authenticate for all providers given access token

        :param access_token:
        :param provider:
        :param social_app_id:
        :param social_app_secret:
        :param app_id:
        :param index:
        :return:
        """

        # 1. get social data for user
        try:
            social_data = SocialNetworkResolution.get_network_user_data(provider,
                                                                        app_id=app_id,
                                                                        access_token=access_token,
                                                                        social_app_id=social_app_id,
                                                                        social_app_secret=social_app_secret)
        except exceptions.XimpiaAPIException:
            raise

        # 2. Check user_id exists for provider
        es_response = get_es_response(
            req_session.get(
                '{host}/{index}/{document_type}/_search'.format(
                    host=settings.ELASTIC_SEARCH_HOST,
                    index=index or settings.SITE_BASE_INDEX,
                    document_type='user'),
                data=json.dumps({
                    'query': {
                        'bool': {
                            'must': [
                                {
                                    "nested": {
                                        "path": "social_networks__v1",
                                        "filter": {
                                            "bool": {
                                                "must": [
                                                    {
                                                        "term": {
                                                            "social_networks__v1.user_id__v1":
                                                                social_data.get('user_id', '')
                                                        }
                                                    },
                                                    {
                                                        "term": {
                                                            "social_networks__v1.network__v1": provider
                                                        }
                                                    }
                                                ]
                                            }
                                        }
                                    }
                                }
                            ]
                        }
                    }
                })
            )
        )
        if es_response.get('hits', {'total': 0})['total'] == 0:
            return None
        db_data = es_response['hits']['hits'][0]
        user_data = to_logical_doc('user', db_data['_source'])
        user = User()
        user.id = db_data['_id']
        user.email = user_data['email']
        user.pk = user.id
        user.username = user.id
        user.first_name = user_data['first_name']
        user.last_name = user_data['last_name']
        user_document = {
            'id': db_data['_id']
        }
        user.document = user_document.update(user_data)
        # create ximpia token with timestamp: way to check user was authenticated
        es_response_raw = req_session.post(
            '{}/{}/user/{id}/_update'.format(settings.ELASTIC_SEARCH_HOST,
                                             settings.SITE_BASE_INDEX,
                                             id=user.id),
            data=json.dumps(
                {
                    u'doc': {
                        u'token__v1': {
                            u'key__v1': get_random_string(100, VALID_KEY_CHARS),
                            u'created_on__v1': datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                        },
                    }
                }
            ))
        if es_response_raw.status_code not in [200, 201]:
            raise exceptions.XimpiaAPIException(_(u'Could not create token "{}" :: {}'.format(
                user.id,
                es_response_raw.content)))
        user_document = req_session.get(
            '{host}/{index}/{document_type}/{id}'.format(
                host=settings.ELASTIC_SEARCH_HOST,
                index=index or settings.SITE_BASE_INDEX,
                document_type='user',
                id=user.id
            )).json()
        user_data = user_document['_source']
        user_data['id'] = user_document['_id']
        user.document = to_logical_doc('user', user_data)
        return user

    @classmethod
    def get_user(cls, user_id):
        """
        Get user document by id

        :param user_id:
        :return:
        """
        es_response = get_es_response(
            req_session.get(
                '{host}/{index}/{document_type}/{user_id}'.format(
                    host=settings.ELASTIC_SEARCH_HOST,
                    index=settings.SITE_BASE_INDEX,
                    document_type='user',
                    user_id=user_id))
        )
        if not es_response['found']:
            raise exceptions.DocumentNotFound(_(u'User document not found for "{}"'.format(user_id)))
        return es_response
