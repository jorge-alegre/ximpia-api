import json
import requests
from requests.adapters import HTTPAdapter
import logging

from django.test import RequestFactory
from django.conf import settings
from django.core.urlresolvers import reverse

from base.tests import XimpiaTestCase, get_fb_test_user_local
from document import Document
from base.tests import XimpiaClient as Client, refresh_index


__author__ = 'jorgealegre'

req_session = requests.Session()
req_session.mount('https://{}'.format(settings.ELASTIC_SEARCH_HOST),
                  HTTPAdapter(max_retries=3))

logger = logging.getLogger(__name__)


class Authenticate(XimpiaTestCase):

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

    def connect_signup(self):
        site = Document.objects.filter('site',
                                       **{
                                           'site__slug__v1.raw__v1': 'my-site',
                                           'get_logical': True
                                       })[0]
        # no user, would be signup
        response = self.c.post(
            reverse('connect'),
            json.dumps({
                u'access_token': get_fb_test_user_local('registration_my_site')['access_token'],
                u'provider': 'facebook',
                u'api_key': site['api_access']['key'],
                u'api_secret': site['api_access']['secret'],
                u'site': 'my-site',
            }),
            content_type="application/json"
        )
        response_data = json.loads(response.content)
        self.assertTrue(response_data['status'] == 'ok' and response_data['action'] == 'signup'
                        and response_data['token'])

    def connect_login(self):
        site = Document.objects.filter('site',
                                       **{
                                           'site__slug__v1.raw__v1': 'my-site',
                                           'get_logical': True
                                       })[0]
        # do signup first
        groups = Document.objects.filter('group',
                                         **{
                                             'group__slug__v1.raw__v1': settings.DEFAULT_GROUPS,
                                             'get_logical': True
                                         })
        access_token = get_fb_test_user_local('registration_my_site')['access_token']
        response = self.c.post(
            reverse('connect'),
            json.dumps({
                u'access_token': access_token,
                u'provider': 'facebook',
                u'groups': groups,
                u'api_key': site['api_access']['key'],
                u'api_secret': site['api_access']['secret'],
                u'site': 'my-site'
            }),
            content_type="application/json"
        )
        self.assertTrue(response.status_code == 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data['action'] == 'signup')
        refresh_index('ximpia-api__base')
        # login
        self.c.logout()
        response = self.c.post(
            reverse('connect'),
            json.dumps({
                u'access_token': access_token,
                u'provider': 'facebook',
                u'api_key': site['api_access']['key'],
                u'api_secret': site['api_access']['secret'],
                u'site': 'my-site',
            }),
            content_type="application/json"
        )
        self.assertTrue(response.status_code == 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data['action'] == 'login')


class Signup(XimpiaTestCase):

    def setUp(self):
        self.c = Client()
        self.req_factory = RequestFactory()

    def tearDown(self):
        pass

    def signup_ximpia_user(self):
        # print 'signup_ximpia_user...'
        # get access token
        # get site
        site = Document.objects.filter('site',
                                       **{
                                           'site__slug__v1.raw__v1': 'ximpia-api',
                                           'get_logical': True
                                       })[0]
        logger.debug(u'signup_ximpia_user :: site: {}'.format(site))
        # get groups
        groups = Document.objects.filter('group',
                                         **{
                                             'site__slug__v1.raw__v1': settings.DEFAULT_GROUPS,
                                             'get_logical': True
                                         })
        logger.debug(u'signup_ximpia_user :: groups: {}'.format(groups))

        """user_raw = get_resource(
                    request,
                    reverse('signup'),
                    'post',
                    data={
                        u'access_token': access_token,
                        u'social_network': provider,
                        u'groups': groups,
                        u'api_key': app['site']['api_access']['key'],
                        u'api_secret': app['site']['api_access']['secret'],
                        u'site': site_slug
                    }
                )"""

        response = self.c.post(
            reverse('signup'),
            json.dumps({
                u'access_token': get_fb_test_user_local('registration')['access_token'],
                u'social_network': 'facebook',
                u'groups': groups,
                u'api_key': site['api_access']['key'],
                u'api_secret': site['api_access']['secret'],
                u'site': site['slug']
            }),
            content_type="application/json"
        )
        self.assertTrue(response.status_code == 200)
        self.assertTrue(json.loads(response.content) and 'email' in json.loads(response.content))
