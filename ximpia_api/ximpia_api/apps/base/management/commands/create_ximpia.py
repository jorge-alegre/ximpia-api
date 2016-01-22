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

from base import SocialNetworkResolution, refresh_index
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

        with open('{}/field-version.json'.format(document_path)) as f:
            field_version_dict = json.loads(f.read())

        with open('{}/session.json'.format(settings.BASE_DIR + 'apps/xp_sessions/mappings')) as f:
            session_dict = json.loads(f.read())

        with open('{}/document_definition.json'.format(document_path)) as f:
            document_definition_dict = json.loads(f.read())

        es_response_raw = requests.post('{}/{}'.format(settings.ELASTIC_SEARCH_HOST, index_name_physical),
                                        data=json.dumps({
                                            'settings': settings_dict,
                                            'mappings': {
                                                'account': account_dict,
                                                'site': site_dict,
                                                'urlconf': urlconf_dict,
                                                'app': app_dict,
                                                'settings': settings__dict,
                                                'user': user_dict,
                                                'group': group_dict,
                                                'user-group': user_group_dict,
                                                'permission': permissions_dict,
                                                'tag': tag_dict,
                                                'field-version': field_version_dict,
                                                'invite': invite_dict,
                                                'session': session_dict,
                                                'document-definition': document_definition_dict,
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
    def _create_tag(cls, index_name, now_es, version=settings.DEFAULT_VERSION):
        """
        Create tag v1

        :param index_name:
        :param now_es:
        :return:
        """
        tag_data = {
            u'tag__name__v1': version,
            u'tag__slug__v1': version,
            u'tag__is_active__v1': True,
            u'tag__permissions__v1': None,
            u'tag__public__v1': True,
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
        from document import Document
        # generate api access key
        counter = 0
        api_access_key = get_random_string(32, VALID_KEY_CHARS)
        while Document.objects.filter('site', api_access__api_key=api_access_key):
            api_access_key = get_random_string(32, VALID_KEY_CHARS)
            if counter > 10:
                raise XimpiaAPIException(_(
                    u'Maximum number of iterations for generate api key'
                ))
            counter += 1
        # site
        site_data = {
            u'site__name__v1': site,
            u'site__slug__v1': slugify(site),
            u'site__url__v1': u'http://{}.ximpia.io/'.format(slugify(site)),
            u'site__is_active__v1': True,
            u'site__domains__v1': map(lambda x: {'domain_name__v1': x}, domains),
            u'site__public__v1': public,
            u'site__api_access__v1': {
                u'site__api_access__key__v1': api_access_key,
                u'site__api_access__secret__v1': get_random_string(32, VALID_KEY_CHARS),
                u'created_on__v1': now_es,
            },
            u'created_on__v1': now_es
        }
        if invite_only:
            site_data[u'site__invites__v1'] = {
                u'site__invites__age_days__v1': 2,
                u'site__invites__active__v1': True,
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
        site_data['site__id'] = site_id
        # app
        app_access_token = SocialNetworkResolution.get_app_access_token(settings.XIMPIA_FACEBOOK_APP_ID,
                                                                        settings.XIMPIA_FACEBOOK_APP_SECRET)
        app_data = {
            u'site__v1': site_data,
            u'app__name__v1': app,
            u'app__slug__v1': slugify(app),
            u'app__is_active__v1': True,
            u'app__social__v1': {
                u'app__social__facebook__v1': {
                    u'app__social__facebook__access_token__v1': app_access_token,
                    u"app__social__facebook__app_id__v1": settings.XIMPIA_FACEBOOK_APP_ID,
                    u"app__social__facebook__app_secret__v1": settings.XIMPIA_FACEBOOK_APP_SECRET
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
        app_data_logical['site']['id'] = site_id
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
                u'site__id': site_id,
                u'site__name__v1': site,
                u'site__slug__v1': slugify(site)
            },
            u'app__v1': None,
            u'tag__v1': tag_data,
            u'settings__fields__v1': None,
            u'created_on__v1': now_es
        }
        settings_output = []
        for setting_item in settings_input:
            settings_data.update({
                u'settings__setting_name__v1': setting_item[0],
                u'settings__setting_value__v1': setting_item[1]
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
        # account
        account_data = {
            u'account__organization__v1': {
                u'name__v1': organization_name
            },
            u'account__name__v1': account,
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

        return site_data_logical, app_data_logical, settings_output, account_data_logical

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
                u'permission__name__v1': permission,
                u'permission__apps__v1': [
                    {
                        u'permission__apps__site_slug__v1': slugify(site),
                        u'permission__apps__app_slug__v1': slugify(app)
                    }
                ],
                u'permission__data__v1': None,
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
    def _create_user_groups(cls, index_name, groups, social_data, social_network, app_data, now_es):
        """
        Create Groups, User and User mappings to Groups

        :param index_name:
        :param groups:
        :param social_data:
        :param social_network:
        :param app_data:
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
                u'group__name__v1': group,
                u'group__slug__v1': slugify(group),
                u'group__tags__v1': None,
                u'created_on__v1': now_es,
            }
            if group in permissions:
                group_data[u'group__permissions__v1'] = [
                    {
                        u'group__permissions__name__v1': permissions[group],
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
        logger.debug(u'groups_data : {}'.format(groups_data))
        # user
        seconds_two_months = str(int((datetime.now() + timedelta(days=60) -
                                      datetime(1970, 1, 1)).total_seconds()))
        user_data = {
            u'user__username__v1': " ",
            u'user__alias__v1': "",
            u'user__email__v1': social_data.get('email', None),
            u'user__password__v1': None,
            u'user__avatar__v1': social_data.get('profile_picture', None),
            u'user__user_name__v1': social_data.get('name', None),
            u'user__first_name__v1': social_data.get('first_name', ''),
            u'user__last_name__v1': social_data.get('last_name', ''),
            u'user__social_networks__v1': [
                {
                    u'user__social_networks__network__v1': social_network,
                    u'user__social_networks__user_id__v1': social_data.get('user_id', None),
                    u'user__social_networks__access_token__v1': social_data.get('access_token', None),
                    u'user__social_networks__state__v1': None,
                    u'user__social_networks__scopes__v1': social_data.get('scopes', None),
                    u'user__social_networks__has_auth__v1': True,
                    u'user__social_networks__link__v1': social_data.get('link', None),
                    u'user__social_networks__expires_at__v1': social_data.get('expires_at', None),
                }
            ],
            u'user__permissions__v1': None,
            u'groups__v1': map(lambda x: {
                u'group__id': x['id'],
                u'group__name__v1': x['name']
            }, groups_data),
            u'user__is_active__v1': True,
            u'user__token__v1': None,
            u'user__expires_at__v1': time.strftime(
                '%Y-%m-%dT%H:%M:%S',
                time.gmtime(float(social_data.get('expires_at', seconds_two_months)))),
            u'user__session_id__v1': None,
            u'app__v1': {
                u'app__id': app_data['id'],
                u'app__slug__v1': app_data['slug'],
                u'app__name__v1': app_data['name'],
                u'site__v1': {
                    u'site__id': app_data['site']['id'],
                    u'site__slug__v1': app_data['site']['slug'],
                    u'site__name__v1': app_data['site']['name'],
                }
            },
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
                        u'user__id': user_data_logical[u'id'],
                        u'user__username__v1': user_data_logical[u'username'],
                        u'user__email__v1': user_data_logical[u'email'],
                        u'user__avatar__v1': user_data_logical[u'avatar'],
                        u'user__user_name__v1': user_data_logical[u'user_name'],
                        u'user__social_networks__v1': user_data_logical[u'social_networks'],
                        u'user__permissions__v1': user_data_logical[u'permissions'],
                        u'created_on__v1': user_data_logical[u'created_on'],
                    },
                    u'group__v1': {
                        u'group__id': group_data[u'id'],
                        u'group__name__v1': group_data[u'name'],
                        u'group__slug__v1': group_data[u'slug'],
                        u'group__tags__v1': group_data[u'tags'],
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
        organization_name = 'Ximpia Inc'
        account = 'ximpia'

        index_name = 'ximpia-api__base'
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
        site_data, app_data, settings_data, account_data = site_tuple
        # print 'app_data:', app_data
        refresh_index(index_name)

        # social
        # login access token for user to use
        social_data = SocialNetworkResolution.get_network_user_data(social_network,
                                                                    access_token=access_token,
                                                                    app_id=app_data['id'],
                                                                    social_app_id=settings.XIMPIA_FACEBOOK_APP_ID)

        # 2. Permissions
        permissions_data = self._create_permissions(site, app, index_name, now_es)

        # 3. Groups, User, UserGroup
        user_data, groups_data = self._create_user_groups(index_name, default_groups, social_data,
                                                          social_network, app_data, now_es)

        # refresh_index(index_name)

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
                })
            ))
