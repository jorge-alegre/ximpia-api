import logging
import requests
import json

from django.core.management.base import BaseCommand
from django.utils.translation import ugettext as _
from django.conf import settings

from base.exceptions import XimpiaAPIException

__author__ = 'jorgealegre'

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Create document types for Ximpia API'
    can_import_settings = True

    def handle(self, *args, **options):
        index_name = 'ximpia_api__base'

        mappings_path = settings.BASE_DIR + 'apps/base/mappings'
        with open(settings.BASE_DIR + 'settings/settings.json') as f:
            settings_dict = json.loads(f.read())

        with open('{}/site.json'.format(mappings_path)) as f:
            site_dict = json.loads(f.read())

        with open('{}/app.json'.format(mappings_path)) as f:
            app_dict = json.loads(f.read())

        with open('{}/settings.json'.format(mappings_path)) as f:
            settings__dict = json.loads(f.read())

        es_response_raw = requests.post('{}/{}'.format(settings.ELASTIC_SEARCH_HOST, index_name),
                                        data={
                                            'settings': settings_dict,
                                            'mappings': {
                                                'site': site_dict,
                                                'app': app_dict,
                                                'settings': settings__dict,
                                                }
                                            }
                                        )

        if es_response_raw.status_code != 200:
            raise XimpiaAPIException(_(u'Error creating index "{}"'.format(index_name)))
        es_response = es_response_raw.json()
        if not es_response['acknowledged']:
            raise XimpiaAPIException(_(u'Error creating index "{}"'.format(index_name)))
        logger.info(u'SetupSite :: created index {} response: {}'.format(
            index_name,
            es_response
        ))

        if 'verbosity' in options and options['verbosity'] != '0':
            self.stdout.write(u'created index {} response: {}'.format(
                index_name,
                es_response
            ))
