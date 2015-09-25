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

from document.views import DocumentViewSet
from base import exceptions, get_path_by_id, SocialNetworkResolution, get_path_site
from document import to_logical_doc, to_physical_doc, Document

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
{site}.ximpia.io and application would be placed at a header probably XIMPIA-APP:myapp
2. We get all urls for it and paste into urlconf dynamically

We would get all routes related to an app and use that.

For this to work, we need already data in document_definition

We will test with NewRelic, should be fast to satisfy the 50ms requirement for Python processing speed, since data
fetch would be 10 msc. We need testing for this.

How about site and app in url???
https://{site}.ximpia.io/??? for base app, always installed
https://{site}.ximpia.io/{app}/

https://pichit.ximpia.io/v1/missions/my-mission/
https://pichit.ximpia.io/v1/contributions/blue-eye/
https://pichit.ximpia.io/v1/tags/my-tag/ -> app tags with home viewset

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
                # invite checking if active at site
                site = Document.objects.get('site',
                                            id=settings.SITE_ID,
                                            es_path=get_path_site(settings.SITE_ID))
                if site['_source']['invites'] and site['_source']['invites']['active'] and \
                        'invite_id' not in request.REQUEST:
                    raise exceptions.XimpiaAPIException(_(u'Site requests an invite'))
                invite = None
                if site['_source']['invites'] and site['_source']['invites']['active']:
                    invite = Document.objects.get('_invite', id=request.REQUEST.get('invite_id', ''))
                # create user
                # we need to check user exists at provider!!!!!
                response_provider = req_session.get('https://graph.facebook.com/debug_token?'
                                                    'input_token={access_token}&'
                                                    'access_token={app_token}'.format(
                                                        access_token=access_token,
                                                        app_token=SocialNetworkResolution.get_app_access_token(
                                                            app_id, app_secret
                                                        )))
                if response_provider.status_code != 200:
                    raise exceptions.XimpiaAPIException(u'Error in validating Facebook response',
                                                        code=exceptions.SOCIAL_NETWORK_AUTH_ERROR)
                fb_data = json.loads(response_provider.content)
                if not fb_data['data']['is_valid']:
                    raise exceptions.XimpiaAPIException(u'Error in validating Facebook response',
                                                        code=exceptions.SOCIAL_NETWORK_AUTH_ERROR)

                token = get_random_string(400, VALID_KEY_CHARS)
                user_raw = req_session.post(
                    '{scheme}://{site}.ximpia.io/user-signup'.format(settings.SCHEME, settings.SITE),
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
                # link invite with user
                if site['_source']['invites'] and site['_source']['invites']['active']:
                    invite['_source']['user__v1'] = {
                        'id__v1': user['_id'],
                        'name__v1': user['_source']['name']
                    }
                    invite['_source']['consumed_on__v1'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    Document.objects.update('_invite', invite['_id'], invite['_source'])
                return {
                    'status': 'ok',
                    'action': 'create_user',
                    'token': token
                }

        except (exceptions.XimpiaAPIException, exceptions.DocumentNotFound) as e:
            # error_code = e.code
            return {
                'status': 'error',
                'message': e.message
            }


class UserSignup(generics.CreateAPIView):

    def create(self, request, *args, **kwargs):
        """
        Create user

        :param request:
        :param args:
        :param kwargs:
        :return:
        """
        token = request.data.get('token', get_random_string(400, VALID_KEY_CHARS))
        now_es = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        index_name = '{site}__base'.format(site=settings.SITE)
        data = request.data
        social_data = SocialNetworkResolution.get_network_user_data(data['social_network'],
                                                                    access_token=data['access_token'])

        # user
        # generate session
        session_id = get_random_string(50, VALID_KEY_CHARS)
        user_data = {
            u'email__v1': social_data.get('email', None),
            u'password__v1': None,
            u'avatar__v1': social_data.get('profile_picture', None),
            u'name__v1': social_data.get('name', None),
            u'social_networks__v1': [
                {
                    u'network__v1': request.data['social_network'],
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
                u'id__v1': x['_id'],
                u'name__v1': x['_source']['name']
            }, data['groups_data']),
            u'is_active__v1': True,
            u'token__v1': token,
            u'last_login__v1': now_es,
            u'session_id__v1': session_id,
            u'created_on__v1': now_es,
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
                u'user__v1': map(lambda x: {
                    u'id__v1': x['id'],
                    u'username__v1': x['username'],
                    u'email__v1': x['email'],
                    u'avatar__v1': x['avatar'],
                    u'name__v1': x['name'],
                    u'social_networks__v1': x['social_networks'],
                    u'permissions__v1': x['permissions'],
                    u'created_on__v1': x['created_on'],
                }, user_data),
                u'group__v1': map(lambda x: {
                    u'id__v1': x['_id'],
                    u'name__v1': x['_source']['name'],
                    u'slug__v1': x['_source']['slug'],
                    u'tags__v1': x['_source']['tags'],
                    u'created_on__v1': x['_source']['created_on']
                }, data['groups_data']),
                u'created_on__v1': now_es,
            }))
        if es_response_raw.status_code != 200:
            exceptions.XimpiaAPIException(_(u'Could not write user group'))
        es_response = es_response_raw.json()
        logger.info(u'SetupSite :: created user group id: {}'.format(
            es_response.get('_id', '')
        ))
        return Response(user_data)


class User(DocumentViewSet):

    document_type = '_user'
    app = 'base'


class Group(DocumentViewSet):

    document_type = '_group'
    app = 'base'


class Permission(DocumentViewSet):

    document_type = '_permission'
    app = 'base'


class Invite(DocumentViewSet):

    document_type = '_invite'
    app = 'base'
