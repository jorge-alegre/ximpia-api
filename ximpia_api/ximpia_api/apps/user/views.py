import string
import requests
import json
from requests.adapters import HTTPAdapter
import logging
from datetime import datetime

# from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login
from django.utils.crypto import get_random_string
from django.utils.translation import ugettext as _
from django.utils.text import slugify
from django.conf import settings

from rest_framework import viewsets, generics, response
from rest_framework.response import Response

from base.views import DocumentViewSet
from base import exceptions, get_path_by_id, SocialNetworkResolution
from document import to_logical_doc, to_physical_doc

__author__ = 'jorgealegre'

VALID_KEY_CHARS = string.ascii_lowercase + string.digits
MAX_RETRIES = 3

req_session = requests.Session()
req_session.mount('https://{}'.format(settings.SEARCH_HOST),
                  HTTPAdapter(max_retries=MAX_RETRIES))

logger = logging.getLogger(__name__)


"""
Routes
======

We would define this from front, being some map simple to understand.

/contributions/{contribution_slug:slug_type}/

We save this into document_definition as route field

above is the one to be configured, then we can access with:

/contributions/{contribution_slug:slug_type}/create
/contributions/{contribution_slug:slug_type}/update
/contributions/{contribution_slug:slug_type}/list (these would accept Ximpia queries, input, query_name)
/contributions/{contribution_slug:slug_type}/detail

URL Resolutions
===============

1. We create a middleware, which sets request.urlconf with all urls for application and site. Site will be in url, like
{site}.ximpia.com and application would be placed at a header probably XIMPIA-APP:myapp
2. We get all urls for it and paste into urlconf dynamically

We would get all routes related to an app and use that.

For this to work, we need already data in document_definition

We will test with NewRelic, should be fast to satisfy the 50ms requirement for Python processing speed, since data
fetch would be 10 msc. We need testing for this.

How about site and app in url???
https://{site}.ximpia.com/??? for base app, always installed
https://{site}.ximpia.com/{app}/

https://pichit.ximpia.com/v1/missions/my-mission/
https://pichit.ximpia.com/v1/contributions/blue-eye/
https://pichit.ximpia.com/v1/tags/my-tag/ -> app tags with home viewset

The url configs map to site and app when defined in document definition

Common Resolutions
- - - - - - - - - -
user app, etc... would have common urls that we can map in main urls.py. These mappings would be for ximpia base
features:
* users
* document definitions
* query update

But not for app documents for other sites, and these would need app document_definition and generation of ES
mappings.

Indices
=======

ximpia__base: would keep general data for config
{site}__base: General config for site
{site}__{app}: Data for app

"""


# Serializers define the API representation.
"""class UserSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = User
        fields = ('url', 'username', 'email', 'is_staff')"""


class Connect(generics.CreateAPIView):

    def post(self, request, *args, **kwargs):
        try:
            if len(args) != 2:
                raise exceptions.XimpiaAPIException(_(u'access_token and provider are required'))
            access_token, provider = args
            if settings.SITE == 'XimpiaApi':
                if not hasattr(settings, '{}_APP_ID'.format(provider.upper())):
                    app_id = getattr(settings, 'XIMPIA_{}_APP_ID'.format(provider.upper()))
                    app_secret = getattr(settings, 'XIMPIA_{}_APP_SECRET'.format(provider.upper()))
                else:
                    app_id = getattr(settings, '{}_APP_ID'.format(provider.upper()))
                    app_secret = getattr(settings, '{}_APP_SECRET'.format(provider.upper()))
            else:
                app_id = getattr(settings, '{}_APP_ID'.format(provider.upper()))
                app_secret = getattr(settings, '{}_APP_SECRET'.format(provider.upper()))
            auth_data = {
                'access_token': access_token,
                'provider': provider,
                'app_id': app_id,
                'app_secret': app_secret,
            }
            user = authenticate(**auth_data)
            if user:
                login(request, user)
                token = get_random_string(400, VALID_KEY_CHARS)
                es_response_raw = req_session.put(get_path_by_id('_user', user.document.get('_id', '')),
                                                  data=user.document['_source'].update(
                                                      {
                                                          'token': token
                                                      }
                    )
                )
                es_response = json.loads(es_response_raw.content)
                return {
                    'status': 'ok',
                    'action': 'login',
                    'token': es_response['_source']['token']
                }
            else:
                # create user
                # we need to check user exists at provider!!!!!
                response = req_session.get('https://graph.facebook.com/debug_token?'
                                           'input_token={access_token}&'
                                           'access_token={app_token}'.format(
                                               access_token=access_token,
                                               app_token=app_access_token))
                if response.status_code != 200:
                    raise exceptions.XimpiaAPIException(u'Error in validating Facebook response',
                                                        code=exceptions.SOCIAL_NETWORK_AUTH_ERROR)
                fb_data = json.loads(response.content)
                if fb_data['data']['app_id'] != settings.FACEBOOK_APP_ID or not fb_data['data']['is_valid']:
                    raise exceptions.XimpiaAPIException(u'Error in validating Facebook response',
                                                        code=exceptions.SOCIAL_NETWORK_AUTH_ERROR)

                token = get_random_string(400, VALID_KEY_CHARS)
                user_raw = req_session.post(
                    '{scheme}://{site}.ximpia.com/user-signup'.format(settings.SCHEME, settings.SITE),
                    data={
                        'token': token,
                        'access_token': access_token,
                        'social_network': provider
                    }
                )
                if user_raw.status_code != 200:
                    raise exceptions.XimpiaAPIException(_(u'Error creating user'))
                user = json.loads(user_raw.content)['user']
                logger.info(u'Connect :: user: '.format(user))
                return {
                    'status': 'ok',
                    'action': 'create_user',
                    'token': token
                }

        except exceptions.XimpiaAPIException as e:
            # error_code = e.code
            return {
                'status': 'error',
                'message': e.message
            }


class UserSignup(generics.CreateAPIView):

    def create(self, request, *args, **kwargs):
        token = request.data.get('token', get_random_string(400, VALID_KEY_CHARS))
        groups = ['users', 'users-test', 'admin']
        now_es = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        index_name = '{site}__base'.format(site=settings.SITE)
        social_data = SocialNetworkResolution.get_network_user_data(request.data['social_network'],
                                                                    access_token=request.data['access_token'])

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
            es_response_raw = req_session.post(
                '{}/{}/_group'.format(settings.ELASTIC_SEARCH_HOST, index_name),
                data=to_physical_doc('_group', group_data))
            if es_response_raw.status_code != 200:
                exceptions.XimpiaAPIException(_(u'Could not write group "{}"'.format(group)))
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
                    u'network': request.data['social_network'],
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
        es_response_raw = req_session.post(
            '{}/{}/_user'.format(settings.ELASTIC_SEARCH_HOST, index_name),
            data=to_physical_doc('_user', user_data))
        if es_response_raw.status_code != 200:
            exceptions.XimpiaAPIException(_(u'Could not write user "{}.{}"'.format(
                request.data['social_network'],
                social_data.get('user_id', None))))
        es_response = es_response_raw.json()
        logger.info(u'SetupSite :: created user id: {}'.format(
            es_response.get('_id', '')
        ))
        user_data['id'] = es_response.get('_id', '')
        # users groups
        es_response_raw = req_session.post(
            '{}/{}/_user-group'.format(settings.ELASTIC_SEARCH_HOST, index_name),
            data=to_physical_doc('_user-group', {
                u'user': map(lambda x: {
                    u'id': x['id'],
                    u'username': x['username'],
                    u'email': x['email'],
                    u'avatar': x['avatar'],
                    u'name': x['name'],
                    u'social_networks': x['social_networks'],
                    u'permissions': x['permissions'],
                    u'created_on': x['created_on'],
                }, user_data),
                u'group': map(lambda x: {
                    u'id': x['id'],
                    u'name': x['name'],
                    u'slug': x['slug'],
                    u'tags': x['tags'],
                    u'created_on': x['created_on']
                }, groups_data),
                u'created_on': now_es,
            }))
        if es_response_raw.status_code != 200:
            exceptions.XimpiaAPIException(_(u'Could not write user group'))
        es_response = es_response_raw.json()
        logger.info(u'SetupSite :: created user group id: {}'.format(
            es_response.get('_id', '')
        ))
        return Response({
            'user': user_data,
            'groups': groups_data,
        })


class User(DocumentViewSet):

    document_type = '_user'
    app = 'base'


class Group(DocumentViewSet):

    document_type = '_group'
    app = 'base'


class Permission(DocumentViewSet):

    document_type = '_permission'
    app = 'base'
