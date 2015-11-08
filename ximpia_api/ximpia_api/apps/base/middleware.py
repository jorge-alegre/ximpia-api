import json
import requests
from requests.adapters import HTTPAdapter

from django.conf import settings

from document import to_logical_doc
from base import get_es_response, get_path_search

req_session = requests.Session()
req_session.mount('https://{}'.format(settings.ELASTIC_SEARCH_HOST),
                  HTTPAdapter(max_retries=3))

__author__ = 'jorgealegre'


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
