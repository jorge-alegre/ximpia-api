from django.test import RequestFactory, Client

from base.tests import XimpiaTestCase, get_fb_test_user_local
from document import Document

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
        self.assertTrue(self.c.session.items() is not None and len(self.c.session.items()) != 0
                        and '_auth_user_id' in self.c.session)
        user_id = self.c.session['_auth_user_id']
        user = Document.objects.get('user', id=user_id, get_logical=True)
        self.assertTrue(user['token'] and 'key' in user['token'] and user['token']['key'])
