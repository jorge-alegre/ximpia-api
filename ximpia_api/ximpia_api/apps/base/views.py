import requests
from requests.adapters import HTTPAdapter
import json
import logging
import string

from datetime import datetime

from rest_framework import viewsets, generics, response
from rest_framework.response import Response

from django.conf import settings
from django.utils.translation import ugettext as _
from django.utils.text import slugify
from django.utils.crypto import get_random_string

from . import SocialNetworkResolution
import exceptions

from document import to_physical_doc, to_logical_doc, Document

__author__ = 'jorgealegre'

logger = logging.getLogger(__name__)

VALID_KEY_CHARS = string.ascii_lowercase + string.digits

req_session = requests.Session()
req_session.mount('https://{}'.format(settings.ELASTIC_SEARCH_HOST),
                  HTTPAdapter(max_retries=3))


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
        # base_mappings_path = settings.BASE_DIR + 'apps/base/mappings'
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
                                                'app': app_dict,
                                                'urlconf': urlconf_dict,
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
            raise exceptions.XimpiaAPIException(_(u'Error creating index "{}" {}'.format(
                index_name,
                es_response_raw.content
            )))
        es_response = es_response_raw.json()
        if not es_response['acknowledged']:
            raise exceptions.XimpiaAPIException(_(u'Error creating index "{}"'.format(index_name)))
        logger.info(u'SetupSite :: created index {} response: {}'.format(
            index_name,
            es_response
        ))

    @classmethod
    def _create_site_app(cls, index_ximpia, index_name, site, app, now_es, languages, location,
                         invite_only, tag_data, domains, account, organization_name):
        """
        Create site and app

        :param index_ximpia:
        :param index_name:
        :param site:
        :param app:
        :param now_es:
        :return:
        """
        # site
        # generate api access key
        counter = 0
        api_access_key = get_random_string(32, VALID_KEY_CHARS)
        while Document.objects.filter('site', api_access__api_key=api_access_key):
            api_access_key = get_random_string(32, VALID_KEY_CHARS)
            if counter > 10:
                raise exceptions.XimpiaAPIException(_(
                    u'Maximum number of iterations for generate api key'
                ))
            counter += 1
        site_data = {
            u'name__v1': site,
            u'slug__v1': slugify(site),
            u'url__v1': u'http://{site_slug}.ximpia.io/'.format(slugify(site)),
            u'is_active__v1': True,
            u'domains__v1': map(lambda x: {'domain_name__v1': x}, domains),
            u'api_access__v1': {
                u'api_key__v1': api_access_key,
                u'api_secret__v1': get_random_string(32, VALID_KEY_CHARS),
                u'created_on__v1': now_es,
            },
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
            '{}/{}/site'.format(settings.ELASTIC_SEARCH_HOST, index_ximpia),
            data=json.dumps(site_data))
        if es_response_raw.status_code not in [200, 201]:
            exceptions.XimpiaAPIException(_(u'Could not write site "{}" :: {}'.format(
                site,
                es_response_raw.content
            )))
        es_response = es_response_raw.json()
        site_id = es_response.get('_id', '')
        logger.info(u'SetupSite :: created site {} id: {}'.format(
            site,
            site_id
        ))
        site_data_logical = to_logical_doc('site', site_data)
        site_data_logical['id'] = site_id
        # site_data['id'] = site_id
        # app
        # social app data would be inserted once admin user adds facebook id and secret
        # having pattern to get facebook app access token. Call would be update app with pattern
        # to generate the app access token
        app_data = {
            u'site__v1': site_data_logical,
            u'name__v1': app,
            u'slug__v1': slugify(app),
            u'is_active__v1': True,
            u'social__v1': {
                u'facebook__v1': {
                    u'access_token__v1': None,
                    u"app_id__v1": None,
                    u"app_secret__v1": None,
                }
            },
            u'created_on__v1': now_es
        }
        es_response_raw = requests.post(
            '{}/{}/app'.format(settings.ELASTIC_SEARCH_HOST, index_name),
            data=json.dumps(app_data))
        if es_response_raw.status_code not in [200, 201]:
            exceptions.XimpiaAPIException(_(u'Could not write app "{}" :: {}'.format(
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
                raise exceptions.XimpiaAPIException(_(u'Could not write settings for site "{}" :: {}'.format(
                    site, es_response_raw.content)))
            es_response = es_response_raw.json()
            logger.info(u'SetupSite :: created settings id: {}'.format(
                es_response.get('_id', '')
            ))
            settings_data_logical = to_logical_doc('settings', settings_data)
            settings_output.append(settings_data_logical)

        # account
        account_data = {
            u'organization__v1': {
                u'name__v1': organization_name
            },
            u'account_name__v1': account,
            u'created_on__v1': now_es,
        }
        es_response_raw = requests.post(
            '{}/{}/account'.format(settings.ELASTIC_SEARCH_HOST, settings.SITE_BASE_INDEX),
            data=json.dumps(account_data))
        if es_response_raw.status_code not in [200, 201]:
            raise exceptions.XimpiaAPIException(_(u'Could not write account "{}" :: {}'.format(
                site, es_response_raw.content)))
        es_response = es_response_raw.json()
        logger.info(u'SetupSite :: created account {}'.format(
            account,
        ))
        account_data_logical = to_logical_doc('account', account_data)
        account_data_logical['id'] = es_response.get('_id', '')

        return site_data_logical, app_data_logical, settings_output, account_data_logical

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
            raise exceptions.XimpiaAPIException(_(u'Could not write tag v1 :: {} :: {}'.format(
                es_response_raw.status_code,
                es_response_raw.content)))
        es_response = es_response_raw.json()
        logger.info(u'SetupSite :: created tag "v1" id: {}'.format(
            es_response.get('_id', '')
        ))
        tag_data['id'] = es_response.get('_id', '')
        return to_logical_doc('tag', tag_data)

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
                raise exceptions.XimpiaAPIException(_(u'Could not write permission "can-admin" :: {}'.format(
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
    def _create_groups(cls, groups, now_es, index_name, group_permissions):
        """
        Create site groups taking default site groups

        :param groups:
        :param now_es:
        :param index_name:
        :return:
        """
        # group
        groups_data = []
        groups_data_logical = {}
        for group in groups:
            group_data = {
                u'group_name__v1': group,
                u'slug__v1': slugify(group),
                u'tags__v1': None,
                u'created_on__v1': now_es,
            }
            if group in group_permissions:
                group_data[u'group_permissions__v1'] = [
                    {
                        u'name__v1': group_permissions[group],
                        u'created_on__v1': now_es
                    }
                ]
            es_response_raw = requests.post(
                '{}/{}/group'.format(settings.ELASTIC_SEARCH_HOST, index_name),
                data=json.dumps(group_data))
            if es_response_raw.status_code not in [200, 201]:
                raise exceptions.XimpiaAPIException(_(u'Could not write group "{}" :: {}'.format(
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
        return groups_data

    def post(self, request, *args, **kwargs):
        """
        Create site

        Endpoint:
        https://{site_slug}.ximpia.io/create-site

        :param request:
        :param args:
        :param kwargs:
        :return:
        """
        site = args[0]
        data = request.data
        app = 'base'
        social_access_token = data['access_token']
        social_network = data.get('social_network', 'facebook')
        invite_only = data.get('invite_only', False)
        languages = data.get('languages', ['en'])
        location = data.get('location', 'us')
        domains = data.get('domains', [])
        organization_name = data.get('organization_name', site)
        account = data.get('account', site)

        # Site has normal users, beta users, admin users and staff
        default_groups = [
            u'users',
            u'users-test',
            u'admin',
            u'staff'
        ]

        if filter(lambda x: site.index(x) != -1, list(self.RESERVED_WORDS)):
            raise exceptions.XimpiaAPIException(_(u'Site name not allowed'))

        now_es = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        index_name = '{site}__base'.format(site=site)
        index_ximpia = settings.SITE_BASE_INDEX

        # create index with settings and mappings:
        self._create_site_index(index_name)

        tag_data = self._create_tag(index_name, now_es)

        # 1. create site, app and settings
        site_tuple = self._create_site_app(index_ximpia, index_name, site, app, now_es, languages,
                                           location, invite_only, tag_data, domains, account, organization_name)
        site_data, app_data, settings_data, account_data = site_tuple

        # 2. Permissions
        permissions_data = self._create_permissions(site, app, index_name, now_es)

        # 3. Create site groups
        groups = self._create_groups(default_groups, now_es, index_name,
                                     {
                                         u'admin': u'can-admin',
                                     })

        # 4. User signup
        # We create user at ximpia, so user can connect to ximpia api app to manage account
        user_raw = req_session.post(
            '{scheme}://ximpia.io/user-signup'.format(settings.SCHEME),
            data=json.dumps({
                u'access_token': social_access_token,
                u'social_network': social_network,
                u'groups': groups,
                u'api_key': site_data['api_access']['api_key'],
                u'api_secret': site_data['api_access']['api_secret'],
            })
        )
        if user_raw.status_code not in [200, 201]:
            raise exceptions.XimpiaAPIException(_(u'Error creating user'))
        user = user_raw.json()

        response_ = {
            u'account': account_data,
            u'site': to_logical_doc('site', site_data),
            u'app': to_logical_doc('app', app_data),
            u'settings': to_logical_doc('settings', settings_data),
            u'user': user,
            u'groups': groups,
            u'permissions': permissions_data,
            u'token': user.get('token', {}),
        }
        print response_
        return response.Response(response_)
