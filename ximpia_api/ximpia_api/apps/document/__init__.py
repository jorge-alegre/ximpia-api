import requests
import json
import datetime
import logging
from requests.adapters import HTTPAdapter

from django.utils.translation import ugettext as _
from django.conf import settings

from base import exceptions, get_es_response, get_path_search

__author__ = 'jorgealegre'

MAX_RETRIES = 3

req_session = requests.Session()
req_session.mount('https://{}'.format(settings.ELASTIC_SEARCH_HOST),
                  HTTPAdapter(max_retries=MAX_RETRIES))

logger = logging.getLogger(__name__)


def walk(node, **kwargs):
    """
    Walk through dictionary

    field1__v1
    field1__v2

    In this case, I should get field1 as key and field1__v2 as value

    :param node:
    :param is_logical:
    :param is_physical:
    :param version:
    :return:
    """
    data = {}
    versions_map = {}
    is_physical = kwargs.get('is_physical', False)
    is_logical = kwargs.get('is_logical', False)
    fields_version = kwargs.get('fields_version', [])
    fields_data = kwargs.get('fields_data', [])
    tag = kwargs.get('tag', None)
    if is_physical is False and is_logical is False:
        raise exceptions.XimpiaAPIException(u'Need physical or logical filter')
    if is_physical:
        for key, item in node.items():
            # key might have version, or key should strip version
            if key.find('__') == -1:
                continue
            # field, version_str = key.split('__')
            field_items = key.split('__')
            if field_items[-1] == 'id':
                continue
            version_str = field_items[-1]
            field = field_items[-2]
            version_int = int(version_str[1:])
            versions_map.setdefault(field, {})
            versions_map[field][version_int] = item
    # print versions_map
    if is_physical:
        for field in versions_map:
            # print field
            if not fields_version:
                target_version = max(versions_map[field].keys())
            else:
                target_version = int(filter(lambda x: x.split('__')[-2] == field,
                                            fields_version)[0].split('__')[-1][1:])
            # print 'target_version: {}'.format(target_version)
            item = versions_map[field][target_version]
            if isinstance(item, dict):
                data[field] = walk(item, **kwargs)
            elif isinstance(item, (list, tuple)) and isinstance(item[0], dict):
                data[field] = map(lambda x: walk(x, **kwargs), item)
            else:
                data[field] = item
    elif is_logical:
        for key, item in node.items():
            # key like 'status', item like 'ok', ['ok', 'right'], 67 or { field: value }, etc...
            if fields_data:
                if tag:
                    # like status__v7
                    field = map(lambda x: x,
                                filter(lambda y: y['field-version__field__v1'] == key, fields_data))[0]
                else:
                    fields = map(lambda x: x['field-version__field__v1'], fields_data)
                    # field: {version}
                    versions_map = map(lambda x: (x['field-version__field__v1'].split('__')[0],
                                                  {x['field-version__field__v1'].split('__')[1]}),
                                       fields_data)
                    # like status__v7
                    field = map(lambda y: max(list(versions_map[y.split('__')[0]])),
                                filter(lambda x: x.split('__')[0] == key, fields))
            else:
                field = u'{key}__v1'.format(key=key)
            if isinstance(item, dict):
                data[field] = walk(item, **kwargs)
            elif isinstance(item, (list, tuple)) and isinstance(item[0], dict):
                data[field] = map(lambda x: walk(x, **kwargs), item)
            else:
                data[field] = item
    return data


def to_logical_doc(doc_type, document, tag=None, user=None):
    """
    Physical documents will have versioned fields

    :param doc_type:
    :param document:
    :param tag:
    :param user: User document requesting tag for visibility check
    :return:
    """
    fields_version = None
    if tag:
        query_dsl = {
            'query': {
                'bool': {
                    'must': [
                        {
                            'term': {
                                "tag__v1": tag
                            }
                        },
                        {
                            "term": {
                                "field-version__doc_type__v1": doc_type
                            }
                        },
                        {
                            "term": {
                                "field-version__is_active__v1": True
                            }
                        }
                    ]
                }
            }
        }
        if user:
            query_dsl['query']['bool']['should'] = [
                {
                    'nested': {
                        'path': 'tag__v1.tag__permissions__v1.tag__permissions__users__v1',
                        'filter': {
                            {
                                'term': {
                                    'tag__v1.tag__permissions__v1.tag__permissions__users__v1.id': user['id']
                                }
                            }
                        }
                    }
                },
                {
                    'nested': {
                        'path': 'tag__v1.tag__permissions__v1.tag__permissions__groups__v1',
                        'filter': {
                            {
                                'term': {
                                    'tag__v1.tag__permissions__v1.tag__permissions__groups__v1.id':
                                        u' OR '.join(user['groups'])
                                }
                            }
                        }
                    }
                },
                {
                    'term': {
                        'tag__v1.tag__public__v1': True
                    }
                }
            ]
        es_response = get_es_response(
            req_session.get(
                get_path_search('field-version'),
                data=json.dumps(query_dsl)
            )
        )
        fields_version = map(lambda x: x['field__v1'], es_response['hits']['hits'])
    return walk(document, is_physical=True, fields_version=fields_version)


def to_physical_doc(doc_type, document, tag=None, user=None):
    """
    Logical document will have fields without version

    :param doc_type:
    :param document:
    :param tag:
    :param user:
    :return:
    """
    query = {
        'query': {
            'bool': {
                'must': [
                    {
                        "term": {
                            "field-version__doc_type__v1": doc_type
                        }
                    },
                    {
                        "term": {
                            "field-version__is_active__v1": True
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
                        'path': 'tag__permissions__v1.tag__permissions__users__v1',
                        'filter': {
                            {
                                'term': {
                                    'tag__permissions__v1.tag__permissions__users__v1.id': user['id']
                                }
                            }
                        }
                    }
                },
                {
                    'nested': {
                        'path': 'tag__permissions__v1.tag__permissions__groups__v1',
                        'filter': {
                            {
                                'term': {
                                    'tag__permissions__v1.tag__permissions__groups__v1.id':
                                        u' OR '.join(user['groups'])
                                }
                            }
                        }
                    }
                },
                {
                    'term': {
                        'tag__v1.tag__public__v1': True
                    }
                }
            ]
    es_response = get_es_response(
        req_session.get(get_path_search('field-version'),
                        data=json.dumps(query)))
    return walk(document, is_logical=True, fields_data=es_response['hits']['hits'], tag=tag)


def to_physical_fields(document_type, fields, tag=None, user=None):
    """
    Get physical fields

    :param document_type:
    :param fields: List of fields expanded in a query
    :param tag:
    :param user:
    :return:
    """
    query = {
        'query': {
            'bool': {
                'must': [
                    {
                        "term": {
                            "field-version__doc_type__v1.raw__v1": document_type
                        }
                    },
                    {
                        "term": {
                            "field-version__is_active__v1": True
                        }
                    }
                ]
            }
        },
        "from": 0, "size": 500,
    }
    if tag:
        query['query']['bool']['must'].append(
            {
                'term': {
                    "tag__v1.tag__slug__v1": tag
                }
            }
        )
        if user:
            query['query']['bool']['should'] = [
                {
                    'nested': {
                        'path': 'tag__v1.tag__permissions__v1.tag__permissions__users__v1',
                        'filter': {
                            {
                                'term': {
                                    'tag__v1.tag__permissions__v1.tag__permissions__users__v1.id': user['id']
                                }
                            }
                        }
                    }
                },
                {
                    'nested': {
                        'path': 'tag__v1.tag__permissions__v1.tag__permissions__groups__v1',
                        'filter': {
                            {
                                'term': {
                                    'tag__v1.tag__permissions__v1.tag__permisions__groups__v1.id':
                                        u' OR '.join(user['groups'])
                                }
                            }
                        }
                    }
                },
                {
                    'term': {
                        'tag__v1.tag__public__v1': True
                    }
                }
            ]
    # logger.debug(u'to_physical_fields :: query: {}'.format(json.dumps(query)))
    es_response = get_es_response(
        req_session.get(get_path_search('field-version'),
                        data=json.dumps(query)))
    # logger.debug(u'to_physical_fields :: response: {}'.format(es_response))
    # here we have all physical fields for document
    field_dict = {}
    # print u'physical db field response: {}'.format(es_response)
    # logger.debug(u'to_physical_fields :: count: {}'.format(len(es_response['hits']['hits'])))
    for field_db_es in es_response['hits']['hits']:
        field_db_data = field_db_es['_source']
        # logger.debug(u'to_physical_fields :: field_db_data: {}'.format(field_db_data))
        try:
            # logger.debug(u'to_physical_fields :: db field: {}'.format(field_db_data['field-version__field__v1']))
            field_dict[field_db_data['field-version__field_name__v1']] = field_db_data['field-version__field__v1']
        except (IndexError, KeyError):
            pass
    return field_dict


class DocumentManager(object):

    @classmethod
    def get_op(cls, field):
        """
        Get op from field

        :param field:
        :return:
        """
        ops = ['in']
        op = None
        field_name = field
        if '__' in field:
            op_fields = field.split('__')
            for op_guess in ops:
                if op_guess in op_fields and op_fields[-1] in ops:
                    op = op_fields[-1]
            if op:
                field_name = field.split('__' + op)[0]
            else:
                field_name = field
        return op, field_name

    @classmethod
    def fields_to_es_format(cls, document_type, fields_dict, expand=False):
        """
        Fields to ElasticSearch format. We receive

        :param document_type : Document type
        :param fields_dict: dictionary with kwargs received in filter type of methods
        :return: List of fields like ['field1', 'field1.field2', ... ]
        """
        fields_generated = []
        for field in fields_dict:
            op, field_name = DocumentManager.get_op(field)
            field_name = document_type + '__' + field_name
            if '__' not in field_name:
                fields_generated.append(field_name)
            else:
                if expand:
                    fields_generated.append(field_name.replace('__', '.'))
                else:
                    for field_item in field_name.split('__'):
                        fields_generated.append(field_item)
        return fields_generated

    @classmethod
    def get(cls, document_type, **kwargs):
        """
        Get document

        :param document_type:
        :param kwargs:
        :return:
        """
        # TODO: When document definition done, get index by type
        get_logical = False
        if 'get_logical' in kwargs and kwargs['get_logical']:
            get_logical = True
            del kwargs['get_logical']
        if 'es_path' in kwargs:
            es_path = kwargs.pop('es_path')
        else:
            if 'id' in kwargs:
                es_path = '{host}/{index}/{document_type}/{id_}'.format(
                    host=settings.ELASTIC_SEARCH_HOST,
                    index=kwargs.get('index', settings.SITE_BASE_INDEX),
                    document_type=document_type,
                    id_=kwargs['id'])
            else:
                es_path = '{host}/{index}/{document_type}/_search'.format(
                    host=settings.ELASTIC_SEARCH_HOST,
                    index=kwargs.get('index', settings.SITE_BASE_INDEX),
                    document_type=document_type)
        if 'id' in kwargs:
            # do logic for get by id
            es_response_raw = req_session.get(es_path)
            if es_response_raw.status_code != 200:
                raise exceptions.DocumentNotFound(_(u'Document "{}" with id "{}" does not exist'.format(
                    document_type, kwargs['id']
                )))
            es_response = es_response_raw.json()
            if 'status' in es_response and es_response['status'] != 200:
                raise exceptions.DocumentNotFound(_(u'Document "{}" with id "{}" does not exist'.format(
                    document_type, kwargs['id']
                )))

        elif 'slug' in kwargs:
            query_dsl = {
                'query': {
                    "filtered": {
                        'query': {
                            'bool': {
                                'must': [
                                    {
                                        'term': {
                                            'slug__v1.raw': kwargs['slug']
                                        }
                                    }
                                ]
                            }
                        }
                    }
                }
            }
            es_response_raw = req_session.get(es_path, data=json.dumps(query_dsl))
            if es_response_raw.status_code != 200:
                raise exceptions.DocumentNotFound(_(u'Document "{}" with slug "{}" does not exist'.format(
                    document_type, kwargs['slug']
                )))
            es_response = es_response_raw.json()
            if 'status' in es_response and es_response['status'] != 200:
                raise exceptions.DocumentNotFound(_(u'Document "{}" with slug "{}" does not exist'.format(
                    document_type, kwargs['slug']
                )))
        else:
            raise exceptions.XimpiaAPIException(u'We only support get document by id')
        if get_logical:
            logical_doc = to_logical_doc(document_type, es_response['_source'])
            logical_doc['id'] = es_response['_id']
            return logical_doc
        else:
            return es_response['_source']

    @classmethod
    def filter(cls, document_type, **kwargs):
        """
        Filter document. We use ES filters without queries

        We support IN operator

        field1__field2 = 78
        field1__field2__in=[78, 34]

        :param document_type:
        :param kwargs:
        :return:
        """
        get_logical = False
        if 'get_logical' in kwargs and kwargs['get_logical']:
            get_logical = True
            del kwargs['get_logical']
        index = None
        if 'index' in kwargs:
            index = kwargs.pop('es_path')
        if 'es_path' in kwargs:
            es_path = kwargs.pop('es_path')
        else:
            es_path = '{host}/{index}/{document_type}/_search'.format(
                host=settings.ELASTIC_SEARCH_HOST,
                index=index or settings.SITE_BASE_INDEX,
                document_type=document_type)

        # we have like ['status', 'user.value, ... ]
        # field_dict would have items like {'status': 'status__v1', 'value': 'value__v1'
        # print u'fields ES format: {}'.format(cls.fields_to_es_format(kwargs, expand=True))
        field_dict = to_physical_fields(document_type,
                                        cls.fields_to_es_format(document_type, kwargs, expand=True))
        # print u'field_dict: {}'.format(field_dict)
        # logger.debug(u'Document.filter :: field_dict: {}'.format(field_dict))

        # filter_data = {}
        query_items = []
        for field in kwargs:
            value = kwargs[field]
            if isinstance(value, (datetime.date, datetime.datetime)):
                value = value.strftime('"%Y-%m-%dT%H:%M:%S"')

            # field_name is like 'status', but on db we have like status__v1, status__v1.value__v1
            # logger.debug(u'Document.filter :: field_name: {}'.format(field_name))

            # filter_data[field_name] = value
            query_items.append({
                'term': {
                    field: value
                }
            })

        # print u'filter_data: {}'.format(filter_data)
        query_dsl = {
            'query': {
                'filtered': {
                    'query': {
                        'match_all': {}
                    },
                    'filter': {
                        'and': query_items
                    }
                }
            }
        }
        logger.debug(u'Document.filter :: type: {} query_dsl:{}'.format(
            document_type,
            query_dsl
        ))

        # print u'query_dsl: {}'.format(query_dsl)
        es_response_raw = req_session.get(es_path,
                                          data=json.dumps(query_dsl))
        es_response = es_response_raw.json()
        # print es_response_raw.content
        if get_logical:
            output = []
            for item in es_response['hits']['hits']:
                item_data = item['_source']
                # item_data['id'] = item['_id']
                item_document = to_logical_doc(document_type, item_data)
                item_document['id'] = item['_id']
                output.append(
                    item_document
                )
        else:
            output = es_response['hits']['hits']
        return output

    @classmethod
    def update_partial(cls, document_type, id_, partial_document, index=settings.SITE_BASE_INDEX):
        """
        Update partial document

        :param document_type:
        :param id_:
        :param partial_document:
        :return:
        """
        es_response_raw = req_session.post(
            '{host}/{index}/{document_type}/{id_}/_update'.format(
                host=settings.ELASTIC_SEARCH_HOST,
                index=index,
                document_type=document_type,
                id_=id_),
            data=json.dumps({
                'doc': partial_document
            })
        )
        if es_response_raw.status_code not in [200, 201]:
            raise exceptions.XimpiaAPIException(_(u'Could no partially update document {} '
                                                  u'with id {} doc: {} :: {}'.format(
                                                      document_type,
                                                      id_,
                                                      partial_document,
                                                      es_response_raw.content)))
        return es_response_raw.json()

    @classmethod
    def update(cls, document_type, id_, document):
        """
        Update partial document

        :param document_type:
        :param id_:
        :param document:
        :return:
        """
        es_response_raw = req_session.put(
            '{host}/{index}/{document_type}/{id_}'.format(
                host=settings.ELASTIC_SEARCH_HOST,
                index=settings.SITE_BASE_INDEX,
                document_type=document_type,
                id_=id_),
            data=json.dumps(document)
        )
        if es_response_raw.status_code != 200:
            raise exceptions.XimpiaAPIException(_(u'Could no update document {} '
                                                  u'with id {} doc: {}'.format(
                                                      document_type,
                                                      id_,
                                                      document)))
        return es_response_raw.json()


class Document(object):

    objects = DocumentManager()


def walk_mapping(mapping_piece):
    """

    :param mapping_piece:
    :return:
    """
    data = []
    for field in mapping_piece:
        version = field.split('__')[-1]
        if version == 'id':
            version = None
            field_name = field.split('__')[-1]
        else:
            field_name = field.split('__')[-2]
        if isinstance(field, dict):
            # nested type, we have field as dict
            if isinstance(field, dict):
                data.extend(walk_mapping(field))
        else:
            # object type
            data.append(
                {
                    'field': field,
                    'version': version,
                    'field_name': field_name,
                }
            )
    return data


def get_fields_from_mapping(mapping):
    """
    Get field versions from mapping data

    :param mapping:
    :return:
    """
    # Have walk_mapping
    # 1. Travel document type properties
    # 2.1 When no type, assume object: get items
    # 2.2 Parse when nested
    document_type = mapping.keys()[0]
    field_versions = []
    root_fields_map = mapping[document_type]['properties']
    for root_field in root_fields_map:
        # logger.debug(u'get_fields_from_mapping :: root_field: {}'.format(root_field))
        root_field_data = root_fields_map[root_field]
        field_type = root_field_data.get('type', 'object')
        # logger.debug(u'get_fields_from_mapping :: field_type: {}'.format(field_type))
        version = root_field.split('__')[-1]
        if version == 'id':
            version = None
            field_name = root_field.split('__')[-1]
        else:
            field_name = root_field.split('__')[-2]
        if field_type in ['object', 'nested']:
            field_versions.extend(walk_mapping(root_field_data['properties']))
            field_versions.append(
                {
                    'field': root_field,
                    'version': version,
                    'field_name': field_name,
                }
            )
        else:
            field_versions.append(
                {
                    'field': root_field,
                    'version': version,
                    'field_name': field_name,
                }
            )
    return field_versions


def save_field_versions_from_mapping(mapping, index='ximpia-api__base', user=None,
                                     tag=None, branch=None):
    """
    Save data into field versions for all fields in a mapping

    :param mapping:
    :return:
    """
    # logger.debug(u'save_field_versions_from_mapping...')
    from datetime import datetime
    now_es = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    fields = get_fields_from_mapping(mapping)
    fields_version_str = ''
    doc_type = mapping.keys()[0]
    user_id = getattr(user, 'id', None)
    user_name = getattr(user, 'username', None)
    # logger.debug(u'save_field_versions_from_mapping :: [{}] fields: {}'.format(doc_type, len(fields)))
    for field in fields:
        if field in ['text', 'text__v1']:
            continue
        bulk_header = '{ "create": { "_index": "' + index + '", "_type": "field-version"} }\n'
        bulk_data = json.dumps(
            {
                'field-version__doc_type__v1': doc_type,
                'field-version__field__v1': field['field'],
                'field-version__field_name__v1': field['field_name'],
                'field-version__version__v1': field['version'],
                'field-version__is_active__v1': True,
                'tag__v1': tag,
                'branch__v1': branch,
                'field-version__created_by__v1': {
                    'field-version__created_by__id': user_id,
                    'field-version__created_by__user_name__v1': user_name
                },
                'created_on__v1': now_es,
            }
        ) + '\n'
        if not fields_version_str:
            fields_version_str = bulk_header
            fields_version_str += bulk_data
        else:
            fields_version_str += bulk_header
            fields_version_str += bulk_data
    es_response_raw = requests.post(
        '{host}/_bulk'.format(host=settings.ELASTIC_SEARCH_HOST),
        data=fields_version_str,
        headers={'Content-Type': 'application/octet-stream'},
    )
    # logger.debug(u'save_field_versions_from_mapping :: status: {}'.format(es_response_raw.status_code))
    es_response = es_response_raw.json()
    # logger.debug(u'save_field_versions_from_mapping :: bulk response: {}'.format(es_response))
    # logger.debug(u'save_field_versions_from_mapping :: response: {}'.format(es_response))
    logger.info(u'save_field_versions_from_mapping :: doc_type: {} is OK: {} items: {}'.format(
        doc_type,
        es_response_raw.status_code in [200, 201] and es_response['errors'] is False,
        len(es_response['items'])
    ))
