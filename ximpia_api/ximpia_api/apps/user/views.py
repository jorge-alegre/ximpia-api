from rest_framework import routers, serializers, viewsets
# from django.contrib.auth.models import User

__author__ = 'jorgealegre'

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


# ViewSets define the view behavior.
class UserViewSet(viewsets.ModelViewSet):
    pass
