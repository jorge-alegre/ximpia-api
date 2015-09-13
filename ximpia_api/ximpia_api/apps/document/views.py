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
from base import get_es_response, get_path_search

__author__ = 'jorgealegre'

logger = logging.getLogger(__name__)

req_session = requests.Session()
req_session.mount('https://{}'.format(settings.SEARCH_HOST),
                  HTTPAdapter(max_retries=3))


class DocumentViewSet(viewsets.ModelViewSet):

    document_type = ''
    app = ''

    @classmethod
    def _filter_doc_fields(cls, tag, user, document):
        """
        Filter document fields based on user permissions for tag

        :param tag:
        :param user:
        :param document:
        :return:
        """
        query = {
            'query': {
                'bool': {
                    'must': [
                        {
                            "term": {
                                "doc_type__v1": cls.document_type
                            }
                        },
                        {
                            "term": {
                                "is_active__v1": True
                            }
                        }
                    ]
                }
            }
        }
        if tag:
            query['query']['bool']['must'].append(
                {
                    'term': {
                        "tag__v1": tag
                    }
                }
            )
            if user:
                query['query']['bool']['should'] = [
                    {
                        'nested': {
                            'path': 'permissions__v1.users__v1',
                            'filter': {
                                {
                                    'term': {
                                        'permissions__v1.users__v1.id': user['id']
                                    }
                                }
                            }
                        }
                    },
                    {
                        'nested': {
                            'path': 'permissions__v1.groups__v1',
                            'filter': {
                                {
                                    'term': {
                                        'permissions__v1.groups__v1.id': u' OR '.join(user['groups'])
                                    }
                                }
                            }
                        }
                    },
                    {
                        'term': {
                            'tag.public': True
                        }
                    }
                ]
        es_response_raw = get_es_response(
            req_session.get(get_path_search('_field_version'),
                            data=json.dumps(query)))
        es_response = es_response_raw.json()
        db_fields = map(lambda x: x['field__v1'], es_response['hits']['hits'])
        document_new = {}
        for key in document:
            if key in db_fields:
                document_new[key] = document[key]
        return document_new

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
        tag = kwargs.get('tag', 'v1')
        # check that user and tag allows this operation
        es_response_raw = req_session.post(
            '{}/{}/_{document_type}'.format(
                settings.ELASTIC_SEARCH_HOST,
                '{site}__{app}'.format(site=settings.SITE, app=self.app),
                document_type=self.document_type),
            data=to_physical_doc(self.document_type, request.data, tag=tag, user=request.user))
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
        # TODO: check that tag and user allows getting content
        tag = kwargs.get('tag', 'v1')
        es_response_raw = req_session.put(
            '{}/{}/_{document_type}/{id}'.format(
                settings.ELASTIC_SEARCH_HOST,
                '{site}__{app}'.format(site=settings.SITE, app=self.app),
                document_type=self.document_type,
                id=id_),
            data=to_physical_doc(self.document_type, request.data, tag=tag, user=request.user))
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

         query can be text or dictionary with key -> value. Depending on value, we map to right ES query

        payload
        {
          "query": "cat",
          "filters": {
            "must": [
            ],
            "should": [
            ]
          },
          "excludes": {
            "user.id": 34
          },
          "sort": [
            "name",
            {
              "post_date": {
                "order": "asc"
              }
            }
          ],
          "group_by": [
              {
              },
              {
              }
          ]
        }

        {
          "query": {
              "fields": ['description']
              "value": "mine"
          },
          "filters": {
            "must": [
            ],
            "should": [
            ]
          }
        }


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
        return Response(es_response['hits']['hits'])

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
        # TODO: check that tag and user allows getting content
        es_response_raw = req_session.get(
            '{}/{}/_{document_type}/{id}'.format(
                settings.ELASTIC_SEARCH_HOST,
                '{site}__{app}'.format(site=settings.SITE, app=self.app),
                document_type=self.document_type,
                id=id_))
        if es_response_raw.status_code != 200:
            exceptions.XimpiaAPIException(_(u'Could not get document'))
        es_response = es_response_raw.json()
        logger.info(u'DocumentViewSet.retrieve :: retrieved document "{document_type}" id_:{id}'.format(
            id=es_response.get('_id', ''),
            document_type=self.document_type
        ))
        document = self._filter_doc_fields(tag, request.user, es_response['_source'])
        return Response(document)

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
        tag = kwargs.get('tag', 'v1')
        # TODO: check that tag and user allows getting content
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
