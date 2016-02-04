import requests
from requests.adapters import HTTPAdapter
import json
import logging
from datetime import datetime
import pprint

from rest_framework import viewsets, generics
from rest_framework.response import Response

from django.conf import settings
from django.utils.translation import ugettext as _
from django.utils.text import slugify

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
            req_session.get(get_path_search('field-version'),
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


class DocumentDefinition(viewsets.ModelViewSet):

    @classmethod
    def _generate_input_document(cls, input_document_request, doc_type):
        """
        Generate internal definition document for ES, same structure as mappings

        :param input_document_request:
        :param doc_type:
        :return:
        """
        input_document = dict()
        input_document['_meta'] = {}
        for doc_field in input_document_request['_meta']:
            if doc_field == 'choices':
                input_document['_meta']['choices'] = []
                for choice_name in input_document_request['_meta']['choices']:
                    request_list = input_document_request['_meta']['choices'][choice_name]
                    choice_list = []
                    for choice_items in request_list:
                        choice_list.append(
                            {
                                'name': choice_items[0],
                                'value': choice_items[1]
                            }
                        )
                    input_document['_meta']['choices'].append(
                        {
                            'choice_name': choice_list
                        }
                    )
            elif doc_field == 'messages':
                input_document['_meta']['messages'] = []
                for message_name in input_document_request['_meta']['messages']:
                    input_document['_meta']['messages'].append(
                        {
                            'name': message_name,
                            'value': input_document_request['_meta']['messages'][message_name]
                        }
                    )
            elif doc_field == 'tag':
                tag_name = input_document_request['_meta']['tag']
                tag = Document.objects.filter('tag',
                                              **{
                                                  'tag__slug__v1.raw__v1': tag_name
                                              })[0]
                input_document['_meta']['tag'] = tag['_source']
                input_document['_meta']['tag']['tag__id'] = tag['_id']
            elif doc_field == 'branch':
                branch_name = input_document_request['_meta']['branch']
                branch = Document.objects.filter('branch',
                                                 **{
                                                     'branch__slug__v1.raw__v1': branch_name
                                                 })[0]
                input_document['_meta']['branch'] = branch['_source']
                input_document['_meta']['branch']['branch__id'] = branch['_id']
            elif doc_field == 'validations':
                # We need to generate from pattern class
                # So far, exists, not-exists have same structure
                input_document['_meta']['validations'] = []
                for validation_data in input_document_request['_meta']['validations']:
                        input_document['_meta']['validations'].append(
                            validation_data
                        )
            else:
                input_document['_meta'][doc_field] = input_document_request['_meta'][doc_field]
        for field in input_document_request:
            if field != '_meta':
                # we check validations. Only support is-unique, exists and not-exists
                field_data = input_document_request[field]
                if 'validations' in field_data and filter(lambda x: x['type'] == 'is-unique',
                                                          field_data['validations']):
                    validations_new = []
                    for validation_data in field_data['validations']:
                        if validation_data['type'] == 'is-unique':
                            validation_data_item = {
                                'type': 'not-exists',
                                'path': '{doc_type}.{field}'.format(
                                    doc_type=doc_type,
                                    field=field
                                ),
                                'value': 'self'
                            }
                            validations_new.append(validation_data_item)
                    field_data['validations'] = validations_new
                input_document[field] = field_data
        return input_document

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
            tag: 'v1',                  # Optional, v1 is nothing sent
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
        print
        print
        print
        logger.debug(u'DocumentDefinition.create ...')
        logger.debug(u'DocumentDefinition.create :: REQUEST: {}'.format(request.REQUEST))
        now_es = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        if len(kwargs) == 0:
            raise exceptions.XimpiaAPIException(_(u'No document type sent'))
        doc_type = kwargs['doc_type']
        logger.debug(u'DocumentDefinition.create :: doc_type: {}'.format(doc_type))
        # resolve index based on request host for site
        site_slug = get_site(request)
        index = '{}__base'.format(site_slug)
        logger.debug(u'DocumentDefinition.create :: index: {}'.format(index))
        ###############
        # validations
        ###############
        # check user request and user is admin
        if not request.user or (request.user and not request.user.id):
            raise exceptions.XimpiaAPIException(_(u'User needs to be authenticated'))
        user = request.user
        logger.debug(u'DocumentDefinition.create :: request.user: {}'.format(user))
        groups = user.document['groups']
        logger.debug(u'DocumentDefinition.create :: groups: {}'.format(groups))
        admin_groups = filter(lambda x: x['name'] == 'admin', groups)
        if not admin_groups:
            raise exceptions.XimpiaAPIException(_(u'User needs to be admin'))
        # generate mappings
        document_definition_input = self._generate_input_document(
            json.loads(request.body), doc_type
        )
        logger.info(u'DocumentDefinition.create :: document_definition_input: {}'.format(
            pprint.PrettyPrinter(indent=4).pformat(document_definition_input)))
        if 'tag' not in document_definition_input['_meta'] or document_definition_input['_meta']['tag']:
            tag = settings.DEFAULT_VERSION
        else:
            tag = document_definition_input['_meta']['tag']
        bulk_queries = list()
        # Check db validations: tag exists, document definition not exists, no fields
        bulk_queries.append(
            (json.dumps(
                {
                    'index': index,
                    'type': 'document-definition'
                }
            ), json.dumps(
                {
                    'query': {
                        'match_all': {}
                    },
                    'filter': {
                        'term': {
                            'document-definition__doc_type__v1.raw__v1': doc_type
                        }
                    }
                }
            )
            )
        )
        # meta_data = document_definition_input['_meta']
        # Check mapping does not exist
        es_response_raw = requests.get(
            '{host}/{index}/_mapping/{doc_type}'.format(
                host=settings.ELASTIC_SEARCH_HOST,
                index=index,
                doc_type=doc_type
            )
        )
        existing_mapping = es_response_raw.json()
        if existing_mapping:
            raise exceptions.XimpiaAPIException(_(u'Document definition already exists :: {}'.format(
                existing_mapping
            )))
        # Check no fields for doc type
        logger.debug(u'DocumentDefinition.create :: mapping in ES: {}'.format(es_response_raw.content))

        bulk_queries.append(
            (json.dumps(
                {
                    'index': index,
                    'type': 'field-version'
                }
            ), json.dumps(
                {
                    'query': {
                        'match_all': {}
                    },
                    'filter': {
                        'term': {
                            'field-version__doc_type__v1.raw__v1': doc_type
                        }
                    }
                }
            )
            )
        )
        # Validate tag exists
        bulk_queries.append(
            (json.dumps(
                {
                    'index': index,
                    'type': 'tag'
                }
            ), json.dumps(
                {
                    'query': {
                        'match_all': {}
                    },
                    'filter': {
                        'term': {
                            'tag__slug__v1.raw__v1': slugify(tag)
                        }
                    }
                }
            )
            )
        )
        print ''.join(map(lambda x: '{}\n'.format(x[0]) + '{}\n'.format(x[1]), bulk_queries))
        es_response_raw = requests.get(
            '{host}/_msearch'.format(
                host=settings.ELASTIC_SEARCH_HOST
            ),
            data=''.join(map(lambda x: '{}\n'.format(x[0]) + '{}\n'.format(x[1]), bulk_queries))
        )
        es_response = es_response_raw.json()
        logger.info(u'DocumentDefinition.create :: response validations: {}'.format(
            es_response
        ))
        responses = es_response.get('responses', [])
        if responses[0]['hits']['total'] > 0:
            raise exceptions.XimpiaAPIException(_(u'Document definition already exists'))
        if responses[1]['hits']['total'] > 0:
            raise exceptions.XimpiaAPIException(_(u'Document definition already exists'))
        if responses[2]['hits']['total'] == 0:
            raise exceptions.XimpiaAPIException(_(u'Tag does not exist'))
        ##################
        # End validations
        ##################
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
        db_document_definition['created_by'] = {
            'id': user.id,
            'user_name': user.username
        }
        # Build data
        doc_mapping = {
            doc_type: {
                'dynamic': 'strict',
                '_timestamp': {
                    "enabled": True
                },
                "properties": {
                }
            }
        }
        fields_version_str = ''
        for field_name in document_definition_input.keys():
            if field_name == '_meta':
                continue

            instance_data = document_definition_input[field_name]
            module = 'document.fields'
            instance = __import__(module)
            for comp in module.split('.')[1:]:
                instance = getattr(instance, comp)
            logger.debug(u'DocumentDefinition.create :: instance: {} {}'.format(instance,
                                                                                dir(instance)))
            field_class = getattr(instance, '{}Field'.format(instance_data['type'].capitalize()))
            logger.debug(u'DocumentDefinition.create :: field_class: {}'.format(field_class))
            instance_data['name'] = field_name
            instance_data['doc_type'] = doc_type
            field_instance = field_class(**instance_data)
            field_items = field_instance.get_field_items()
            field_mapping = field_instance.make_mapping()
            doc_mapping[doc_type]['properties'].update(field_mapping)
            bulk_header = '{ "create": { "_index": "' + index + '", "_type": "field-version"} }\n'
            # Note: field__v1 would need to be generated by fields, since changes for links, string fields, etc...
            bulk_data = json.dumps(
                {
                    'field-version__doc_type__v1': doc_type,
                    'field-version__field__v1': field_items['field'],
                    'field-version__field_name__v1': field_items['field_name'],
                    'field-version__version__v1': 'v1',
                    'tag__v1': db_document_definition['tag'],
                    'branch__v1': db_document_definition.get('branch', None),
                    'field-version__is_active__v1': True,
                    'field-version__created_on__v1': now_es,
                    'field-version__created_by__v1': {
                        'field-version__created_by__id': user.id,
                        'field-version__created_by__user_name__v1': user.username
                    }
                }
            ) + '\n'
            if not fields_version_str:
                fields_version_str = bulk_header
                fields_version_str += bulk_data
            else:
                fields_version_str += bulk_header
                fields_version_str += bulk_data
        # Create document definition document
        es_response_raw = requests.post(
            '{host}/{index}/{doc_type}'.format(
                host=settings.ELASTIC_SEARCH_HOST,
                index=index,
                doc_type=doc_type
            ),
            data=json.dumps(
                to_physical_doc(
                    doc_type, db_document_definition
                )
            )
        )
        es_response = es_response_raw.json()
        logger.info(u'DocumentDefinition.create :: response create document definition: {}'.format(
            es_response
        ))
        if 'errors' in es_response and es_response['errors']:
            raise exceptions.XimpiaAPIException(u'Error creating document definition')
        # Bulk insert for all fields
        print fields_version_str
        es_response_raw = requests.post(
            '{host}/_bulk'.format(host=settings.ELASTIC_SEARCH_HOST),
            data=fields_version_str,
            headers={'Content-Type': 'application/octet-stream'},
        )
        es_response = es_response_raw.json()
        logger.info(u'DocumentDefinition.create :: response create field versions: {}'.format(
            es_response
        ))
        if 'errors' in es_response and es_response['errors']:
            raise exceptions.XimpiaAPIException(u'Error creating fields')
        # Create mapping
        logger.debug(u'DocumentDefinition.create :: mappings: {}'.format(
            pprint.PrettyPrinter(indent=4).pformat(doc_mapping)
        ))
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
        if 'error' in es_response and es_response['error']:
            raise exceptions.XimpiaAPIException(u'Error in saving mappings')
        return Response(document_definition_input)

    def update(self, request, *args, **kwargs):
        pass

    def retrieve(self, request, *args, **kwargs):
        pass

    def list(self, request, *args, **kwargs):
        pass

    def destroy(self, request, *args, **kwargs):
        pass
