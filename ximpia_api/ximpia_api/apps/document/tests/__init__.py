import json
import logging
import requests

from django.test import RequestFactory
from django.conf import settings

from base.tests import XimpiaClient as Client, XimpiaTestCase
from base import exceptions

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


def pattern_validate_field(index, field_name, field_value, doc, field_class, pattern=None, tag='v1'):
    """

    :param index:
    :param field_name:
    :param field_value:
    :param doc:
    :param pattern:
    :return:
    """
    if not pattern:
        raise exceptions.XimpiaAPIException(u'I need a pattern to check validations')
    bulk_queries = [pattern.build_query(index=index)]
    # Get results
    es_response_raw = requests.get(
        '{host}/_msearch'.format(
            host=settings.ELASTIC_SEARCH_HOST
        ),
        data=''.join(bulk_queries)
    )

    es_response = es_response_raw.json()
    # Validate pattern
    validate = pattern.validate(es_response['responses'][0])
    logger.debug(u'pattern_validate_field :: validate pattern: {}'.format(validate))
    # Validate Field
    patterns_data = {
        '{}.is-unique'.format(field_name): validate
    }
    field_config = doc[field_name]
    field_config['name'] = field_name
    doc_config = doc['_meta']
    field_validate = field_class.validate(
        field_value,
        field_config,
        doc_config,
        patterns_data=patterns_data,
    )
    return field_validate.check
