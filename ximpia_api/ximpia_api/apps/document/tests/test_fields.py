import json
import logging

from django.test import RequestFactory
from django.core.urlresolvers import reverse

from base.tests import XimpiaClient as Client, XimpiaTestCase, get_fb_test_user_local
from document import Document

__author__ = 'jorgealegre'

logger = logging.getLogger(__name__)


class StringFieldTest(XimpiaTestCase):

    def setUp(self):
        self.c = Client()
        self.req_factory = RequestFactory()

    def tearDown(self):
        pass

    def test_string(self):
        print
        print
        print
        # user_signup_data = self.connect_user(user='admin')
        user = self.connect_user()
        with open('ximpia_api/apps/document/tests/data/doc_string.json') as f:
            doc_string_str = f.read()
        doc_string = json.loads(doc_string_str)
        response = self.c.post(
            reverse('document-definition',
                    kwargs={'doc_type': 'test-string-field'}) + '?access_token={}'.format(user['token']),
            json.dumps(doc_string),
            content_type="application/json",
            headers={
                'Authorization: ': user['token']
            }
        )
        response_data = json.loads(response.content)
        logger.debug(u'test_string:: create document: {}'.format(response_data))
