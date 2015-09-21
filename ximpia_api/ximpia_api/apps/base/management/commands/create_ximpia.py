import logging
import requests
import json
import pprint
import string

from datetime import datetime

from django.core.management.base import BaseCommand
from django.utils.translation import ugettext as _
from django.utils.text import slugify
from django.utils.crypto import get_random_string
from django.conf import settings

from base import SocialNetworkResolution
from base.exceptions import XimpiaAPIException
from django.contrib.auth import authenticate, login

__author__ = 'jorgealegre'

logger = logging.getLogger(__name__)

VALID_KEY_CHARS = string.ascii_lowercase + string.digits


class Command(BaseCommand):
    help = 'Create document types for Ximpia API'
    can_import_settings = True

    def _create_index(self, index_name, **options):
        mappings_path = settings.BASE_DIR + 'apps/base/mappings'
        user_path = settings.BASE_DIR + 'apps/user/mappings'
        document_path = settings.BASE_DIR + 'apps/document/mappings'

        with open(settings.BASE_DIR + 'settings/settings.json') as f:
            settings_dict = json.loads(f.read())

        with open('{}/site.json'.format(mappings_path)) as f:
            site_dict = json.loads(f.read())

        with open('{}/urlconf.json'.format(mappings_path)) as f:
            urlconf_dict = json.loads(f.read())

        with open('{}/_app.json'.format(mappings_path)) as f:
            app_dict = json.loads(f.read())

        with open('{}/_settings.json'.format(mappings_path)) as f:
            settings__dict = json.loads(f.read())

        with open('{}/_user.json'.format(user_path)) as f:
            user_dict = json.loads(f.read())

        with open('{}/_group.json'.format(user_path)) as f:
            group_dict = json.loads(f.read())

        with open('{}/_user-group.json'.format(user_path)) as f:
            user_group_dict = json.loads(f.read())

        with open('{}/_permission.json'.format(user_path)) as f:
            permissions_dict = json.loads(f.read())

        with open('{}/_invite.json'.format(user_path)) as f:
            invite_dict = json.loads(f.read())

        with open('{}/_tag.json'.format(document_path)) as f:
            tag_dict = json.loads(f.read())

        with open('{}/_field_version.json'.format(document_path)) as f:
            field_version_dict = json.loads(f.read())

        es_response_raw = requests.post('{}/{}'.format(settings.ELASTIC_SEARCH_HOST, index_name),
                                        data={
                                            'settings': settings_dict,
                                            'mappings': {
                                                'site': site_dict,
                                                'urlconf': urlconf_dict
                                                '_app': app_dict,
                                                '_settings': settings__dict,
                                                '_user': user_dict,
                                                '_group': group_dict,
                                                '_user-group': user_group_dict,
                                                '_permissions': permissions_dict,
                                                '_tag': tag_dict,
                                                '_field_version': field_version_dict,
                                                '_invite': invite_dict
                                                }
                                            }
                                        )

        if es_response_raw.status_code != 200:
            raise XimpiaAPIException(_(u'Error creating index "{}"'.format(index_name)))
        es_response = es_response_raw.json()
        if not es_response['acknowledged']:
            raise XimpiaAPIException(_(u'Error creating index "{}"'.format(index_name)))
        logger.info(u'SetupSite :: created index {} response: {}'.format(
            index_name,
            es_response
        ))

        if 'verbosity' in options and options['verbosity'] != '0':
            self.stdout.write(u'created index {} response: {}'.format(
                index_name,
                es_response
            ))

    @classmethod
    def _create_site_app(cls, index_name, site, app, now_es, languages, location):
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
            '{}/{}/_app'.format(settings.ELASTIC_SEARCH_HOST, index_name),
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
            '{}/{}/_settings'.format(settings.ELASTIC_SEARCH_HOST, index_name),
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
        # generate token
        token = get_random_string(400, VALID_KEY_CHARS)
        # generate session
        session_id = get_random_string(50, VALID_KEY_CHARS)
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
            u'token': token,
            u'last_login': now_es,
            u'session_id': session_id,
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
        user = authenticate(token)
        return user_data, groups_data

    def handle(self, *args, **options):
        access_token = options['access_token']
        social_network = options['social_network']

        index_name = 'ximpia_api__base'
        site = 'Ximpia API'
        app = 'base'
        languages = ['en']
        location = 'us'
        default_groups = ['users', 'users-test', 'admin']

        now_es = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        social_data = SocialNetworkResolution.get_network_user_data(social_network,
                                                                    access_token=access_token)

        self._create_index(index_name, **options)

        site_data, app_data, settings_data = self._create_site_app(index_name, site, app, now_es,
                                                                   languages, location)

        # 2. Permissions
        self._create_permissions(site, app, index_name, now_es)

        # 3. Groups, User, UserGroup
        user_data, groups_data = self._create_user_groups(index_name, default_groups, social_network,
                                                          social_data, now_es)

        if 'verbosity' in options and options['verbosity'] != '0':
            self.stdout.write(u'{}'.format(
                pprint.PrettyPrinter(indent=4).pformat({
                    u'site': site_data,
                    u'app': app_data,
                    u'settings': settings_data,
                    u'user': user_data,
                    u'groups': groups_data
                })
            ))
