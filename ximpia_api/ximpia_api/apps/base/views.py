import requests

from rest_framework import viewsets, generics, response

from . import SocialNetworkResolution

__author__ = 'jorgealegre'


class DocumentViewSet(viewsets.ModelViewSet):
    pass


class SetupSite(generics.CreateAPIView):

    def post(self, request, *args, **kwargs):
        data = request.data
        site = data['site']
        app = 'base'
        access_token = data['access_token']
        social_network = data['social_network']
        languages = data.get('languages', ['en'])
        location = data.get('location', 'us')
        default_groups = ['users', 'users-test', 'admin']
        # We fetch information from social network with access_token, verify tokens, etc...
        # integrate only for first version Facebook
        # social_data is same for all social networks, a dictionary with data
        social_data = SocialNetworkResolution.get_network_user_data(social_network,
                                                                    access_token=access_token)

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
