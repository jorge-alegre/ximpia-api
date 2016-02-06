import string
import requests
import json
from requests.adapters import HTTPAdapter
import logging
from datetime import datetime, timedelta

import time

# from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.utils.crypto import get_random_string
from django.utils.translation import ugettext as _
from django.utils.text import slugify
from django.core.urlresolvers import reverse
from django.conf import settings

from rest_framework import viewsets, generics, response
from rest_framework.response import Response

from document.views import DocumentViewSet
from base import exceptions, get_path_by_id, SocialNetworkResolution, get_path_site, refresh_index, \
    get_site, constants, get_resource
from document import to_logical_doc, to_physical_doc, Document
from xp_user import login, logout

__author__ = 'jorgealegre'

VALID_KEY_CHARS = string.ascii_lowercase + string.digits
MAX_RETRIES = 3

req_session = requests.Session()
req_session.mount('https://{}'.format(settings.ELASTIC_SEARCH_HOST),
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


class Logout(generics.CreateAPIView):

    def post(self, request, *args, **kwargs):
        pass


class Connect(generics.CreateAPIView):

    def post(self, request, *args, **kwargs):
        from base import get_base_app
        # this endpoint is related to site, being app base. We get site from request, host name
        try:
            # get access_token and provider from request parameter, then from data
            data = json.loads(request.body)
            access_token = request.REQUEST.get('access_token', data.get('access_token', None))
            provider = request.REQUEST.get('provider', data.get('provider',
                                                                constants.DEFAULT_PROVIDER))
            logger.info(u'Connect :: access_token: {} provider: {}'.format(
                access_token,
                provider
            ))
            site_slug = get_site(request)
            if isinstance(site_slug, dict):
                site_slug = site_slug['slug']
            logger.info(u'Connect :: site: {}'.format(site_slug))
            app = get_base_app(site_slug)
            # print u'Connect :: app: {}'.format(app)
            logger.info(u'Connect :: app: {}'.format(app))
            if not access_token:
                raise exceptions.XimpiaAPIException(u'access_token required')
            # Check access
            is_validated = False
            if not app['site']['public']:
                # check api key
                if 'api_key' in data:
                    # api_access = Document.objects.get('api_access', id=data['api_key'], get_logical=True)
                    api_secret_db = app['site']['api_access']['secret']
                    logger.debug(u'Connect :: api_secret_db: {}'.format(api_secret_db))
                    if api_secret_db != data.get('api_secret', ''):
                        # display error
                        raise exceptions.XimpiaAPIException(_(
                            u'Secret does not match API access'
                        ))
                    is_validated = True
                    # skip_validate = True
                # check domain
                """if request.META['http_request_domain'] not in map(lambda x: x['domain_name'],
                                                                  app['site']['domains'])\
                        and not skip_validate:
                    raise exceptions.XimpiaAPIException(_(
                        u'API access error'
                    ))"""
            if not is_validated:
                raise exceptions.XimpiaAPIException(u'Access not allowed')
            auth_data = {
                'access_token': access_token,
                'provider': provider,
                'social_app_id': app['social'][provider]['app_id'],
                'social_app_secret': app['social'][provider]['app_secret'],
                'app_id': app['id'],
            }
            user = authenticate(**auth_data)
            if user:
                logger.info(u'Connect :: logging in...')
                login(request, user)
                return Response({
                    'status': 'ok',
                    'action': 'login',
                    'token': user.document['token']['key'],
                    'id': user.id,
                })
            else:
                logger.info(u'Connect :: doing signup...')
                # signup
                groups = Document.objects.filter('group',
                                                 **{
                                                     'group__slug__v1.raw__v1': settings.DEFAULT_GROUPS_NORMAL_USER,
                                                     'get_logical': True
                                                 })
                user_raw = get_resource(
                    request,
                    reverse('signup'),
                    'post',
                    data={
                        u'access_token': access_token,
                        u'social_network': provider,
                        u'groups': groups,
                        u'api_key': app['site']['api_access']['key'],
                        u'api_secret': app['site']['api_access']['secret'],
                        u'site': site_slug
                    }
                )
                try:
                    user = json.loads(user_raw.content)
                    logger.info(u'Connect :: user: {}'.format(user))
                    return Response({
                        'status': 'ok',
                        'action': 'signup',
                        'token': user['token']['key'],
                        'id': user['id'],
                    })
                except ValueError as e:
                    raise exceptions.XimpiaAPIException(e.message)

        except (exceptions.XimpiaAPIException, exceptions.DocumentNotFound) as e:
            import traceback
            # print traceback.print_exc()
            # error_code = e.code
            return Response({
                'status': 'error',
                'message': e.message
            })


class UserSignup(generics.CreateAPIView):

    def create(self, request, *args, **kwargs):
        """
        Create user

        :param request:
        :param args:
        :param kwargs:
        :return:
        """
        # print u'UserSignup...'
        from base import get_base_app
        # print request.body
        data = json.loads(request.body)
        site_slug = get_site(request)
        # print u'UserSignup :: site: {}'.format(site_slug)
        app = get_base_app(site_slug)
        logger.debug(u'UserSignup :: app: {}'.format(app))
        app_ximpia_base = get_base_app(slugify(settings.SITE))
        # print u'UserSignup :: app: {}'.format(app)
        app_id = app['id']
        # print u'UserSignup :: app_id: {}'.format(app_id)
        # Access
        # In future, this logic would be handled by the api access modules, checking rating, etc...
        # Implemented with the document features
        # skip_validate = False
        # check if public, when we don't do API access checks
        is_validated = False
        if not app['site']['public']:
            # check api key
            if 'api_key' in data:
                # api_access = Document.objects.get('api_access', id=data['api_key'], get_logical=True)
                api_secret_db = app['site']['api_access']['secret']
                if api_secret_db != data.get('api_secret', ''):
                    # display error
                    raise exceptions.XimpiaAPIException(_(
                        u'Secret does not match for API access'
                    ))
                # skip_validate = True
                is_validated = True
            # check domain
            """if request.META['http_request_domain'] not in map(lambda x: x['domain_name'],
                                                              app['site']['domains'])\
                    and not skip_validate:
                raise exceptions.XimpiaAPIException(_(
                    u'API access error'
                ))"""
        if not is_validated:
            raise exceptions.XimpiaAPIException(u'Access not allowed')
        now_es = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        index_name = '{site}__base'.format(site=site_slug)
        index_name_ximpia = '{site}__base'.format(site=slugify(settings.SITE))

        if not app['social']['facebook']['app_id'] or not app['social']['facebook']['app_secret']:
            raise exceptions.XimpiaAPIException(_(
                u'Social app data not found. Check "app" document for {}.base'.format(
                    site_slug
                )
            ))
        social_data = SocialNetworkResolution.get_network_user_data(
            data['social_network'],
            access_token=data['access_token'],
            app_id=app['id'],
            social_app_id=app['social']['facebook']['app_id'],
            social_secret=app['social']['facebook']['app_secret'],
            app=app,
        )

        seconds_two_months = str(int((datetime.now() + timedelta(days=60) -
                                      datetime(1970, 1, 1)).total_seconds()))
        # user
        # print u'groups_data: {}'.format(data['groups'])
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
                    u'user__social_networks__network__v1': data.get('social_network', 'facebook'),
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
            }, data['groups']),
            u'user__is_active__v1': True,
            u'user__token__v1': None,
            u'user__expires_at__v1': time.strftime(
                '%Y-%m-%dT%H:%M:%S',
                time.gmtime(float(social_data.get('expires_at', seconds_two_months)))),
            u'user__session_id__v1': None,
            u'app__v1': {
                u'app__id': app['id'],
                u'app__slug__v1': app['slug'],
                u'app__name__v1': app['name'],
                u'site__v1': {
                    u'site__id': app['site']['id'],
                    u'site__slug__v1': app['site']['slug'],
                    u'site__name__v1': app['site']['name'],
                }
            },
            u'user__created_on__v1': now_es,
        }
        es_response_raw = requests.post(
            '{}/{}/user'.format(settings.ELASTIC_SEARCH_HOST, index_name_ximpia),
            data=json.dumps(user_data))
        if es_response_raw.status_code not in [200, 201]:
            raise exceptions.XimpiaAPIException(_(u'Could not write user "{}.{}" :: {}'.format(
                data.get('social_network', 'facebook'),
                social_data.get('user_id', None),
                es_response_raw.content)))
        es_response = es_response_raw.json()
        logger.info(u'UserSignup :: created user id: {}'.format(
            es_response.get('_id', '')
        ))
        user_data_logical = to_logical_doc('user', user_data)
        user_data_logical['id'] = es_response.get('_id', '')
        # users groups
        for group_data in data['groups']:
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
                        u'user__created_on__v1': user_data_logical[u'created_on'],
                    },
                    u'group__v1': {
                        u'group__id': group_data[u'id'],
                        u'group__name__v1': group_data[u'name'],
                        u'group__slug__v1': group_data[u'slug'],
                        u'group__tags__v1': group_data[u'tags'],
                        u'group__created_on__v1': group_data[u'created_on']
                    },
                    u'user-group__created_on__v1': now_es,
                }))
            if es_response_raw.status_code not in [200, 201]:
                raise exceptions.XimpiaAPIException(_(u'Could not write user group :: {}'.format(
                    es_response_raw.content
                )))
            es_response = es_response_raw.json()
            es_response['id'] = es_response.get('_id', '')
            logger.info(u'UserSignup :: created user group id: {}'.format(
                es_response.get('_id', '')
            ))
        refresh_index(index_name)
        refresh_index(index_name_ximpia)
        # authenticate and login user
        auth_data = {
            u'access_token': data['access_token'],
            u'provider': data.get('social_network', 'facebook'),
            u'app_id': app_id,
            u'social_app_id': app['social']['facebook']['app_id'],
            u'social_app_secret': app['social']['facebook']['app_secret'],
        }
        user_obj = authenticate(**auth_data)
        if not user_obj:
            raise exceptions.XimpiaAPIException(u'Error in authenticate')
        # user already has token, logical user
        # print u'SetupSite :: user_obj: {}'.format(user_obj)
        login(request, user_obj)
        return Response(user_obj.document)


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
