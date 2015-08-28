import requests
import json
import logging

from datetime import datetime

from rest_framework import viewsets, generics, response

from django.conf import settings
from django.utils.translation import ugettext as _
from django.utils.text import slugify

from . import SocialNetworkResolution

__author__ = 'jorgealegre'

logger = logging.getLogger(__name__)


class DocumentViewSet(viewsets.ModelViewSet):
    pass


class SetupSite(generics.CreateAPIView):

    reserved_words = {'ximpia_api'}

    def _create_site_index(self, index_name):
        """
        Create index

        :param index_name:
        :return:
        """
        with open('../../settings.json') as f:
            settings_dict = json.loads(f.read())
        es_response_raw = requests.post('{}/{}'.format(settings.ELASTIC_SEARCH_HOST, index_name),
                                        data={
                                            'settings': settings_dict
                                        })
        # {"acknowledged":true}
        if es_response_raw.status_code != 200:
            pass
        es_response = es_response_raw.json()
        if not es_response['acknowledged']:
            pass
        logger.info(u'SetupSite :: created index {} response: {}'.format(
            index_name,
            es_response
        ))

    def _create_site_app(self, index_name, site, app, now_es):
        """
        Create site and app

        :param index_name:
        :param site:
        :param app:
        :param now_es:
        :return:
        """
        # site
        es_response_raw = requests.post(
            '{}/{}/site'.format(settings.ELASTIC_SEARCH_HOST, index_name),
            data={
                u'name': site,
                u'slug': slugify(site),
                u'url': u'http://{site_slug}.ximpia.com/'.format(slugify(site)),
                u'is_active': True,
                u'created_on': now_es
            })
        if es_response_raw.status_code != 200:
            pass
        es_response = es_response_raw.json()
        site_id = es_response.get('_id', '')
        logger.info(u'SetupSite :: created site {} id: {}'.format(
            site,
            site_id
        ))
        # app
        es_response_raw = requests.post(
            '{}/{}/app'.format(settings.ELASTIC_SEARCH_HOST, index_name),
            data={
                u'name': app,
                u'slug': slugify(app),
                u'is_active': True,
                u'created_on': now_es
            })
        if es_response_raw.status_code != 200:
            pass
        es_response = es_response_raw.json()
        app_id = es_response.get('_id', '')
        logger.info(u'SetupSite :: created app {} id: {}'.format(
            app,
            app_id
        ))
        # settings for app and site
        es_response_raw = requests.post(
            '{}/{}/settings'.format(settings.ELASTIC_SEARCH_HOST, index_name),
            data={
                u'site': {
                    u'id': site_id,
                    u'name': site,
                    u'slug': slugify(site)
                },
                u'app': {
                    u'id': app_id,
                    u'name': app,
                    u'slug': slugify(app)
                },
                u'fields': None,
                u'created_on': now_es
            })
        if es_response_raw.status_code != 200:
            pass
        es_response = es_response_raw.json()
        logger.info(u'SetupSite :: created settings id: {}'.format(
            es_response.get('_id', '')
        ))

    def _create_permissions(self, site, app, index_name, now_es):
        """
        Create permission can_admin

        :param app:
        :param index_name:
        :param now_es:
        :return:
        """
        es_response_raw = requests.post(
            '{}/{}/settings'.format(settings.ELASTIC_SEARCH_HOST, index_name),
            data={
                u'name': u'can_admin',
                u'apps': [
                    {
                        u'site': site,
                        u'app': app
                    }
                ],
                u'created_on': now_es
            })
        if es_response_raw.status_code != 200:
            pass
        es_response = es_response_raw.json()
        logger.info(u'SetupSite :: created permission "can_admin" for app: {} id: {}'.format(
            app['name'],
            es_response.get('_id', '')
        ))

    def _create_user_groups(self):
        pass

    def post(self, request, *args, **kwargs):
        data = request.data
        site = data['site']
        app = 'base'
        access_token = data['access_token']
        social_network = data['social_network']
        languages = data.get('languages', ['en'])
        location = data.get('location', 'us')
        default_groups = ['users', 'users-test', 'admin']

        if site in self.reserved_words:
            # maybe raise different error
            # XimpiaAPIException ???
            raise TypeError(_(u'Site name not allowed'))

        # We fetch information from social network with access_token, verify tokens, etc...
        # integrate only for first version Facebook
        # social_data is same for all social networks, a dictionary with data
        social_data = SocialNetworkResolution.get_network_user_data(social_network,
                                                                    access_token=access_token)

        # create index with settings and mappings:
        # site__base
        # ximpia_api__base (these indices need to already be created, we need a management command for it,
        # creating index, settings and also mappings for all system types)

        # site__base index creation
        index_name = '{site}__base'.format(site=site)
        self._create_site_index(index_name)

        now_es = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 1. create site, app and settings
        self._create_site_app(index_name, site, app, now_es)

        # 2. Permissions
        self._create_permissions(site, app, index_name, now_es)

        # 3. Groups, User, UserGroup

        response_ = {
            "site": site,
            "app": app,
            "user": {
                'name': social_data['name'],
                'email': social_data['email'],
                'avatar': social_data['avatar']
            },
            "access_token": access_token,
            "social_network": social_network,
            "languages": languages,
            "location": location,
        }
        return response.Response(response_)
