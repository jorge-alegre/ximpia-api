import requests
from requests.adapters import HTTPAdapter
import json
import logging
import string

from django.conf import settings

from document import Document

__author__ = 'jorgealegre'


class XimpiaSettingsMiddleware(object):

    def process_request(self, request):
        db_settings = Document.objects.filter('_settings',
                                              site__id='',
                                              app__id='')
