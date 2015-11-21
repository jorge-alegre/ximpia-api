import requests
from requests.adapters import HTTPAdapter
import logging
import json

from django.contrib.sessions.backends.base import CreateError, SessionBase
from django.utils import timezone
from django.utils.translation import ugettext as _

from django.conf import settings

from base import exceptions
from document import to_logical_doc, to_physical_doc


__author__ = 'jorgealegre'


MAX_RETRIES = 3
FLUSH_LIMIT = 1000

req_session = requests.Session()
req_session.mount('{}'.format(settings.ELASTIC_SEARCH_HOST),
                  HTTPAdapter(max_retries=MAX_RETRIES))

logger = logging.getLogger(__name__)


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
        es_response_raw = req_session.get(
            '{host}/{index}/{document_type}/_search?query_cache={query_cache}'.format(
                host=settings.ELASTIC_SEARCH_HOST,
                document_type='session',
                index=settings.SITE_BASE_INDEX,
                query_cache=json.dumps(True)),
            data=json.dumps({
                'query': {
                    'bool': {
                        'must': [
                            {
                                'term': {
                                    'session_key__v1': self.session_key
                                }
                            },
                            {
                                'range': {
                                    'expire_date__v1': {
                                        "gt": timezone.now().strftime("%Y-%m-%d %H:%M:%S")
                                    }
                                }
                            }
                        ]
                    }
                }
            })
            )
        if es_response_raw.status_code != 200 or 'status' in es_response_raw and es_response_raw['status'] != 200:
            self._session_key = None
            return {}
        es_response = es_response_raw.json()
        try:
            session_data = self.decode(to_logical_doc('session',
                                                      es_response['hits']['hits'][0]['_source'])['session_data'])
            session_data['_id'] = es_response['hits']['hits'][0]['_id']
        except IndexError:
            session_data = {}
        return session_data

    def exists(self, session_key):
        """
        Exists session_key

        :param session_key:
        :return:
        """
        es_response_raw = req_session.get(
            '{host}/{index}/{document_type}/_count?query_cache={query_cache}'.format(
                host=settings.ELASTIC_SEARCH_HOST,
                index=settings.SITE_BASE_INDEX,
                document_type='session',
                query_cache=json.dumps(True)),
            data=json.dumps({
                'query': {
                    'term': {
                        'session_key__v1': session_key
                    }
                }
            })
            )
        es_response = es_response_raw.json()
        if es_response_raw.status_code != 200 or 'status' in es_response and es_response['status'] != 200:
            return False
        return es_response['count'] > 0

    def create(self):
        """
        Create session

        :return:
        """
        while True:
            self._session_key = self._get_new_session_key()
            try:
                # Save immediately to ensure we have a unique entry in the
                # database.
                self.save(must_create=True)
            except CreateError:
                # Key wasn't unique. Try again.
                continue
            self.modified = True
            return

    def save(self, must_create=False):
        """
        Saves the current session data to the database. If 'must_create' is
        True, a database error will be raised if the saving operation doesn't
        create a *new* entry (as opposed to possibly updating an existing
        entry).
        """
        if self.session_key is None:
            return self.create()
        raw_session_data = self._get_session(no_load=must_create)
        session_data = {
            'session_key': self._get_or_create_session_key(),
            'session_data': self.encode(raw_session_data),
            'expire_date': self.get_expiry_date().strftime("%Y-%m-%d %H:%M:%S")
        }
        if must_create:
            es_response_raw = requests.post('{}/{}/session'.format(settings.ELASTIC_SEARCH_HOST,
                                                                   settings.SITE_BASE_INDEX),
                                            data=json.dumps(to_physical_doc('session', session_data)))
        else:
            es_response_raw = requests.put('{}/{}/session/{id}'.format(settings.ELASTIC_SEARCH_HOST,
                                                                       settings.SITE_BASE_INDEX,
                                                                       id=raw_session_data['_id']),
                                           data=json.dumps(to_physical_doc('session', session_data)))
        if es_response_raw.status_code != 200:
            exceptions.XimpiaAPIException(_(u'SessionStore :: save() :: Could not write session'))
        es_response = es_response_raw.json()
        logger.info(u'SessionStore :: save() :: es_response: {}'.format(es_response))

    def delete(self, session_key=None):
        """
        Delete session

        :param session_key:
        :return:
        """
        if session_key is None:
            if self.session_key is None:
                return
            session_key = self.session_key
        es_response_raw = req_session.get(
            '{host}/{index}/{document_type}/_search?query_cache={query_cache}'.format(
                host=settings.ELASTIC_SEARCH_HOST,
                document_type='session',
                index=settings.SITE_BASE_INDEX,
                query_cache=json.dumps(True)),
            data=json.dumps({
                'query': {
                    'term': {
                        'session_key__v1': session_key
                    }
                }
            })
            )
        if es_response_raw.status_code != 200:
            return
        es_response = es_response_raw.json()
        try:
            id_ = es_response['hits']['hits'][0]['_id']
            es_response_raw = req_session.delete('{host}/{index}/{document_type}/{id_}'.format(
                host=settings.ELASTIC_SEARCH_HOST,
                document_type='session',
                index=settings.SITE_BASE_INDEX,
                id_=id_))
            if es_response_raw.status_code != 200:
                exceptions.XimpiaAPIException(_(u'Could not get session'))
            es_response = es_response_raw.json()
            logger.info(u'SessionStore :: delete() :: es_response: {}'.format(es_response))
        except IndexError:
            pass


    @classmethod
    def clear_expired(cls):
        """
        Clear expired sessions

        :return:
        """
        es_response_raw = req_session.get(
            '{host}/{index}/{document_type}/_search?scroll=1m&search_type=scan'.format(
                host=settings.ELASTIC_SEARCH_HOST,
                document_type='session',
                index=settings.SITE_BASE_INDEX),
            data=json.dumps({
                'query': {
                    'range': {
                        'expire_date__v1': {
                            "lt": timezone.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                    }
                }
            })
            )
        es_response = es_response_raw.json()
        es_response_raw = req_session.get(
            '{host}/_search?scroll=1m&search_type=scan'.format(
                host=settings.ELASTIC_SEARCH_HOST),
            data={
                'scroll_id': es_response['_scroll_id']
            })
        es_response = es_response_raw.json()
        delete_list = []
        while es_response['hits']['hits']:
            # build bulk data to delete
            for result in es_response['hits']['hits']:
                if len(delete_list) > FLUSH_LIMIT:
                    req_session.post('{host}/_bulk'.format(host=settings.ELASTIC_SEARCH_HOST),
                                     u'\n'.join(delete_list) + u'\n')
                    delete_list = []
                else:
                    delete_list.append({
                        "delete": {
                            "_index": result['_index'],
                            "_type": result['_type'],
                            "_id": result['_id']
                        }
                    })
            es_response_raw = req_session.get(
                '{host}/_search?scroll=1m&search_type=scan'.format(
                    host=settings.ELASTIC_SEARCH_HOST),
                data={
                    'scroll_id': es_response['_scroll_id']
                })
            es_response = es_response_raw.json()
        req_session.post('{host}/_bulk'.format(host=settings.ELASTIC_SEARCH_HOST),
                         u'\n'.join(delete_list) + u'\n')
