from django.conf import settings

from document import Document, to_logical_doc
from base import exceptions

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
