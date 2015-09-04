import string
import requests
import json
from requests.adapters import HTTPAdapter
import logging

# from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login
from django.utils.crypto import get_random_string
from django.utils.translation import ugettext as _
from django.conf import settings

from rest_framework import viewsets, generics, response

from base.views import DocumentViewSet
from base import exceptions, get_path_by_id

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

            user = authenticate(access_token=access_token, provider=provider)
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
                token = get_random_string(400, VALID_KEY_CHARS)
                user_raw = req_session.post(
                    '{scheme}://{site}.ximpia.com/user'.format(settings.SCHEME, settings.SITE),
                    data={
                        'token': token,
                        'access_token': access_token,
                        'provider': provider
                    }
                )
                if user_raw.status_code != 200:
                    raise exceptions.XimpiaAPIException(_(u'Error creating user'))
                user = json.loads(user_raw.content)
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


class User(DocumentViewSet):
    """
    This class will create user, update user, get user and list users. Would also search for users with Ximpia
    query.

    We need to implement all methods, create, list, retrieve, etc...

    We would have common DocumentViewSet, which is the one that interacts with ElasticSearch needs
    """
    pass


class Group(DocumentViewSet):
    pass


class Permission(DocumentViewSet):
    pass
