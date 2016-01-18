import json
import logging

from django.test import RequestFactory
from django.core.urlresolvers import reverse

from base.tests import XimpiaClient as Client, XimpiaTestCase

__author__ = 'jorgealegre'

logger = logging.getLogger(__name__)


class StringFieldTest(XimpiaTestCase):

    def setUp(self):
        self.c = Client()
        self.req_factory = RequestFactory()

    def tearDown(self):
        pass

    def test_string(self):
        with open('data/doc_string.json') as f:
            doc_string_str = f.read()
        doc_string = json.loads(doc_string_str)
        response = self.c.post(
            reverse('document_definition'),
            json.dumps(doc_string),
            content_type="application/json"
        )
        response_data = json.loads(response.content)
        logger.debug(u'test_string:: create document: {}'.format(response_data))
