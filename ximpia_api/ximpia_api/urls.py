"""ximpia URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.8/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Add an import:  from blog import urls as blog_urls
    2. Add a URL to urlpatterns:  url(r'^blog/', include(blog_urls))
"""

from django.conf.urls import url, include
# from django.contrib import admin
from rest_framework import routers

# from ximpia_api.ximpia_api.apps.xp_user.views import User
from base.views import SetupSite
from xp_user.views import UserSignup, Connect, User
from document.views import DocumentDefinition

router = routers.DefaultRouter(trailing_slash=False)
router.register(r'users', User, base_name='user')
router.register(r'document-definition/(?P<doc_type>[-\w]+)', DocumentDefinition, base_name='document-definition')

urlpatterns = [
    # url(r'^admin/', include(admin.site.urls)),
    url(r'^', include(router.urls)),
    # url(r'^api-auth/', include('rest_framework.urls', namespace='rest_framework'))
    url(r'^v1/user-signup$', UserSignup.as_view(), name='signup'),
    url(r'^v1/create-site$', SetupSite.as_view(), name='create_site'),
    url(r'^v1/connect$', Connect.as_view(), name='connect'),
]

"""
    url(r'^v1/document-definition/(?P<doc_type>[-\w]+)$', DocumentDefinition.as_view(
        {
            'post': 'create'
        }
    ), name='document-definition'),
"""
