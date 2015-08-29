import requests
import json
import logging

from datetime import datetime

from rest_framework import viewsets, generics, response

from django.conf import settings
from django.utils.translation import ugettext as _
from django.utils.text import slugify

from . import SocialNetworkResolution
from exceptions import XimpiaAPIException

__author__ = 'jorgealegre'

logger = logging.getLogger(__name__)


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
        with open(settings.BASE_DIR + 'settings/settings.json') as f:
            settings_dict = json.loads(f.read())

        with open('{}/user.json'.format(user_path)) as f:
            user_dict = json.loads(f.read())

        with open('{}/group.json'.format(user_path)) as f:
            group_dict = json.loads(f.read())

        with open('{}/user-group.json'.format(user_path)) as f:
            user_group_dict = json.loads(f.read())

        with open('{}/permission.json'.format(user_path)) as f:
            permissions_dict = json.loads(f.read())

        es_response_raw = requests.post('{}/{}'.format(settings.ELASTIC_SEARCH_HOST, index_name),
                                        data={
                                            'settings': settings_dict,
                                            'mappings': {
                                                '_user': user_dict,
                                                '_group': group_dict,
                                                '_user-group': user_group_dict,
                                                '_permissions': permissions_dict
                                                }
                                            }
                                        )
        # {"acknowledged":true}
        if es_response_raw.status_code != 200:
            raise XimpiaAPIException(_(u'Error creating index "{}"'.format(index_name)))
        es_response = es_response_raw.json()
        if not es_response['acknowledged']:
            raise XimpiaAPIException(_(u'Error creating index "{}"'.format(index_name)))
        logger.info(u'SetupSite :: created index {} response: {}'.format(
            index_name,
            es_response
        ))

    @classmethod
    def _create_site_app(cls, index_name, site, app, now_es, languages, location):
        """
        Create site and app

        :param index_name:
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
        es_response_raw = requests.post(
            '{}/{}/site'.format(settings.ELASTIC_SEARCH_HOST, index_name),
            data=site_data)
        if es_response_raw.status_code != 200:
            XimpiaAPIException(_(u'Could not write site "{}"'.format(site)))
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
        es_response_raw = requests.post(
            '{}/{}/app'.format(settings.ELASTIC_SEARCH_HOST, index_name),
            data=app_data)
        if es_response_raw.status_code != 200:
            XimpiaAPIException(_(u'Could not write app "{}"'.format(app)))
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
        es_response_raw = requests.post(
            '{}/{}/settings'.format(settings.ELASTIC_SEARCH_HOST, index_name),
            data=settings_data)
        if es_response_raw.status_code != 200:
            XimpiaAPIException(_(u'Could not write settings for site "{}"'.format(site)))
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
        es_response_raw = requests.post(
            '{}/{}/_permission'.format(settings.ELASTIC_SEARCH_HOST, index_name),
            data={
                u'name': u'can-admin',
                u'apps': [
                    {
                        u'site': site,
                        u'app': app
                    }
                ],
                u'created_on': now_es
            })
        if es_response_raw.status_code != 200:
            XimpiaAPIException(_(u'Could not write permission "can-admin"'))
        es_response = es_response_raw.json()
        logger.info(u'SetupSite :: created permission "can_admin" for app: {} id: {}'.format(
            app['name'],
            es_response.get('_id', '')
        ))

    @classmethod
    def _create_user_groups(cls, index_name, groups, social_data, social_network, now_es):
        """
        Create Groups, User and User mappings to Groups

        :param index_name:
        :param groups:
        :param social_data:
        :param social_network:
        :param now_es:
        :return:
        """
        # group
        permissions = {
            u'admin': u'can-admin',
            u'users-test': u'can-test'
        }
        groups_data = []
        for group in groups:
            group_data = {
                u'name': group,
                u'slug': slugify(group),
                u'tags': None,
                u'created_on': now_es,
            }
            if group in permissions:
                group_data['permissions'] = [
                    {
                        u'name': permissions[group],
                        u'created_on': now_es
                    }
                ]
            es_response_raw = requests.post(
                '{}/{}/_group'.format(settings.ELASTIC_SEARCH_HOST, index_name),
                data=group_data)
            if es_response_raw.status_code != 200:
                XimpiaAPIException(_(u'Could not write group "{}"'.format(group)))
            es_response = es_response_raw.json()
            logger.info(u'SetupSite :: created group {} id: {}'.format(
                group,
                es_response.get('_id', u'')
            ))
            # group_ids[group] = es_response.get('_id', '')
            groups_data.append(group_data.update({
                u'id': es_response.get('_id', ''),
            }))
        # user
        user_data = {
            u'alias': None,
            u'email': social_data.get('email', None),
            u'password': None,
            u'avatar': social_data.get('profile_picture', None),
            u'name': social_data.get('name', None),
            u'social_networks': [
                {
                    u'network': social_network,
                    u'user_id': social_data.get('user_id', None),
                    u'access_token': social_data.get('access_token', None),
                    u'state': None,
                    u'scopes': social_data.get('scopes', None),
                    u'has_auth': True,
                    u'link': social_data.get('link', None),
                }
            ],
            u'permissions': None,
            u'groups': map(lambda x: {
                u'id': x['id'],
                u'name': x['name']
            }, groups_data),
            u'is_active': True,
            u'token': None,
            u'last_login': None,
            u'session_id': None,
            u'created_on': now_es,
        }
        es_response_raw = requests.post(
            '{}/{}/_user'.format(settings.ELASTIC_SEARCH_HOST, index_name),
            data=user_data)
        if es_response_raw.status_code != 200:
            XimpiaAPIException(_(u'Could not write user "{}.{}"'.format(
                social_network,
                social_data.get('user_id', None))))
        es_response = es_response_raw.json()
        logger.info(u'SetupSite :: created user id: {}'.format(
            es_response.get('_id', '')
        ))
        user_data['id'] = es_response.get('_id', '')
        # users groups
        es_response_raw = requests.post(
            '{}/{}/_user-group'.format(settings.ELASTIC_SEARCH_HOST, index_name),
            data={
                u'user': map(lambda x: {
                    'id': x['id'],
                    'username': x['username'],
                    'email': x['email'],
                    'avatar': x['avatar'],
                    'name': x['name'],
                    'social_networks': x['social_networks'],
                    'permissions': x['permissions'],
                    'created_on': x['created_on'],
                }, user_data),
                u'group': map(lambda x: {
                    'id': x['id'],
                    'name': x['name'],
                    'slug': x['slug'],
                    'tags': x['tags'],
                    'created_on': x['created_on']
                }, groups_data),
                u'created_on': now_es,
            })
        if es_response_raw.status_code != 200:
            XimpiaAPIException(_(u'Could not write user group'))
        es_response = es_response_raw.json()
        logger.info(u'SetupSite :: created user group id: {}'.format(
            es_response.get('_id', '')
        ))
        return user_data, groups_data

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
            raise XimpiaAPIException(_(u'Site name not allowed'))

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
        site_data, app_data, settings_data = self._create_site_app(index_ximpia, site, app, now_es,
                                                                   languages, location)

        # 2. Permissions
        self._create_permissions(site, app, index_name, now_es)

        # 3. Groups, User, UserGroup
        user_data, groups_data = self._create_user_groups(index_name, default_groups, social_network,
                                                          social_data, now_es)

        response_ = {
            u'site': site_data,
            u'app': app_data,
            u'settings': settings_data,
            u'user': user_data,
            u'groups': groups_data
        }
        return response.Response(response_)
