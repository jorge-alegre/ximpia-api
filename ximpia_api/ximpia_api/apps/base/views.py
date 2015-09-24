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

from . import SocialNetworkResolution
import exceptions

from document import to_physical_doc, to_logical_doc

__author__ = 'jorgealegre'

logger = logging.getLogger(__name__)

VALID_KEY_CHARS = string.ascii_lowercase + string.digits

req_session = requests.Session()
req_session.mount('https://{}'.format(settings.SEARCH_HOST),
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
        base_mappings_path = settings.BASE_DIR + 'apps/base/mappings'
        user_path = settings.BASE_DIR + 'apps/user/mappings'
        document_path = settings.BASE_DIR + 'apps/document/mappings'

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

        with open('{}/_invite.json'.format(user_path)) as f:
            invite_dict = json.loads(f.read())

        with open('{}/_tag.json'.format(document_path)) as f:
            tag_dict = json.loads(f.read())

        with open('{}/_branch.json'.format(document_path)) as f:
            branch_dict = json.loads(f.read())

        with open('{}/_field_version.json'.format(document_path)) as f:
            field_version_dict = json.loads(f.read())

        es_response_raw = req_session.post('{}/{}'.format(settings.ELASTIC_SEARCH_HOST, index_name),
                                           data={
                                               'settings': settings_dict,
                                               'mappings': {
                                                   '_app': app_dict,
                                                   '_settings': settings__dict,
                                                   '_user': user_dict,
                                                   '_group': group_dict,
                                                   '_user-group': user_group_dict,
                                                   '_permission': permissions_dict,
                                                   '_session': session_dict,
                                                   '_invite': invite_dict,
                                                   '_tag': tag_dict,
                                                   '_branch': branch_dict,
                                                   '_field_version': field_version_dict,
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
    def _create_site_app(cls, index_ximpia, index_name, site, app, now_es, languages, location,
                         invite_only, access_token, tag_data):
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
        site_data = {
            u'name__v1': site,
            u'slug__v1': slugify(site),
            u'url__v1': u'http://{site_slug}.ximpia.io/'.format(slugify(site)),
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
            '{}/{}/site'.format(settings.ELASTIC_SEARCH_HOST, index_ximpia),
            data=site_data)
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
            exceptions.XimpiaAPIException(_(u'Could not write app "{}"'.format(app)))
        es_response = es_response_raw.json()
        app_id = es_response.get('_id', '')
        app_data['id'] = app_id
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
                u'name': setting_item[0],
                u'value': setting_item[1]
            })
            es_response_raw = requests.post(
                '{}/{}/_settings'.format(settings.ELASTIC_SEARCH_HOST, index_name),
                data=db_settings)
            if es_response_raw.status_code != 200:
                exceptions.XimpiaAPIException(_(u'Could not write settings for site "{}"'.format(site)))
            es_response = es_response_raw.json()
            logger.info(u'SetupSite :: created settings id: {}'.format(
                es_response.get('_id', '')
            ))
            settings_output.append(settings_data)

        return site_data, app_data, settings_data

    @classmethod
    def _create_tag(cls, index_name, now_es):
        """
        Create tag v1

        :param index_name:
        :param now_es:
        :return:
        """
        tag_data = {
            u'name__v1': u'v1',
            u'slug__v1': u'v1',
            u'is_active__v1': True,
            u'permissions__v1': None,
            u'public__v1': True,
            u'created_on__v1': now_es,
        }
        es_response_raw = requests.post(
            '{}/{}/_tag'.format(settings.ELASTIC_SEARCH_HOST, index_name),
            data=json.dumps(tag_data))
        if es_response_raw.status_code != 200:
            exceptions.XimpiaAPIException(_(u'Could not write tag v1'))
        es_response = es_response_raw.json()
        logger.info(u'SetupSite :: created tag "v1" id: {}'.format(
            es_response.get('_id', '')
        ))
        return tag_data

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
                exceptions.XimpiaAPIException(_(u'Could not write permission "can-admin"'))
            es_response = es_response_raw.json()
            logger.info(u'SetupSite :: created permission "can_admin" for app: {} id: {}'.format(
                app['name'],
                es_response.get('_id', '')
            ))
            output_permissions.append(db_permission)
        return output_permissions

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
            '{scheme}://{site}.ximpia.io/user-signup'.format(settings.SCHEME, settings.SITE),
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
