import requests
from requests.adapters import HTTPAdapter
import json
import logging
import string

from datetime import datetime

from rest_framework import viewsets, generics, response

from django.conf import settings
from django.utils.translation import ugettext as _
from django.utils.text import slugify
from django.utils.crypto import get_random_string

from . import SocialNetworkResolution
import exceptions

from document import to_physical_doc, to_logical_doc

__author__ = 'jorgealegre'

logger = logging.getLogger(__name__)

VALID_KEY_CHARS = string.ascii_lowercase + string.digits

req_session = requests.Session()
req_session.mount('https://{}'.format(settings.SEARCH_HOST),
                  HTTPAdapter(max_retries=3))


class DocumentViewSet(viewsets.ModelViewSet):

    pass


class SetupSite(generics.CreateAPIView):

    RESERVED_WORDS = {
        'ximpia_api__'
    }

    @classmethod
    def _create_site_index(cls, index_name):
        """
        Create index

        :param index_name:
        :return:
        """
        user_path = settings.BASE_DIR + 'apps/user/mappings'
        base_mappings_path = settings.BASE_DIR + 'apps/base/mappings'
        with open(settings.BASE_DIR + 'settings/settings.json') as f:
            settings_dict = json.loads(f.read())

        with open('{}/_user.json'.format(user_path)) as f:
            user_dict = json.loads(f.read())

        with open('{}/_group.json'.format(user_path)) as f:
            group_dict = json.loads(f.read())

        with open('{}/_user-group.json'.format(user_path)) as f:
            user_group_dict = json.loads(f.read())

        with open('{}/_permission.json'.format(user_path)) as f:
            permissions_dict = json.loads(f.read())

        with open('{}/_app.json'.format(base_mappings_path)) as f:
            app_dict = json.loads(f.read())

        with open('{}/_settings.json'.format(base_mappings_path)) as f:
            settings__dict = json.loads(f.read())

        with open('{}/_session.json'.format(settings.BASE_DIR + 'apps/sessions/mappings')) as f:
            session_dict = json.loads(f.read())

        es_response_raw = req_session.post('{}/{}'.format(settings.ELASTIC_SEARCH_HOST, index_name),
                                           data={
                                               'settings': settings_dict,
                                               'mappings': {
                                                   '_app': app_dict,
                                                   '_settings': settings__dict,
                                                   '_user': user_dict,
                                                   '_group': group_dict,
                                                   '_user-group': user_group_dict,
                                                   '_permissions': permissions_dict,
                                                   '_session': session_dict
                                               }
                                               }
                                           )
        # {"acknowledged":true}
        if es_response_raw.status_code != 200:
            raise exceptions.XimpiaAPIException(_(u'Error creating index "{}"'.format(index_name)))
        es_response = es_response_raw.json()
        if not es_response['acknowledged']:
            raise exceptions.XimpiaAPIException(_(u'Error creating index "{}"'.format(index_name)))
        logger.info(u'SetupSite :: created index {} response: {}'.format(
            index_name,
            es_response
        ))

    @classmethod
    def _create_site_app(cls, index_ximpia, index_site, site, app, now_es, languages, location):
        """
        Create site and app

        :param index_ximpia:
        :param index_site:
        :param site:
        :param app:
        :param now_es:
        :return:
        """
        # site
        site_data = {
            u'name': site,
            u'slug': slugify(site),
            u'url': u'http://{site_slug}.ximpia.com/'.format(slugify(site)),
            u'is_active': True,
            u'created_on': now_es
        }
        es_response_raw = req_session.post(
            '{}/{}/site'.format(settings.ELASTIC_SEARCH_HOST, index_ximpia),
            data=to_physical_doc('site', site_data))
        if es_response_raw.status_code != 200:
            exceptions.XimpiaAPIException(_(u'Could not write site "{}"'.format(site)))
        es_response = es_response_raw.json()
        site_id = es_response.get('_id', '')
        logger.info(u'SetupSite :: created site {} id: {}'.format(
            site,
            site_id
        ))
        site_data['id'] = site_id
        # app
        app_data = {
            u'name': app,
            u'slug': slugify(app),
            u'is_active': True,
            u'created_on': now_es
        }
        es_response_raw = req_session.post(
            '{}/{}/_app'.format(settings.ELASTIC_SEARCH_HOST, index_site),
            data=to_physical_doc('_app', app_data))
        if es_response_raw.status_code != 200:
            exceptions.XimpiaAPIException(_(u'Could not write app "{}"'.format(app)))
        es_response = es_response_raw.json()
        app_id = es_response.get('_id', '')
        app_data['id'] = app_id
        logger.info(u'SetupSite :: created app {} id: {}'.format(
            app,
            app_id
        ))
        # settings for app and site
        settings_data = {
            u'site': {
                u'id': site_id,
                u'name': site,
                u'slug': slugify(site)
            },
            u'app': None,
            u'fields': [
                {
                    u'name': u'languages',
                    u'value': json.dumps(languages)
                },
                {
                    u'name': u'location',
                    u'value': json.dumps(location)
                }
            ],
            u'created_on': now_es
        }
        es_response_raw = req_session.post(
            '{}/{}/_settings'.format(settings.ELASTIC_SEARCH_HOST, index_site),
            data=to_physical_doc('_settings', settings_data))
        if es_response_raw.status_code != 200:
            exceptions.XimpiaAPIException(_(u'Could not write settings for site "{}"'.format(site)))
        es_response = es_response_raw.json()
        logger.info(u'SetupSite :: created settings id: {}'.format(
            es_response.get('_id', '')
        ))
        return site_data, app_data, settings_data

    @classmethod
    def _create_permissions(cls, site, app, index_name, now_es):
        """
        Create permission can_admin

        :param app:
        :param index_name:
        :param now_es:
        :return:
        """
        es_response_raw = req_session.post(
            '{}/{}/_permission'.format(settings.ELASTIC_SEARCH_HOST, index_name),
            data=to_physical_doc('_permission', {
                u'name': u'can-admin',
                u'apps': [
                    {
                        u'site': site,
                        u'app': app
                    }
                ],
                u'created_on': now_es
            }))
        if es_response_raw.status_code != 200:
            exceptions.XimpiaAPIException(_(u'Could not write permission "can-admin"'))
        es_response = es_response_raw.json()
        logger.info(u'SetupSite :: created permission "can_admin" for app: {} id: {}'.format(
            app['name'],
            es_response.get('_id', '')
        ))

    def post(self, request, *args, **kwargs):
        data = request.data
        site = data['site']
        app = 'base'
        access_token = data['access_token']
        social_network = data['social_network']
        languages = data.get('languages', ['en'])
        location = data.get('location', 'us')
        default_groups = ['users', 'users-test', 'admin']

        if filter(lambda x: site.index(x) != -1, list(self.RESERVED_WORDS)):
            raise exceptions.XimpiaAPIException(_(u'Site name not allowed'))

        # We fetch information from social network with access_token, verify tokens, etc...
        # social_data is same for all social networks, a dictionary with data
        social_data = SocialNetworkResolution.get_network_user_data(social_network,
                                                                    access_token=access_token)

        index_name = '{site}__base'.format(site=site)
        index_ximpia = 'ximpia_api__base'

        # create index with settings and mappings:
        self._create_site_index(index_name)

        now_es = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 1. create site, app and settings
        site_data, app_data, settings_data = self._create_site_app(index_ximpia, index_name,
                                                                   site, app, now_es,
                                                                   languages, location)

        # 2. Permissions
        self._create_permissions(site, app, index_name, now_es)

        # 3. Groups, User, UserGroup
        user_raw = req_session.post(
            '{scheme}://{site}.ximpia.com/user-signup'.format(settings.SCHEME, settings.SITE),
            data={
                'access_token': access_token,
                'social_network': social_network
            }
        )
        if user_raw.status_code != 200:
            raise exceptions.XimpiaAPIException(_(u'Error creating user'))
        user = json.loads(user_raw.content)['user']

        response_ = {
            u'site': site_data,
            u'app': app_data,
            u'settings': settings_data,
            u'user': user['user'],
            u'groups': user['groups_data']
        }
        return response.Response(response_)
