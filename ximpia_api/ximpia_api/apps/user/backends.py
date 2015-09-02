import requests
from requests.adapters import HTTPAdapter
import logging
import json

from django.utils.translation import ugettext as _

from django.conf import settings

from base import exceptions
from base import SocialNetworkResolution


__author__ = 'jorgealegre'


MAX_RETRIES = 3
FLUSH_LIMIT = 1000

req_session = requests.Session()
req_session.mount('https://{}'.format(settings.SEARCH_HOST),
                  HTTPAdapter(max_retries=MAX_RETRIES))

logger = logging.getLogger(__name__)


class XimpiaAuthBackend(object):

    @classmethod
    def authenticate(cls, access_token, provider):
        """
        Authenticate for all providers given access token

        :param access_token:
        :param provider:
        :return:
        """

        # 1. get social data for user
        try:
            social_data = SocialNetworkResolution.get_network_user_data(provider,
                                                                        access_token=access_token)
        except exceptions.XimpiaAPIException:
            raise

        # 2. Check user_id exists for provider
        es_response_raw = req_session.get(
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
                                    "path": "social_networks",
                                    "filter": {
                                        "bool": {
                                            "must": [
                                                {
                                                    "term": {
                                                        "social_networks.user_id": social_data.get('user_id', '')
                                                    }
                                                },
                                                {
                                                    "term": {
                                                        "social_networks.network": provider
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
        if es_response_raw.status_code != 200 or 'status' in es_response_raw and es_response_raw['status'] != 200:
            pass
        es_response = es_response_raw.json()
        if es_response.get('hits', {'total': 0})['total'] == 0:
            raise exceptions.XimpiaAPIException(u'Social network "user_id" not found',
                                                code=exceptions.USER_ID_NOT_FOUND)
        return es_response['hits']['hits'][0]['_source']

    def get_user(self, user_id):
        pass
