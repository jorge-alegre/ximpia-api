import requests
from requests.adapters import HTTPAdapter
import json
import logging
import string

from datetime import datetime

from rest_framework import viewsets
from rest_framework.response import Response

from django.conf import settings
from django.utils.translation import ugettext as _

from base import exceptions

from document import to_physical_doc, to_logical_doc

__author__ = 'jorgealegre'

logger = logging.getLogger(__name__)

req_session = requests.Session()
req_session.mount('https://{}'.format(settings.SEARCH_HOST),
                  HTTPAdapter(max_retries=3))


class DocumentViewSet(viewsets.ModelViewSet):

    document_type = ''
    app = ''

    def create(self, request, *args, **kwargs):
        """
        Create document

        Class attributes:
        - document_type
        - app

        :param request:
        :param args:
        :param kwargs:
        :return:
        """
        es_response_raw = req_session.post(
            '{}/{}/_{document_type}'.format(
                settings.ELASTIC_SEARCH_HOST,
                '{site}__{app}'.format(site=settings.SITE, app=self.app),
                document_type=self.document_type),
            data=to_physical_doc(self.document_type, request.data))
        if es_response_raw.status_code != 200:
            exceptions.XimpiaAPIException(_(u'Could not save "{doc_type}"'.format(
                doc_type=self.document_type)))
        es_response = es_response_raw.json()
        logger.info(u'DocumentViewSet.create :: created document "{document_type}" id_:{id}'.format(
            id=es_response.get('_id', ''),
            document_type=self.document_type
        ))
        return Response(es_response)

    def update(self, request, *args, **kwargs):
        """
        Update document

        :param request:
        :param args:
        :param kwargs:
        :return:
        """
        id_ = args[0]
        es_response_raw = req_session.put(
            '{}/{}/_{document_type}/{id}'.format(
                settings.ELASTIC_SEARCH_HOST,
                '{site}__{app}'.format(site=settings.SITE, app=self.app),
                document_type=self.document_type,
                id=id_),
            data=to_physical_doc(self.document_type, request.data))
        if es_response_raw.status_code != 200:
            exceptions.XimpiaAPIException(_(u'Could not update document'))
        es_response = es_response_raw.json()
        logger.info(u'DocumentViewSet.update :: updated document "{document_type}" id_:{id}'.format(
            id=es_response.get('_id', ''),
            document_type=self.document_type
        ))
        return Response(es_response)

    def list(self, request, *args, **kwargs):
        """
        Get list of documents and searches

        request attributes:
        * page (optional)
        * per_page (optional)
        * order_by (optional)

        payload would have filters, data, etc... just key: value in payload, attributes to be pasted into query

        We would have default collection for document, no need to define query_name, default query with
        order by default


        :param request:
        :param args:
        :param kwargs:
        :return:
        """
        query_name = None
        if len(args) == 1:
            query_name = args[0]
            # get query DSL from query container
            query_dsl = {}
            es_response_raw = req_session.get(
                '{}/{}/_{document_type}/_search'.format(
                    settings.ELASTIC_SEARCH_HOST,
                    '{site}__{app}'.format(site=settings.SITE, app=self.app),
                    document_type=self.document_type),
                data=query_dsl)
        else:
            es_response_raw = req_session.get(
                '{}/{}/_{document_type}/_search'.format(
                    settings.ELASTIC_SEARCH_HOST,
                    '{site}__{app}'.format(site=settings.SITE, app=self.app),
                    document_type=self.document_type))
        if es_response_raw.status_code != 200:
            exceptions.XimpiaAPIException(_(u'Could not search collection'))
        es_response = es_response_raw.json()
        logger.info(u'DocumentViewSet.list :: Performed search "{query_name}" '
                    u'for document {document_type}'.format(
                        query_name=query_name,
                        document_type=self.document_type))
        # make output of logical documents from physical ones
        return Response({})

    def retrieve(self, request, *args, **kwargs):
        """
        Get document

        :param request:
        :param args:
        :param kwargs:
        :return:
        """
        id_ = args[0]
        tag = kwargs.get('tag', 'v1')
        es_response_raw = req_session.get(
            '{}/{}/_{document_type}/{id}'.format(
                settings.ELASTIC_SEARCH_HOST,
                '{site}__{app}'.format(site=settings.SITE, app=self.app),
                document_type=self.document_type,
                id=id_),
            data=to_physical_doc(self.document_type, request.data, tag=tag, user=request.user))
        if es_response_raw.status_code != 200:
            exceptions.XimpiaAPIException(_(u'Could not get document'))
        es_response = es_response_raw.json()
        logger.info(u'DocumentViewSet.retrieve :: retrieved document "{document_type}" id_:{id}'.format(
            id=es_response.get('_id', ''),
            document_type=self.document_type
        ))
        return Response(es_response)

    def destroy(self, request, *args, **kwargs):
        """
        Delete document

        TODO
        ====
        What to do with places embedded?
        cascade options

        :param request:
        :param args:
        :param kwargs:
        :return:
        """
        id_ = args[0]
        es_response_raw = req_session.delete(
            '{}/{}/_{document_type}/{id}'.format(
                settings.ELASTIC_SEARCH_HOST,
                '{site}__{app}'.format(site=settings.SITE, app=self.app),
                document_type=self.document_type,
                id=id_))
        if es_response_raw.status_code != 200:
            exceptions.XimpiaAPIException(_(u'Could not delete document'))
        es_response = es_response_raw.json()
        logger.info(u'DocumentViewSet.destroy :: deleted document "{document_type}" id_:{id}'.format(
            id=es_response.get('_id', ''),
            document_type=self.document_type
        ))
        return Response(es_response)
