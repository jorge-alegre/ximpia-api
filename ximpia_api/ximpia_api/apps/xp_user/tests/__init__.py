from django.test import RequestFactory, Client
from django.contrib.auth import authenticate, login

from base.tests import XimpiaTestCase, get_fb_test_user_local

__author__ = 'jorgealegre'


class AuthenticateTestCase(XimpiaTestCase):

    def setUp(self):
        self.c = Client()
        self.req_factory = RequestFactory()

    def tearDown(self):
        pass

    def authenticate(self):
        auth_data = {
            'access_token': get_fb_test_user_local('admin')['access_token'],
            'provider': 'facebook',
        }
        print u'AuthenticateTestCase.authenticate :: auth_data: {}'.format(auth_data)
        user = authenticate(**auth_data)
        print u'user: {}'.format(user)
        self.assertIsNotNone(user)
