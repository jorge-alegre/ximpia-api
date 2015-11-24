from django.test import RequestFactory, Client
from base.tests import XimpiaTestCase

__author__ = 'jorgealegre'


class AuthenticateTestCase(XimpiaTestCase):

    def setUp(self):
        self.c = Client()
        self.req_factory = RequestFactory()

    def tearDown(self):
        pass

    def authenticate(self):
        pass
