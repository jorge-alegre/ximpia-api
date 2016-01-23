import json
import logging

from django.test import RequestFactory
from django.conf import settings

from base.tests import XimpiaClient as Client, XimpiaTestCase

__author__ = 'jorgealegre'

logger = logging.getLogger(__name__)


class FieldsFromMappingTest(XimpiaTestCase):

    def setUp(self):
        self.c = Client()
        self.req_factory = RequestFactory()

    def tearDown(self):
        pass

    def test_main(self):
        from document import get_fields_from_mapping
        mappings_path = settings.BASE_DIR + 'apps/base/mappings'
        with open('{}/account.json'.format(mappings_path)) as f:
            account_dict = json.loads(f.read())
        fields = get_fields_from_mapping(account_dict)
        self.assertTrue(len(filter(lambda x: x['field'] == u'account__name__v1', fields)) == 1)
        with open('{}/app.json'.format(mappings_path)) as f:
            app_dict = json.loads(f.read())
        fields = get_fields_from_mapping(app_dict)
        logger.debug(u'FieldsFromMappingTest.test_main :: fields: {}'.format(fields))
        self.assertTrue(len(filter(lambda x: x['field'] == u'app__name__v1', fields)) == 1)
