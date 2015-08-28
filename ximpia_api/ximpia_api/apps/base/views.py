import requests
import json
import logging

from rest_framework import viewsets, generics, response

from django.conf import settings
from django.utils.translation import ugettext as _

from . import SocialNetworkResolution

__author__ = 'jorgealegre'

logger = logging.getLogger(__name__)


class DocumentViewSet(viewsets.ModelViewSet):
    pass


class SetupSite(generics.CreateAPIView):

    reserved_words = {'ximpia_api'}

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
        with open('../../settings.json') as f:
            settings_dict = json.loads(f.read())
        es_response_raw = requests.post('{es_host}/{index_name}'.format(
            es_host=settings.ELASTIC_SEARCH_HOST),
            index_name=index_name,
            data={
                'settings': settings_dict
            })
        if es_response_raw.status_code != 200:
            pass
        es_response = es_response_raw.json()
        logger.info(u'SetupSite :: created index {} response: {}'.format(
            index_name,
            es_response
        ))

        # 1. Create groups and parametric data (permissions), settings (locale and languages)
        # 2. Create User
        # 3. Link to UserGroup

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
