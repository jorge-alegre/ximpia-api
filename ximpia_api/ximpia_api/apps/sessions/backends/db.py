import requests
from requests.adapters import HTTPAdapter
import logging
import json

from django.contrib.sessions.backends.base import CreateError, SessionBase
from django.core.exceptions import SuspiciousOperation
from django.db import IntegrityError, router, transaction
from django.utils import timezone
from django.utils.encoding import force_text

from django.conf import settings


__author__ = 'jorgealegre'


MAX_RETRIES = 3


class SessionStore(SessionBase):
    """
    Implements database session store.
    """
    def __init__(self, session_key=None):
        super(SessionStore, self).__init__(session_key)

    def load(self):
        """
        Load session data

        :return:
        """
        req_session = requests.Session()
        req_session.mount('https://{}'.format(settings.SEARCH_HOST),
                          HTTPAdapter(max_retries=MAX_RETRIES))

        es_response = req_session.get(
            'http://{host}/{index}/{document_type}/_search?query_cache={query_cache}'.format(
                host=settings.ELASTIC_SEARCH_HOST,
                document_type='_session',
                index=settings.SITE_BASE_INDEX,
                query_cache=json.dumps(True)),
            data=json.dumps({
                'query': {
                    'bool': {
                        'must': [
                            {
                                'term': {
                                    'session_key': self.session_key
                                }
                            },
                            {
                                'range': {
                                    'expire_date': {
                                        "gt": timezone.now().strftime("%Y-%m-%d %H:%M:%S")
                                    }
                                }
                            }
                        ]
                    }
                }
            })
            )
        if es_response.status_code != 200 or 'status' in es_response and es_response['status'] != 200:
            self._session_key = None
            return {}
        es_response = json.loads(es_response.content)
        return self.decode(es_response['hits']['hits'][0].session_data)

    def exists(self, session_key):
        return True

    def create(self):
        pass

    def save(self, must_create=False):
        """
        Saves the current session data to the database. If 'must_create' is
        True, a database error will be raised if the saving operation doesn't
        create a *new* entry (as opposed to possibly updating an existing
        entry).
        """
        pass

    def delete(self, session_key=None):
        pass

    @classmethod
    def clear_expired(cls):
        pass
