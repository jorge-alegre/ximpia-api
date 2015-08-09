from rest_framework import viewsets, generics, response

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
        # We fetch information from social network with access_token
        response_ = {
            "site": site,
            "app": app,
            "access_token": access_token,
            "social_network": social_network
        }
        return response.Response(response_)
