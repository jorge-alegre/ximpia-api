import requests
from requests.adapters import HTTPAdapter
import logging
import json

from django.utils.translation import ugettext as _
from django.contrib.auth.models import User

from django.conf import settings

from base import SocialNetworkResolution, get_es_response, exceptions
from document import to_logical_doc, to_physical_doc


__author__ = 'jorgealegre'


MAX_RETRIES = 3
FLUSH_LIMIT = 1000

req_session = requests.Session()
req_session.mount('https://{}'.format(settings.SEARCH_HOST),
                  HTTPAdapter(max_retries=MAX_RETRIES))

logger = logging.getLogger(__name__)


class XimpiaAuthBackend(object):

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
                'http://{host}/{index}/{document_type}/_search?query_cache={query_cache}'.format(
                    host=settings.ELASTIC_SEARCH_HOST,
                    document_type='_user',
                    index=settings.SITE_BASE_INDEX,
                    query_cache=json.dumps(True)),
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
            raise exceptions.XimpiaAPIException(u'Social network "user_id" not found',
                                                code=exceptions.USER_ID_NOT_FOUND)
        db_data = es_response['hits']['hits'][0]
        user_data = to_logical_doc('_user', db_data['_source'])
        user = User()
        user.id = user_data.get('_id', '')
        user.email = user_data.get('email', '')
        user.pk = user.id
        user.username = user_data.get('username', '')
        user.first_name = user_data.get('first_name', '')
        user.last_name = user_data.get('last_name', '')
        user.last_login = user_data.get('last_login', '')
        user.document = user_data
        return user

    @classmethod
    def get_user(cls, user_id):
        """
        Get user document by id

        :param user_id:
        :return:
        """
        es_response_raw = req_session.get(
            'http://{host}/{index}/{document_type}/{user_id}'.format(
                host=settings.ELASTIC_SEARCH_HOST,
                document_type='_user',
                index=settings.SITE_BASE_INDEX,
                user_id=user_id))
        if es_response_raw.status_code != 200 or 'status' in es_response_raw and es_response_raw['status'] != 200:
            pass
        es_response = es_response_raw.json()
        if not es_response['found']:
            raise exceptions.DocumentNotFound(_(u'User document not found for "{}"'.format(user_id)))
        return es_response
