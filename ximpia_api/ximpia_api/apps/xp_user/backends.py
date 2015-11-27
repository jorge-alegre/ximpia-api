import requests
from requests.adapters import HTTPAdapter
import logging
import json

from rest_framework import authentication

from django.utils.translation import ugettext as _
from django.contrib.auth.models import User

from django.conf import settings

from base import SocialNetworkResolution, get_es_response, exceptions
from document import to_logical_doc, to_physical_doc


__author__ = 'jorgealegre'


MAX_RETRIES = 3
FLUSH_LIMIT = 1000

req_session = requests.Session()
req_session.mount('{}'.format(settings.ELASTIC_SEARCH_HOST),
                  HTTPAdapter(max_retries=MAX_RETRIES))

logger = logging.getLogger(__name__)


class XimpiaAuthBackend(authentication.BaseAuthentication):

    @classmethod
    def authenticate(cls, access_token=None, provider=None, app_id=settings.XIMPIA_FACEBOOK_APP_ID,
                     app_secret=settings.XIMPIA_FACEBOOK_APP_SECRET):
        """
        Authenticate for all providers given access token

        :param access_token:
        :param provider:
        :return:
        """

        # 1. get social data for user
        try:
            social_data = SocialNetworkResolution.get_network_user_data(provider,
                                                                        access_token=access_token,
                                                                        app_id=app_id,
                                                                        app_secret=app_secret)
        except exceptions.XimpiaAPIException:
            raise

        # 2. Check user_id exists for provider
        es_response = get_es_response(
            req_session.get(
                '{host}/{index}/{document_type}/_search'.format(
                    host=settings.ELASTIC_SEARCH_HOST,
                    index=settings.SITE_BASE_INDEX,
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
        print es_response
        if es_response.get('hits', {'total': 0})['total'] == 0:
            return None
        db_data = es_response['hits']['hits'][0]
        user_data = to_logical_doc('user', db_data['_source'])
        print 'user_data: {}'.format(user_data)
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
        print 'user: {}'.format(user)
        # create ximpia token with timestamp: way to check user was authenticated
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
