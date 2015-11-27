import logging
import requests
import json
import pprint
import string
import time

from datetime import datetime, timedelta

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
            '{}/{}/tag'.format(settings.ELASTIC_SEARCH_HOST, index_name),
            data=json.dumps(tag_data))
        if es_response_raw.status_code not in [200, 201]:
            raise XimpiaAPIException(_(u'Could not write tag v1 :: {} :: {}'.format(
                es_response_raw.status_code,
                es_response_raw.content)))
        es_response = es_response_raw.json()
        logger.info(u'SetupSite :: created tag "v1" id: {}'.format(
            es_response.get('_id', '')
        ))
        tag_data['id'] = es_response.get('_id', '')
        return to_logical_doc('tag', tag_data)

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
        from base import SocialNetworkResolution
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
            data=json.dumps(site_data))
        if es_response_raw.status_code not in [200, 201]:
            raise XimpiaAPIException(_(u'Could not write site "{}" :: {}'.format(
                site, es_response_raw.content)))
        es_response = es_response_raw.json()
        site_id = es_response.get('_id', '')
        logger.info(u'SetupSite :: created site {} id: {}'.format(
            site,
            site_id
        ))
        site_data_logical = to_logical_doc('site', site_data)
        site_data_logical['id'] = site_id
        # app
        app_access_token = SocialNetworkResolution.get_app_access_token(settings.XIMPIA_FACEBOOK_APP_ID,
                                                                        settings.XIMPIA_FACEBOOK_APP_SECRET)
        app_data = {
            u'name__v1': app,
            u'slug__v1': slugify(app),
            u'is_active__v1': True,
            u'social__v1': {
                u'facebook__v1': {
                    u'access_token__v1': app_access_token
                }
            },
            u'created_on__v1': now_es
        }
        es_response_raw = requests.post(
            '{}/{}/app'.format(settings.ELASTIC_SEARCH_HOST, index_name),
            data=json.dumps(app_data))
        if es_response_raw.status_code not in [200, 201]:
            raise XimpiaAPIException(_(u'Could not write app "{}" :: {}'.format(
                app, es_response_raw.content)))
        es_response = es_response_raw.json()
        app_id = es_response.get('_id', '')
        app_data_logical = to_logical_doc('app', app_data)
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
            settings_data.update({
                u'setting_name__v1': setting_item[0],
                u'setting_value__v1': setting_item[1]
            })
            es_response_raw = requests.post(
                '{}/{}/settings'.format(settings.ELASTIC_SEARCH_HOST, index_name),
                data=json.dumps(settings_data))
            if es_response_raw.status_code not in [200, 201]:
                raise XimpiaAPIException(_(u'Could not write settings for site "{}" :: {}'.format(
                    site, es_response_raw.content)))
            es_response = es_response_raw.json()
            logger.info(u'SetupSite :: created settings id: {}'.format(
                es_response.get('_id', '')
            ))
            settings_data_logical = to_logical_doc('settings', settings_data)
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
            u'created_on__v1': now_es,
        }
        es_response_raw = requests.post(
            '{}/{}/api_access'.format(settings.ELASTIC_SEARCH_HOST, index_name),
            data=json.dumps(api_access))
        if es_response_raw.status_code not in [200, 201]:
            raise XimpiaAPIException(_(u'Could not write api access "{}" :: {}'.format(
                site, es_response_raw.content)))
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
            u'account_name__v1': account,
            u'created_on__v1': now_es,
        }
        es_response_raw = requests.post(
            '{}/{}/account'.format(settings.ELASTIC_SEARCH_HOST, index_name),
            data=json.dumps(account_data))
        if es_response_raw.status_code not in [200, 201]:
            raise XimpiaAPIException(_(u'Could not write account "{}" :: {}'.format(
                site, es_response_raw.content)))
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
                        u'site_slug__v1': slugify(site),
                        u'app_slug__v1': slugify(app)
                    }
                ],
                u'data__v1': None,
                u'created_on__v1': now_es
            }
            es_response_raw = requests.post(
                '{}/{}/permission'.format(settings.ELASTIC_SEARCH_HOST, index_name),
                data=json.dumps(db_permission))
            if es_response_raw.status_code not in [200, 201]:
                raise XimpiaAPIException(_(u'Could not write permission "can-admin" :: {}'.format(
                    es_response_raw.content
                )))
            es_response = es_response_raw.json()
            logger.info(u'SetupSite :: created permission "can_admin" for app: {} id: {}'.format(
                app,
                es_response.get('_id', '')
            ))
            permission_logical = to_logical_doc('permission', db_permission)
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
        groups_data_logical = {}
        for group in groups:
            group_data = {
                u'group_name__v1': group,
                u'slug__v1': slugify(group),
                u'tags__v1': None,
                u'created_on__v1': now_es,
            }
            if group in permissions:
                group_data[u'group_permissions__v1'] = [
                    {
                        u'name__v1': permissions[group],
                        u'created_on__v1': now_es
                    }
                ]
            es_response_raw = requests.post(
                '{}/{}/group'.format(settings.ELASTIC_SEARCH_HOST, index_name),
                data=json.dumps(group_data))
            if es_response_raw.status_code not in [200, 201]:
                raise XimpiaAPIException(_(u'Could not write group "{}" :: {}'.format(
                    group, es_response_raw.content)))
            es_response = es_response_raw.json()
            logger.info(u'SetupSite :: created group {} id: {}'.format(
                group,
                es_response.get('_id', u'')
            ))
            # group_ids[group] = es_response.get('_id', '')
            group_data_logical = to_logical_doc('group', group_data)
            group_data_logical['id'] = es_response.get('_id', '')
            groups_data_logical[group_data_logical['id']] = group_data_logical
            groups_data.append(group_data_logical)
        # user
        seconds_two_months = str(int((datetime.now() + timedelta(days=60) -
                                      datetime(1970, 1, 1)).total_seconds()))
        user_data = {
            u'username__v1': " ",
            u'alias__v1': "",
            u'email__v1': social_data.get('email', None),
            u'password__v1': None,
            u'avatar__v1': social_data.get('profile_picture', None),
            u'user_name__v1': social_data.get('name', None),
            u'social_networks__v1': [
                {
                    u'network__v1': social_network,
                    u'user_id__v1': social_data.get('user_id', None),
                    u'access_token__v1': social_data.get('access_token', None),
                    u'state__v1': None,
                    u'scopes__v1': social_data.get('scopes', None),
                    u'has_auth__v1': True,
                    u'link__v1': social_data.get('link', None),
                    u'expires_at__v1': social_data.get('expires_at', None),
                }
            ],
            u'user_permissions__v1': None,
            u'groups__v1': map(lambda x: {
                u'id__v1': x['id'],
                u'name__v1': x['group_name']
            }, groups_data),
            u'is_active__v1': True,
            u'token__v1': {
                u'key__v1': get_random_string(100, VALID_KEY_CHARS),
                u'created_on__v1': now_es,
            },
            u'expires_at__v1': time.strftime(
                '%Y-%m-%dT%H:%M:%S',
                time.gmtime(float(social_data.get('expires_at', seconds_two_months)))),
            u'session_id__v1': None,
            u'created_on__v1': now_es,
        }
        es_response_raw = requests.post(
            '{}/{}/user'.format(settings.ELASTIC_SEARCH_HOST, index_name),
            data=json.dumps(user_data))
        if es_response_raw.status_code not in [200, 201]:
            raise XimpiaAPIException(_(u'Could not write user "{}.{}" :: {}'.format(
                social_network,
                social_data.get('user_id', None),
                es_response_raw.content)))
        es_response = es_response_raw.json()
        logger.info(u'SetupSite :: created user id: {}'.format(
            es_response.get('_id', '')
        ))
        user_data_logical = to_logical_doc('user', user_data)
        user_data_logical['id'] = es_response.get('_id', '')
        user_data['id'] = es_response.get('_id', '')
        # users groups
        for group_data in groups_data:
            es_response_raw = requests.post(
                '{}/{}/user-group'.format(settings.ELASTIC_SEARCH_HOST, index_name),
                data=json.dumps({
                    u'user__v1': {
                        u'id__v1': user_data_logical[u'id'],
                        u'username__v1': user_data_logical[u'username'],
                        u'email__v1': user_data_logical[u'email'],
                        u'avatar__v1': user_data_logical[u'avatar'],
                        u'user_name__v1': user_data_logical[u'user_name'],
                        u'social_networks__v1': user_data_logical[u'social_networks'],
                        u'user_permissions__v1': user_data_logical[u'user_permissions'],
                        u'created_on__v1': user_data_logical[u'created_on'],
                    },
                    u'group__v1': {
                        u'id__v1': group_data[u'id'],
                        u'group_name__v1': group_data[u'group_name'],
                        u'slug__v1': group_data[u'slug'],
                        u'tags__v1': group_data[u'tags'],
                        u'created_on__v1': group_data[u'created_on']
                    },
                    u'created_on__v1': now_es,
                }))
            if es_response_raw.status_code not in [200, 201]:
                raise XimpiaAPIException(_(u'Could not write user group :: {}'.format(
                    es_response_raw.content
                )))
            es_response = es_response_raw.json()
            es_response['id'] = es_response.get('_id', '')
            logger.info(u'SetupSite :: created user group id: {}'.format(
                es_response.get('_id', '')
            ))
        return user_data_logical, groups_data

    def handle(self, *args, **options):
        access_token = options['access_token']
        social_network = options['social_network']
        invite_only = options['invite_only']
        skip_auth_social = options.get('skip_auth_social', False)
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

        now_es = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

        self._create_index(index_name, **options)

        tag_data = self._create_tag(index_name, now_es)

        site_tuple = self._create_site_app(index_name, site, app, now_es,
                                           languages, location, invite_only,
                                           access_token, tag_data, organization_name,
                                           public=public, account=account, domains=domains)
        site_data, app_data, settings_data, api_access, account_data = site_tuple
        settings.APP_ID = app_data['id']

        # social
        # login access token for user to use
        social_data = SocialNetworkResolution.get_network_user_data(social_network,
                                                                    access_token=access_token,
                                                                    skip_auth_social=skip_auth_social)

        # 2. Permissions
        permissions_data = self._create_permissions(site, app, index_name, now_es)

        # 3. Groups, User, UserGroup
        user_data, groups_data = self._create_user_groups(index_name, default_groups, social_data,
                                                          social_network, now_es)

        if 'verbosity' in options and options['verbosity'] == 2:
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
