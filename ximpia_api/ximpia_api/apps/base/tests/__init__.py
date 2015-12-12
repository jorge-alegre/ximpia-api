import requests
import os
import json
import time

from requests.adapters import HTTPAdapter

from django.conf import settings
from django.test.runner import DiscoverRunner
from django.core.management import call_command
from django.utils.translation import ugettext as _
from django.core.urlresolvers import reverse
from django.test import RequestFactory, Client, SimpleTestCase

from base import exceptions, refresh_index

__author__ = 'jorgealegre'

req_session = requests.Session()
req_session.mount('https://graph.facebook.com', HTTPAdapter(max_retries=3))


def create_fb_test_user(app_access_token=None, facebook_app_id=None):
    """
    Create Facebook test user

    :return:
    """
    # /v2.5/{app-id}/accounts/test-users
    request_url = 'https://graph.facebook.com/v2.5/{app_id}/accounts/test-users?access_token={app_token}&' \
                  'permissions=email'.format(
                      app_token=app_access_token or settings.XIMPIA_FACEBOOK_APP_TOKEN,
                      app_id=facebook_app_id or settings.XIMPIA_FACEBOOK_APP_ID)
    response = req_session.post(request_url,
                                data=json.dumps({
                                    'installed': True
                                }))
    if response.status_code != 200:
        raise exceptions.XimpiaAPIException(u'Error in validating Facebook response :: {}'.format(
            response.content
        ),
            code=exceptions.SOCIAL_NETWORK_AUTH_ERROR)
    fb_data = response.json()
    return fb_data


def get_fb_test_users(limit=2000):
    """
    Get all fb users

    :param limit:
    :return:
    """
    app_access_token = settings.XIMPIA_FACEBOOK_APP_TOKEN
    request_url = 'https://graph.facebook.com/v2.5/{app_id}/accounts/test-users?access_token={app_token}&' \
                  'fields=access_token&limit={limit}'.format(
                      app_token=app_access_token,
                      app_id=settings.XIMPIA_FACEBOOK_APP_ID,
                      limit=limit)
    response = req_session.get(request_url)
    if response.status_code != 200:
        raise exceptions.XimpiaAPIException(u'Error in validating Facebook response :: {}'.format(
            response.content
        ),
            code=exceptions.SOCIAL_NETWORK_AUTH_ERROR)
    fb_data = response.json()
    app_access_token = settings.MY_SITE_APP_ACCESS_TOKEN
    request_url = 'https://graph.facebook.com/v2.5/{app_id}/accounts/test-users?access_token={app_token}&' \
                  'fields=access_token&limit={limit}'.format(
                      app_token=app_access_token,
                      app_id=settings.MY_SITE_FACEBOOK_APP_ID,
                      limit=limit)
    response = req_session.get(request_url)
    if response.status_code != 200:
        raise exceptions.XimpiaAPIException(u'Error in validating Facebook response :: {}'.format(
            response.content
        ),
            code=exceptions.SOCIAL_NETWORK_AUTH_ERROR)
    fb_data_my_site = response.json()
    fb_data['data'].extend(fb_data_my_site['data'])
    return fb_data['data']


def create_fb_test_user_login(app_access_token=None, facebook_app_id=None):
    """
    Create and login FB user data

    :return:
    """
    user_data = create_fb_test_user(app_access_token=app_access_token,
                                    facebook_app_id=facebook_app_id)
    # login user
    session_fb = requests.Session()
    session_fb.get("https://www.facebook.com/", allow_redirects=True)
    response = session_fb.get(
        'https://www.facebook.com/login.php'
    )
    response = session_fb.post("https://www.facebook.com/login.php",
                               data={
                                   'email': user_data["email"],
                                   'pass': user_data["password"]
                               })
    if response.status_code != 200:
        raise exceptions.XimpiaAPIException(u'Error in validating Facebook response',
                                            code=exceptions.SOCIAL_NETWORK_AUTH_ERROR)
    return user_data


def fb_test_user_login(user_data):
    """
    Login fb test user

    :return:
    """
    # login user
    session_fb = requests.Session()
    session_fb.get("https://www.facebook.com/", allow_redirects=True)
    response = session_fb.get(
        'https://www.facebook.com/login.php'
    )
    response = session_fb.post("https://www.facebook.com/login.php",
                               data={
                                   'email': user_data["email"],
                                   'pass': user_data["password"]
                               })
    if response.status_code != 200:
        raise exceptions.XimpiaAPIException(u'Error in validating Facebook response',
                                            code=exceptions.SOCIAL_NETWORK_AUTH_ERROR)
    return user_data


def delete_fb_test_user(user_id):
    """
    Delete facebook test user

    :param user_id:
    :return:
    """
    app_access_token = settings.XIMPIA_FACEBOOK_APP_TOKEN
    # /v2.5/{app-id}/accounts/test-users
    request_url = 'https://graph.facebook.com/v2.5/{app_id}/accounts/test-users?' \
                  'access_token={app_token}&uid={user_id}'.format(
                      app_token=app_access_token,
                      app_id=settings.XIMPIA_FACEBOOK_APP_ID,
                      user_id=user_id)
    response = req_session.delete(request_url)
    if response.status_code != 200:
        raise exceptions.XimpiaAPIException(u'Error in validating Facebook response :: {}'.format(
            response.content
        ),
            code=exceptions.SOCIAL_NETWORK_AUTH_ERROR)
    data = response.json()
    if 'success' not in data and not data['success']:
        raise exceptions.XimpiaAPIException(u'Error in validating Facebook response :: {}'.format(
            response.content
        ),
            code=exceptions.SOCIAL_NETWORK_AUTH_ERROR)


def get_fb_test_user_local(feature):
    """
    Get local fb test user random

    :param feature:
    :return:
    """
    from random import choice
    path = '{}/apps/base/tests/data/fb_test_users.json'.format(settings.BASE_DIR)
    with open(path) as f:
        users = json.loads(f.read())
        if feature in users:
            return choice(users[feature])
        else:
            raise exceptions.XimpiaAPIException(u'feature not found in local test users')


class XimpiaDiscoverRunner(DiscoverRunner):

    def __init__(self, *args, **kwargs):
        super(XimpiaDiscoverRunner, self).__init__(*args, **kwargs)
        self.admin_user = None

    def setup_databases(self, **kwargs):
        """
        Create indices with mappings and Ximpia API site with user, groups, settings

        :param kwargs:
        :return:
        """
        from base import exceptions, SocialNetworkResolution
        from document import Document, to_physical_doc
        old_names = []
        mirrors = []
        # get test user
        user_data = get_fb_test_user_local('admin')
        if self.verbosity >= 1:
            print u'Creating test indexes...'
        # Call create_ximpia
        call_command('create_ximpia',
                     access_token=user_data['access_token'],
                     social_network='facebook',
                     invite_only=False,
                     verbosity=self.verbosity)
        # Create site My Site
        user_data = get_fb_test_user_local('registration')
        client = Client()
        response = client.post(
            reverse('create_site'),
            json.dumps({
                u'access_token': user_data['access_token'],
                u'social_network': 'facebook',
                u'languages': ['en'],
                u'location': 'us',
                u'domains': ['my-domain.com'],
                u'organization_name': u'my-company',
                u'account': 'my-company',
                u'site': 'my-site',
            }),
            content_type="application/json"
        )
        if response.status_code != 200:
            raise exceptions.XimpiaAPIException(u'Error creating My Site')
        # Update facebook app ids to My Site
        response_data = json.loads(response.content)
        print u'response_data app: {}'.format(response_data['app'])
        app_id = response_data['app']['id']
        refresh_index('ximpia-api__base')
        refresh_index('my-site__base')
        # get app
        app = Document.objects.get('app', id=app_id, index='my-site__base', get_logical=True)
        print app
        app['social']['facebook']['app_id'] = settings.MY_SITE_FACEBOOK_APP_ID
        app['social']['facebook']['app_secret'] = settings.MY_SITE_FACEBOOK_APP_SECRET
        # Get app access token
        # social_app_id, social_app_secret, app_id='ximpia_api__base')
        app['social']['facebook']['access_token'] = SocialNetworkResolution.get_app_access_token(
            app['social']['facebook']['app_id'],
            app['social']['facebook']['app_secret'],
            app_id=app['id'],
            disable_update=True,
        )
        # update app partially for app['social']
        response = Document.objects.update_partial('app',
                                                   app['id'],
                                                   {
                                                       'social__v1': to_physical_doc('app', app['social'])
                                                   },
                                                   index='my-site__base'
                                                   )
        if 'status' in response and response['status'] not in [200, 201]:
            raise exceptions.XimpiaAPIException(u'Error updating app :: {}'.format(
                response
            ))
        refresh_index('my-site__base')
        return old_names, mirrors

    def teardown_databases(self, old_config, **kwargs):
        """
        Drop indices

        :param old_config:
        :param kwargs:
        :return:
        """
        if self.verbosity >= 1:
            print u'Destroying test indexes...'
        # delete ximpia_api index
        # Get all indices
        # curl -XGET 'http://192.168.99.100:9201/_recovery?pretty'
        es_response_raw = requests.get('{}/_recovery'.format(settings.ELASTIC_SEARCH_HOST))
        if es_response_raw.status_code not in [200, 201]:
            raise exceptions.XimpiaAPIException(_(u'Could not get indices :: {}'.format(
                es_response_raw.content
            )))
        es_response = es_response_raw.json()
        indices = es_response.keys()
        for index in indices:
            # curl -XDELETE 'http://localhost:9200/twitter/'
            es_response_raw = requests.delete('{}/{}/'.format(
                settings.ELASTIC_SEARCH_HOST,
                index
            ))
            if es_response_raw.status_code not in [200, 201]:
                raise exceptions.XimpiaAPIException(_(u'Could not delete index "{}" :: {}'.format(
                    index,
                    es_response_raw.content,
                )))

    @classmethod
    def _create_test_users(cls):
        """
        Create all test users

        :return:
        """
        call_command('create_fb_test_users', feature='admin', size=1)
        call_command('create_fb_test_users', feature='registration', size=5)
        call_command('create_fb_test_users', feature='registration_my_site', size=5,
                     app_access_token='991722957558076|si3sICvrZPEYsSnQawdYwsD1JRE',
                     facebook_app_id='991722957558076')

    def setup_test_environment(self, **kwargs):
        """
        Setup test environment

        :param kwargs:
        :return:
        """
        os.environ['DJANGO_SETTINGS_MODULE'] = 'settings.tests'
        # Create fb_test_users.json
        path = '{}apps/base/tests/data/fb_test_users.json'.format(settings.BASE_DIR)
        path_expires = '{}apps/base/tests/data/fb_test_users-expires.json'.format(settings.BASE_DIR)
        if not os.path.isfile(path):
            if self.verbosity >= 1:
                print 'Creating test users file...'
            data = {}
            f = open(path, 'w')
            f.write(json.dumps(data, indent=2))
            f.close()
            f = open(path_expires, 'w')
            data['expires'] = int(time.time()) + 5000
            f.write(json.dumps(data, indent=2))
            f.close()
            # call command create users for features
            self._create_test_users()
        else:
            # 981166675280371/accounts/test-users?fields=access_token&limit=500
            # login users again
            if not os.path.isfile(path_expires):
                f = open(path_expires, 'w')
                f.write(
                    json.dumps(
                        {
                            'expires': int(time.time()-3600)
                        }, indent=2
                    )
                )
                f.close()
            f = open(path_expires)
            data = json.loads(f.read())
            f.close()
            # check expires
            if int(time.time()) > int(data['expires']):
                if self.verbosity >= 1:
                    print 'Will login test users...'
                f = open(path, 'r')
                data = json.loads(f.read())
                f.close()
                # login users again
                user_ids = []
                for feature in data.keys():
                    for user_data in data[feature]:
                        if self.verbosity >= 1:
                            print 'logging [{}] {}...'.format(
                                feature,
                                user_data['email'],
                            )
                        fb_test_user_login(user_data)
                        user_ids.append(user_data['id'])
                        # get test users data
                # get all test users
                if self.verbosity >= 1:
                    print 'getting new access tokens...'
                all_test_users = get_fb_test_users()
                print all_test_users
                access_tokens = dict(map(lambda y: (y['id'], y['access_token']),
                                     filter(lambda x: x['id'] in user_ids, all_test_users)))
                f = open(path, 'w')
                data_new = {}
                for feature in data.keys():
                    for user_data in data[feature]:
                        if user_data['id'] in access_tokens:
                            user_data['access_token'] = access_tokens[user_data['id']]
                            data_new.setdefault(feature, [])
                            data_new[feature].append(user_data)
                f.write(json.dumps(data_new, indent=2))
                f.close()
                # create expires 5000 seconds
                data = {}
                f = open(path_expires, 'w')
                data['expires'] = int(time.time()) + 5000
                f.write(json.dumps(data, indent=2))
                f.close()
        # settings.DEBUG = True
        super(XimpiaDiscoverRunner, self).setup_test_environment(**kwargs)
        settings.DEBUG = True

    def teardown_test_environment(self, **kwargs):
        """
        TearDown environment

        :param kwargs:
        :return:
        """
        super(XimpiaDiscoverRunner, self).teardown_test_environment(**kwargs)


class XimpiaTestCase(SimpleTestCase):

    def setUp(self):
        self.c = Client()
        self.req_factory = RequestFactory()


class CreateSite(XimpiaTestCase):

    def setUp(self):
        self.c = Client()
        self.req_factory = RequestFactory()

    def tearDown(self):
        pass

    def create_site(self):
        """
        We make request like:
        https://mysite.ximpia.io/create-site

        In tests, since we can't have the different host, we send in data.
        Views get either from hostname or data

        Being site slug embedded in the hostname

        :return:
        """
        user_data = get_fb_test_user_local('registration')
        response = self.c.post(
            reverse('create_site'),
            json.dumps({
                u'access_token': user_data['access_token'],
                u'social_network': 'facebook',
                u'languages': ['en'],
                u'location': 'us',
                u'domains': ['my-domain.com'],
                u'organization_name': u'my-company-test',
                u'account': 'my-company-test',
                u'site': 'my-site-test',
            }),
            content_type="application/json"
        )
        self.assertTrue(response.status_code == 200)
        self.assertTrue(json.loads(response.content) and 'account' in json.loads(response.content))
