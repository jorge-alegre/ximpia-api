import requests
from requests.adapters import HTTPAdapter
import json
import logging
from datetime import datetime

from rest_framework import viewsets, generics
from rest_framework.response import Response

from django.conf import settings
from django.utils.translation import ugettext as _

from base import exceptions

from document import to_physical_doc, Document
from base import get_es_response, get_path_search, get_site

__author__ = 'jorgealegre'

logger = logging.getLogger(__name__)

req_session = requests.Session()
req_session.mount('https://{}'.format(settings.ELASTIC_SEARCH_HOST),
                  HTTPAdapter(max_retries=3))


class DocumentViewSet(viewsets.ModelViewSet):

    document_type = ''
    app = ''

    @classmethod
    def _process_settings(cls, request):
        """
        Process settings

        :param request:
        :return:
        """
        from base import get_setting_table_value, get_setting_value
        from . import Document, to_logical_doc
        site_slug = request.META['HTTP_HOST'].split(settings.XIMPIA_DOMAIN)[0]
        # Where do I get app from?
        # When we resolve url, we get app_id
        app_id = getattr(request, 'app_id', -1)
        if app_id == -1:
            raise exceptions.XimpiaAPIException(u'App id not found in context, we can\'t process request')
        db_settings = Document.objects.filter('_settings',
                                              site__slug__raw=site_slug,
                                              app__id=app_id)
        for db_setting_doc in db_settings['hits']['hits']:
            setting_doc = to_logical_doc('_settings', db_setting_doc)
            if setting_doc['fields']:
                setattr(settings,
                        setting_doc['_source']['name'],
                        get_setting_table_value(setting_doc['_source']['fields']))
            else:
                setattr(settings,
                        setting_doc['_source']['name'],
                        get_setting_value(setting_doc['_source']['value']))

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
        self._process_settings(request)
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
        self._process_settings(request)
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
        self._process_settings(request)
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
                data=json.dumps(query_dsl))
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
        self._process_settings(request)
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
        self._process_settings(request)
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


class Completion(generics.RetrieveAPIView):

    def get(self, request, *args, **kwargs):
        """
        Make autocomplete request

        attributes
        - query

        {
            "_shards" : {
              "total" : 5,
              "successful" : 5,
              "failed" : 0
            },
            "document_type-suggest" : [ {
                "text" : "n",
                "offset" : 0,
                "length" : 1,
                "options" : [ {
                    "text" : "New collection",
                    "score" : 13.0,
                    "payload":{"id":34,"slug":"34-new-collection"}
                }, {
                    "text" : "NEW",
                    "score" : 1.0,
                    "payload":{"id":152,"slug":"152-new"}
                }, {
                    "text" : "Nature",
                    "score" : 1.0,
                    "payload":{"id":58,"slug":"58-nature"}
                }, {
                    "text" : "New collection for approval",
                    "score" : 1.0,
                    "payload":{"id":350,"slug":"350-new-collection-for-approval"}
                }, {
                    "text" : "New test",
                    "score" : 1.0,
                    "payload":{"id":337,"slug":"337-new-test"}
                } ]
            } ]
        }

        :param request:
        :param args:
        :param kwargs:
        :return:
        """
        # TODO: Integrate document visibility for user when doing document app
        payload = request.data
        size = payload.get('size', 10)
        index = settings.IMDEX_NAME
        document_types = payload.get('document_types', [])
        query = payload.get('query', '')
        responses = {}
        for document_type in document_types:
            query_suggest = {
                "{}-suggest".format(document_type): {
                    "text": query,
                    "completion": {
                        "field": 'suggest',
                        "size": size,
                        "fuzzy": {
                            "fuzziness": 'AUTO'
                        }
                    }
                }
            }
            es_response = req_session.post(
                'http://{host}:9200/{index}/_suggest'.format(
                    host=settings.ELASTIC_SEARCH_HOST,
                    index=index),
                data=json.dumps(query_suggest)
                )
            if es_response.status_code != 200 or 'status' in es_response and es_response['status'] != 200:
                raise exceptions.XimpiaAPIException(es_response.json())
            es_response = es_response.json()
            responses[document_type] = es_response
        return Response(responses)


class DocumentDefinitionViewSet(viewsets.ModelViewSet):

    def create(self, request, *args, **kwargs):
        """
        Create a document definition. Algorithm done for StringField only

        1. Check user can create document definition: Verify belongs to admin group for site.
        2. Generate document mapping from fields
        3. Create mapping for document type at ES
        4. Build fields list for all field types received in document
        5. Create document document definition with permissions, etc... Output sent document

        Example structure received here:
        {
          _meta: {
            choices: {
              countries: {
                es: "Spain"
              }
            },
            permissions: [
              {
                type: "allow",
                user: {
                  id: "smkskjshj765"
                }
              },
              {
                type: "deny",
                group: {
                  slug: "users"
                }
              }
            ]
          },
          base_code: {
            type: "string",
            ...
          }

        }

        permissions
        -----------
        We have content_permissions at document definition and permission data for column permission and
        document permission.

        - When we create a document item with private permissions (only set of users can access specific content),
        we send permissions data when creating content item, not separate API endpoint.

        :param request:
        :param args:
        :param kwargs:
        :return:
        """
        now_es = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        if len(args) == 0:
            raise exceptions.XimpiaAPIException(_(u'No document type sent'))
        doc_type = args[0]
        # resolve index based on request host for site
        site_slug = get_site(request)
        index = '{}__base'.format(site_slug)
        # validations
        # check user request and user is admin
        if not request.user or (request.user and not request.user.id):
            raise exceptions.XimpiaAPIException(_(u'User needs to be authenticated'))
        user = request.user
        groups = user.document['groups']
        admin_groups = filter(lambda x: x['name'] == 'admin', groups)
        if not admin_groups:
            raise exceptions.XimpiaAPIException(_(u'User needs to be admin'))
        # generate mappings
        document_definition_input = json.loads(request.body)
        if 'tag' not in document_definition_input['_meta'] or document_definition_input['_meta']['tag']:
            raise exceptions.XimpiaAPIException(_(u'Tag is mandatory'))
        if Document.objects.filter('document_definition',
                                   doc_type=doc_type).count() > 0:
            raise exceptions.XimpiaAPIException(_(u'Document definition already exists'))
        # meta_data = document_definition_input['_meta']
        # Check mapping does not exist
        es_response_raw = requests.get(
            '{host}/{index}/_mapping/{doc_type}'.format(
                host=settings.ELASTIC_SEARCH_HOST,
                index=index,
                doc_type=doc_type
            )
        )
        if es_response_raw.status_code in [200, 201]:
            raise exceptions.XimpiaAPIException(_(u'Document definition already exists'))
        # Build data
        doc_mapping = {
            doc_type: {
                'dynamic': 'strict',
                '_timestamp': {
                    "enabled": True
                },
                '_all': {
                    "enabled": False
                },
                "properties": {
                }
            }
        }
        for field_name in document_definition_input.keys():
            if field_name == '_meta':
                continue
            instance_data = document_definition_input[field_name]
            # instantiate field class based on type
            instance = __import__('document.fields')
            field_class = getattr(instance, '{}Field'.format(instance_data['type'].capitalize()))
            instance_data['name'] = field_name
            field_instance = field_class(**instance_data)
            field_mapping = field_instance.make_mapping()
            doc_mapping[doc_type]['properties'].update(field_mapping)
        # Build db document definition
        db_document_definition = {
            'fields': []
        }
        for meta_field in document_definition_input['_meta'].keys():
            db_document_definition[meta_field] = document_definition_input['_meta'][meta_field]
        for field_name in document_definition_input.keys():
            db_field = document_definition_input[field_name]
            db_field['name'] = field_name
            db_document_definition['fields'].append(db_field)
        db_document_definition['created_on'] = now_es
        # TODO: Create field_version with all fields and tag / branch in single call
        # Create document definition document
        es_response_raw = requests.post(
            '{host}/{index}/{doc_type}'.format(
                host=settings.ELASTIC_SEARCH_HOST,
                index=index,
                doc_type=doc_type
            ),
            data=json.dumps(to_physical_doc(doc_type, db_document_definition))
        )
        es_response = es_response_raw.json()
        logger.info(u'DocumentDefinition.create :: response create document definition: {}'.format(es_response))
        # Create mapping
        es_response_raw = requests.put(
            '{host}/{index}/_mapping/{doc_type}'.format(
                host=settings.ELASTIC_SEARCH_HOST,
                index=index,
                doc_type=doc_type
            ),
            data=json.dumps(doc_mapping)
        )
        es_response = es_response_raw.json()
        logger.info(u'DocumentDefinition.create :: response put mapping: {}'.format(es_response))
        return document_definition_input

    def update(self, request, *args, **kwargs):
        pass

    def retrieve(self, request, *args, **kwargs):
        pass

    def list(self, request, *args, **kwargs):
        pass

    def destroy(self, request, *args, **kwargs):
        pass
