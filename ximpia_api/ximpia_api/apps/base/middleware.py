import json
import requests
import logging
from requests.adapters import HTTPAdapter

from django.utils.functional import SimpleLazyObject
from django.utils.module_loading import import_string
from django.contrib.auth.models import User
from django.utils.crypto import constant_time_compare
from django.http.response import HttpResponseBadRequest
from django.conf import settings

from document import to_logical_doc
from base import get_es_response, get_path_search

req_session = requests.Session()
req_session.mount('https://{}'.format(settings.ELASTIC_SEARCH_HOST),
                  HTTPAdapter(max_retries=3))

SESSION_KEY = '_auth_user_id'
BACKEND_SESSION_KEY = '_auth_user_backend'
HASH_SESSION_KEY = '_auth_user_hash'
REDIRECT_FIELD_NAME = 'next'

__author__ = 'jorgealegre'


logger = logging.getLogger(__name__)


def load_backend(path):
    return import_string(path)()


class XimpiaUrlsMiddleware(object):

    @classmethod
    def process_request(cls, request):
        """
        Process request to build urls based on stored data

        :param request:
        :return:
        """
        from django.conf.urls import url
        import urls
        from document.views import DocumentViewSet
        # get url data
        es_response = get_es_response(
            req_session.get(
                get_path_search('urlconf'),
                data=json.dumps({
                    'query': {
                        'match_all': {
                        }
                    },
                    'from': 0,
                    'size': 1000
                })
            ))
        # build django urls
        my_url_patterns = getattr(urls, 'urlpatterns')
        for data_db in es_response['hits']['hits']:
            data = to_logical_doc('urlconf', data_db)
            for mode in ['create', 'update', 'list', 'get', 'delete']:
                url_data = dict(map(lambda x: (x['name'], x['value']), data['data']))
                url_data['site'] = data.get('site', {})
                url_data['app'] = data.get('app', {})
                url_data['tag'] = data.get('tag', {})
                url_data['branch'] = data.get('branch', {})
                my_url_patterns.append(
                    url(r'{}'.format(data['url']['raw']),
                        getattr(DocumentViewSet, mode),
                        url_data,
                        name='{}__{}'.format(
                            data['document_type'],
                            mode)),
                )
        setattr(urls, 'urlpatterns', my_url_patterns)


class XimpiaRequestMiddleware(object):

    @classmethod
    def get_user(cls, request, token):
        from django.contrib.auth.models import AnonymousUser
        from document import Document
        user = None
        if not token:
            return AnonymousUser()
        try:
            user_document = Document.objects.filter('user',
                                                    **{
                                                        'user__token__v1.user__token__key__v1': token,
                                                        'get_logical': True
                                                    })[0]
            user = User()
            user.id = user_document['id']
            user.email = user_document['email']
            user.pk = user.id
            user.username = user.id
            user.first_name = user_document['first_name']
            user.last_name = user_document['last_name']
            user.document = user_document
            return user
        except IndexError:
            pass
        return user

    @classmethod
    def process_request(cls, request):
        """
        Purpose of this middleware is saving user into request

        Do lazy?? Could be lazy as well. When needed we would execute get_user operation

        1. We get token from request
        2. Get user with token
        3. set request.user

        :param request:
        :return:
        """
        """assert hasattr(request, 'session'), (
            "The Django authentication middleware requires session middleware "
            "to be installed. Edit your MIDDLEWARE_CLASSES setting to insert "
            "'django.contrib.sessions.middleware.SessionMiddleware' before "
            "'django.contrib.auth.middleware.AuthenticationMiddleware'."
        )"""
        if not settings.DEBUG and request.scheme != 'https':
            return HttpResponseBadRequest(u'Invalid request')
        http_header = request.META.get('HTTP_AUTHORIZATION', '')
        token = ''
        if http_header:
            try:
                token = http_header.split('Bearer ')[1]
            except IndexError:
                pass
        if not token and 'access_token' in request.REQUEST:
            token = request.REQUEST.get('access_token', '')
        request.user = SimpleLazyObject(lambda: cls.get_user(request, token))
