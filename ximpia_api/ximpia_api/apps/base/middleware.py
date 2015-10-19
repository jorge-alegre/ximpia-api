import json
import requests
from requests.adapters import HTTPAdapter

from django.conf import settings

from document import Document, to_logical_doc
from base import exceptions, get_es_response, get_path_search

req_session = requests.Session()
req_session.mount('https://{}'.format(settings.SEARCH_HOST),
                  HTTPAdapter(max_retries=3))

__author__ = 'jorgealegre'


class XimpiaSettingsMiddleware(object):

    @classmethod
    def _get_setting_value(cls, value_node):
        """

        :param value_node:
        :return:
        """
        if value_node['int']:
            return value_node['int']
        if value_node['date']:
            return value_node['date']
        return value_node['value']

    @classmethod
    def _get_setting_table_value(cls, value_node):
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

    @classmethod
    def process_request(cls, request):
        """
        Process request to inject settings objects from database settings

        :param request:
        :return:
        """
        site_slug = request.META['REMOTE_HOST'].split(settings.XIMPIA_DOMAIN)[0]
        app_id = getattr(request, 'app_id', -1)
        if app_id == -1:
            raise exceptions.XimpiaAPIException(u'App id error')
        db_settings = Document.objects.filter('_settings',
                                              site__slug__raw=site_slug,
                                              app__id=app_id)
        for db_setting_doc in db_settings['hits']['hits']:
            setting_doc = to_logical_doc('_settings', db_setting_doc)
            if setting_doc['fields']:
                setattr(settings,
                        setting_doc['_source']['name'],
                        cls._get_setting_table_value(setting_doc['_source']['fields']))
            else:
                setattr(settings,
                        setting_doc['_source']['name'],
                        cls._get_setting_value(setting_doc['_source']['value']))


class XimpiaUrlsMiddleware(object):

    @classmethod
    def process_request(cls, request):
        """
        Process request to build urls based on stored data

        :param request:
        :return:
        """
        from django.conf.urls import url
        from ximpia_api import urls
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
