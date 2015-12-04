import json
import requests
from requests.adapters import HTTPAdapter

from django.test import RequestFactory, Client
from django.conf import settings

from base.tests import XimpiaTestCase, get_fb_test_user_local
from document import Document


__author__ = 'jorgealegre'

req_session = requests.Session()
req_session.mount('https://{}'.format(settings.ELASTIC_SEARCH_HOST),
                  HTTPAdapter(max_retries=3))


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


class Signup(XimpiaTestCase):

    def setUp(self):
        self.c = Client()
        self.req_factory = RequestFactory()

    def tearDown(self):
        pass

    def signup_ximpia_user(self):
        print 'signup_ximpia_user...'
        # get access token
        # get site
        site = Document.objects.filter('site',
                                       slug__raw='ximpia-api', get_logical=True)[0]
        # print u'site: {}'.format(site)
        # get groups
        groups = Document.objects.filter('group',
                                         slug__raw__in=settings.DEFAULT_GROUPS,
                                         get_logical=True)
        print u'groups: {}'.format(groups)
        response = self.c.post(
            '/user-signup',
            {
                u'access_token': get_fb_test_user_local('registration')['access_token'],
                u'social_network': 'facebook',
                u'groups': groups,
                u'api_key': site['api_access']['api_key'],
                u'api_secret': site['api_access']['api_secret'],
            }
        )
        print response.status_code
        print response.content
        print response.json()
