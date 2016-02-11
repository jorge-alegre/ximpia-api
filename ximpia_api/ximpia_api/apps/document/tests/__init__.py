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


def pattern_validate_field(index, doc_type, field_value, doc_string, pattern=None):
    """

    :param index:
    :param doc_type:
    :param field_value:
    :param doc_string:
    :param pattern:
    :return:
    """
    from patterns import NotExists
    from document.fields import StringField
    if not pattern:
        raise exceptions.XimpiaAPIException(u'I need a pattern to check validations')
    bulk_queries = []
    pattern = NotExists(
        {
            'path': '{doc_type}.name'.format(doc_type=doc_type),
            'value': field_value
        }
    )
    bulk_queries.append(pattern.build_query(index=index))
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
    # Validate Field
    patterns_data = {
        'name.is-unique': validate
    }
    field_config = doc_string['name']
    field_config['name'] = 'name'
    doc_config = doc_string['_meta']
    field_validate = StringField.validate(field_value, field_config, doc_config, patterns_data=patterns_data)
    return field_validate
