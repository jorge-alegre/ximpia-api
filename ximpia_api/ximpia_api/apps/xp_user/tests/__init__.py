from django.test import RequestFactory, Client

from base.tests import XimpiaTestCase, get_fb_test_user_local

__author__ = 'jorgealegre'


class AuthenticateTestCase(XimpiaTestCase):

    def setUp(self):
        self.c = Client()
        self.req_factory = RequestFactory()

    def tearDown(self):
        pass

    def authenticate_login(self):
        auth_data = {
            'access_token': get_fb_test_user_local('admin')['access_token'],
            'provider': 'facebook',
        }
        is_login = self.c.login(**auth_data)
        self.assertTrue(is_login)
