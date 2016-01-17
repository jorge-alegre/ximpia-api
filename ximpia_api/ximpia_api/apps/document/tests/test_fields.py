from django.test import RequestFactory, Client

from base.tests import XimpiaTestCase

__author__ = 'jorgealegre'


class StringFieldTest(XimpiaTestCase):

    def setUp(self):
        self.c = Client()
        self.req_factory = RequestFactory()

    def tearDown(self):
        pass

    def test_string(self):
        pass
