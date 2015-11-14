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
from document import to_logical_doc

__author__ = 'jorgealegre'

logger = logging.getLogger(__name__)

VALID_KEY_CHARS = string.ascii_lowercase + string.digits


class Command(BaseCommand):
    help = 'Create document types for Ximpia API'
    can_import_settings = True

    def _create_index(self, index_name, **options):
        """
        Create index with document types mappings

        :param index_name:
        :param options:
        :return:
        """
        mappings_path = settings.BASE_DIR + 'apps/base/mappings'
        user_path = settings.BASE_DIR + 'apps/xp_user/mappings'
        document_path = settings.BASE_DIR + 'apps/document/mappings'

        # my-index.mm-dd-yyyyTHH:MM:SS with alias my-index
        index_name_physical = u'{}.{}'.format(
            index_name,
            datetime.now().strftime("%m-%d-%y.%H:%M:%S")
        )
        alias = index_name

        with open(settings.BASE_DIR + 'settings/settings_test.json') as f:
            settings_dict = json.loads(f.read())

        with open('{}/site.json'.format(mappings_path)) as f:
            site_dict = json.loads(f.read())

        with open('{}/account.json'.format(mappings_path)) as f:
            account_dict = json.loads(f.read())

        with open('{}/api_access.json'.format(mappings_path)) as f:
            api_access_dict = json.loads(f.read())

        with open('{}/urlconf.json'.format(mappings_path)) as f:
            urlconf_dict = json.loads(f.read())

        with open('{}/app.json'.format(mappings_path)) as f:
            app_dict = json.loads(f.read())

        with open('{}/settings.json'.format(mappings_path)) as f:
            settings__dict = json.loads(f.read())

        with open('{}/user.json'.format(user_path)) as f:
            user_dict = json.loads(f.read())

        with open('{}/group.json'.format(user_path)) as f:
            group_dict = json.loads(f.read())

        with open('{}/user-group.json'.format(user_path)) as f:
            user_group_dict = json.loads(f.read())

        with open('{}/permission.json'.format(user_path)) as f:
            permissions_dict = json.loads(f.read())

        with open('{}/invite.json'.format(user_path)) as f:
            invite_dict = json.loads(f.read())

        with open('{}/tag.json'.format(document_path)) as f:
            tag_dict = json.loads(f.read())

        with open('{}/field_version.json'.format(document_path)) as f:
            field_version_dict = json.loads(f.read())

        with open('{}/session.json'.format(settings.BASE_DIR + 'apps/xp_sessions/mappings')) as f:
            session_dict = json.loads(f.read())

        es_response_raw = requests.post('{}/{}'.format(settings.ELASTIC_SEARCH_HOST, index_name_physical),
                                        data=json.dumps({
                                            'settings': settings_dict,
                                            'mappings': {
                                                'account': account_dict,
                                                'api_access': api_access_dict,
                                                'site': site_dict,
                                                'urlconf': urlconf_dict,
                                                'app': app_dict,
                                                'settings': settings__dict,
                                                'user': user_dict,
                                                'group': group_dict,
                                                'user-group': user_group_dict,
                                                'permission': permissions_dict,
                                                'tag': tag_dict,
                                                'field_version': field_version_dict,
                                                'invite': invite_dict,
                                                'session': session_dict,
                                            },
                                            'aliases': {
                                                alias: {}
                                            }
                                        })
                                        )

        if es_response_raw.status_code != 200:
            raise XimpiaAPIException(_(u'Error creating index "{}" {}'.format(
                index_name,
                es_response_raw.content
            )))
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
    def _create_tag(cls, index_name, now_es, version='v1'):
        """
        Create tag v1

        :param index_name:
        :param now_es:
        :return:
        """
        tag_data = {
            u'name__v1': version,
            u'slug__v1': version,
            u'is_active__v1': True,
            u'permissions__v1': None,
            u'public__v1': True,
            u'created_on__v1': now_es,
        }
        es_response_raw = requests.post(
            '{}/{}/_tag'.format(settings.ELASTIC_SEARCH_HOST, index_name),
            data=json.dumps(tag_data))
        if es_response_raw.status_code != 200:
            XimpiaAPIException(_(u'Could not write tag v1'))
        es_response = es_response_raw.json()
        logger.info(u'SetupSite :: created tag "v1" id: {}'.format(
            es_response.get('_id', '')
        ))
        return to_logical_doc('_tag', tag_data)

    @classmethod
    def _create_site_app(cls, index_name, site, app, now_es, languages, location, invite_only,
                         access_token, tag_data, organization_name, public=False, account=None,
                         domains=None):
        """
        Create site, settings and app

        :param index_name:
        :param site:
        :param app:
        :param now_es:
        :param languages:
        :param location:
        :param invite_only:
        :param access_token:
        :param tag_data:
        :return:
        """
        # account
        # site
        site_data = {
            u'name__v1': site,
            u'slug__v1': slugify(site),
            u'url__v1': u'http://{}.ximpia.io/'.format(slugify(site)),
            u'is_active__v1': True,
            u'created_on__v1': now_es
        }
        if invite_only:
            site_data[u'invites'] = {
                u'age_days__v1': 2,
                u'active__v1': True,
                u'created_on__v1': now_es,
                u'updated_on__v1': now_es,
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
        site_data_logical = to_logical_doc('site', site_data)
        site_data_logical['id'] = site_id
        # app
        app_data = {
            u'name__v1': app,
            u'slug__v1': slugify(app),
            u'is_active__v1': True,
            u'social__v1': {
                u'facebook__v1': {
                    u'access_token__v1': access_token
                }
            },
            u'created_on__v1': now_es
        }
        es_response_raw = requests.post(
            '{}/{}/_app'.format(settings.ELASTIC_SEARCH_HOST, index_name),
            data=app_data)
        if es_response_raw.status_code != 200:
            XimpiaAPIException(_(u'Could not write app "{}"'.format(app)))
        es_response = es_response_raw.json()
        app_id = es_response.get('_id', '')
        app_data_logical = to_logical_doc('_app', app_data)
        app_data_logical['id'] = app_id
        logger.info(u'SetupSite :: created app {} id: {}'.format(
            app,
            app_id
        ))
        # settings for app and site
        settings_input = [
            (u'languages', json.dumps(languages)),
            (u'location', location)]
        settings_data = {
            u'site__v1': {
                u'id__v1': site_id,
                u'name__v1': site,
                u'slug__v1': slugify(site)
            },
            u'app__v1': None,
            u'tag__v1': tag_data,
            u'fields__v1': None,
            u'created_on__v1': now_es
        }
        settings_output = []
        for setting_item in settings_input:
            db_settings = settings_data.update({
                u'name__v1': setting_item[0],
                u'value__v1': setting_item[1]
            })
            es_response_raw = requests.post(
                '{}/{}/_settings'.format(settings.ELASTIC_SEARCH_HOST, index_name),
                data=db_settings)
            if es_response_raw.status_code != 200:
                XimpiaAPIException(_(u'Could not write settings for site "{}"'.format(site)))
            es_response = es_response_raw.json()
            logger.info(u'SetupSite :: created settings id: {}'.format(
                es_response.get('_id', '')
            ))
            settings_data_logical = to_logical_doc('_settings', db_settings)
            settings_output.append(settings_data_logical)

        # api_access
        api_access = {
            u'site__v1': {
                u'id__v1': site_id,
                u'name__v1': site,
                u'slug__v1': slugify(site)
            },
            u'api_secret__v1': get_random_string(32, VALID_KEY_CHARS),
            u'domains__v1': domains,
            u'created_on': now_es,
        }
        es_response_raw = requests.post(
            '{}/{}/api_access'.format(settings.ELASTIC_SEARCH_HOST, index_name),
            data=api_access)
        if es_response_raw.status_code != 200:
            XimpiaAPIException(_(u'Could not write api access "{}"'.format(site)))
        es_response = es_response_raw.json()
        api_access_key = es_response.get('_id', '')
        logger.info(u'SetupSite :: created api access {} id: {}'.format(
            site,
            api_access_key
        ))
        api_access_logical = to_logical_doc('api_access', api_access)
        api_access_logical['id'] = api_access_key

        # account
        account_data = {
            u'organization__v1': {
                u'name__v1': organization_name
            },
            u'created_on': now_es,
        }
        es_response_raw = requests.post(
            '{}/{}/account/{}'.format(settings.ELASTIC_SEARCH_HOST, index_name, account),
            data=account_data)
        if es_response_raw.status_code != 200:
            XimpiaAPIException(_(u'Could not write account "{}"'.format(site)))
        es_response = es_response_raw.json()
        logger.info(u'SetupSite :: created account {}'.format(
            account,
        ))
        account_data_logical = to_logical_doc('account', account_data)
        account_data_logical['id'] = es_response.get('_id', '')

        return site_data_logical, app_data_logical, settings_output, api_access_logical, account_data_logical

    @classmethod
    def _create_permissions(cls, site, app, index_name, now_es):
        """
        Create permission can_admin

        :param app:
        :param index_name:
        :param now_es:
        :return:
        """
        permissions = [
            u'can-admin'
        ]
        output_permissions = []
        for permission in permissions:
            db_permission = {
                u'name__v1': permission,
                u'apps__v1': [
                    {
                        u'site__v1': site,
                        u'app__v1': app
                    }
                ],
                u'data__v1': None,
                u'created_on__v1': now_es
            }
            es_response_raw = requests.post(
                '{}/{}/_permission'.format(settings.ELASTIC_SEARCH_HOST, index_name),
                data=json.dumps(db_permission))
            if es_response_raw.status_code != 200:
                XimpiaAPIException(_(u'Could not write permission "can-admin"'))
            es_response = es_response_raw.json()
            logger.info(u'SetupSite :: created permission "can_admin" for app: {} id: {}'.format(
                app['name'],
                es_response.get('_id', '')
            ))
            permission_logical = to_logical_doc('_permission', db_permission)
            permission_logical['id'] = es_response.get('_id', '')
            output_permissions.append(permission_logical)
        return output_permissions

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
        }
        groups_data = []
        for group in groups:
            group_data = {
                u'name__v1': group,
                u'slug__v1': slugify(group),
                u'tags__v1': None,
                u'created_on__v1': now_es,
            }
            if group in permissions:
                group_data[u'permissions__v1'] = [
                    {
                        u'name__v1': permissions[group],
                        u'created_on__v1': now_es
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
            group_data_logical = to_logical_doc('_group', group_data)
            group_data_logical['id'] = es_response.get('_id', '')
            groups_data.append(group_data_logical)
        # user
        user_data = {
            u'alias__v1': None,
            u'email__v1': social_data.get('email', None),
            u'password__v1': None,
            u'avatar__v1': social_data.get('profile_picture', None),
            u'name__v1': social_data.get('name', None),
            u'social_networks__v1': [
                {
                    u'network__v1': social_network,
                    u'user_id__v1': social_data.get('user_id', None),
                    u'access_token__v1': social_data.get('access_token', None),
                    u'state__v1': None,
                    u'scopes__v1': social_data.get('scopes', None),
                    u'has_auth__v1': True,
                    u'link__v1': social_data.get('link', None),
                }
            ],
            u'permissions__v1': None,
            u'groups__v1': map(lambda x: {
                u'id__v1': x['id'],
                u'name__v1': x['name']
            }, groups_data),
            u'is_active__v1': True,
            u'token__v1': None,
            u'last_login__v1': None,
            u'session_id__v1': None,
            u'created_on__v1': now_es,
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
        user_data_logical = to_logical_doc('_user', user_data)
        user_data_logical['id'] = es_response.get('_id', '')
        # users groups
        es_response_raw = requests.post(
            '{}/{}/_user-group'.format(settings.ELASTIC_SEARCH_HOST, index_name),
            data={
                u'user__v1': map(lambda x: {
                    u'id__v1': x[u'id'],
                    u'username__v1': x[u'username'],
                    u'email__v1': x[u'email'],
                    u'avatar__v1': x[u'avatar'],
                    u'name__v1': x[u'name'],
                    u'social_networks__v1': x[u'social_networks'],
                    u'permissions__v1': x[u'permissions'],
                    u'created_on__v1': x[u'created_on'],
                }, user_data),
                u'group__v1': map(lambda x: {
                    u'id__v1': x[u'id'],
                    u'name__v1': x[u'name'],
                    u'slug__v1': x[u'slug'],
                    u'tags__v1': x[u'tags'],
                    u'created_on__v1': x[u'created_on']
                }, groups_data),
                u'created_on__v1': now_es,
            })
        if es_response_raw.status_code != 200:
            XimpiaAPIException(_(u'Could not write user group'))
        es_response = es_response_raw.json()
        logger.info(u'SetupSite :: created user group id: {}'.format(
            es_response.get('_id', '')
        ))
        return user_data_logical, groups_data

    def handle(self, *args, **options):
        access_token = options['access_token']
        social_network = options['social_network']
        invite_only = options['invite_only']
        organization_name = 'Ximpia Inc'
        account = 'ximpia'

        index_name = 'ximpia_api__base'
        site = 'Ximpia API'
        app = 'base'
        public = False
        domains = ['ximpia.com']
        languages = ['en']
        location = 'us'
        default_groups = [
            u'users',
            u'users-test',
            u'admin',
            u'staff'
        ]

        now_es = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self._create_index(index_name, **options)

        tag_data = self._create_tag(index_name, now_es)

        site_tuple = self._create_site_app(index_name, site, app, now_es,
                                           languages, location, invite_only,
                                           access_token, tag_data, organization_name,
                                           public=public, account=account, domains=domains)
        site_data, app_data, settings_data, api_access, account_data = site_tuple

        social_data = SocialNetworkResolution.get_network_user_data(social_network,
                                                                    access_token=access_token)

        # 2. Permissions
        permissions_data = self._create_permissions(site, app, index_name, now_es)

        # 3. Groups, User, UserGroup
        user_data, groups_data = self._create_user_groups(index_name, default_groups, social_network,
                                                          social_data, now_es)

        if 'verbosity' in options and options['verbosity'] != '0':
            self.stdout.write(u'{}'.format(
                pprint.PrettyPrinter(indent=4).pformat({
                    u'account': account_data,
                    u'site': site_data,
                    u'app': app_data,
                    u'settings': settings_data,
                    u'user': user_data,
                    u'groups': groups_data,
                    u'permissions': permissions_data,
                    u'api_access': api_access
                })
            ))
