import json
import logging
import requests

from django.test import RequestFactory
from django.core.urlresolvers import reverse
from django.conf import settings

from base.tests import XimpiaClient as Client, XimpiaTestCase, get_fb_test_user_local
from document import Document
from base import refresh_index

__author__ = 'jorgealegre'

logger = logging.getLogger(__name__)


class StringFieldTest(XimpiaTestCase):

    def setUp(self):
        self.c = Client()
        self.req_factory = RequestFactory()

    def tearDown(self):
        pass

    def _validate_field(self, index, doc_type, field_value, doc_string):
        from patterns import NotExists
        from document.fields import StringField
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

    def test_string(self):
        user = self.connect_user(user='my_site_admin', is_admin=True)
        with open('ximpia_api/apps/document/tests/data/doc_string.json') as f:
            doc_string_str = f.read()
        doc_string = json.loads(doc_string_str)
        request_attributes = '?access_token={access_token}&site={site}'.format(
            access_token=user['token'],
            site='my-site'
        )
        doc_type = 'test-string-field'
        index = 'my-site__base'
        response = self.c.post(
            reverse('document-definition',
                    kwargs={'doc_type': 'test-string-field'}) + request_attributes,
            json.dumps(doc_string),
            content_type="application/json",
        )
        response_data = json.loads(response.content)
        """import pprint
        logger.debug(u'test_string:: create document: {}'.format(
            pprint.PrettyPrinter(indent=4).pformat(response_data)
        ))"""
        refresh_index('ximpia-api__base')
        refresh_index('my-site__base')
        # Check document definition created
        es_response_raw = requests.get(
            '{host}/{index}/{doc_type}/{id}'.format(
                host=settings.ELASTIC_SEARCH_HOST,
                index=index,
                doc_type=doc_type,
                id=response_data['_id']
            )
        )
        es_response = es_response_raw.json()
        self.assertTrue(es_response_raw.status_code == 200)
        self.assertTrue(es_response['found'])
        # Check mappings created
        es_response_raw = requests.get(
            '{host}/{index}/_mapping/{doc_type}'.format(
                host=settings.ELASTIC_SEARCH_HOST,
                index=index,
                doc_type=doc_type
            )
        )
        es_response = es_response_raw.json()
        self.assertTrue(es_response_raw.status_code == 200)
        self.assertTrue('test-string-field' in es_response[es_response.keys()[0]]['mappings'])
        # Check fields created
        response = Document.objects.filter(
            'field-version',
            **{
                'field-version__doc_type__v1.raw__v1': doc_type,
                'index': index
            }
        )
        self.assertTrue(response is not None)
        self.assertTrue(len(response) > 0)
        # ========
        # VALIDATE
        # ========
        self.assertTrue(self._validate_field(index, doc_type, 'amazing', doc_string))
        self.assertTrue(not self._validate_field(index, doc_type, 'coc', doc_string))
        self.assertTrue(not self._validate_field(index, doc_type, '1234567890111', doc_string))
