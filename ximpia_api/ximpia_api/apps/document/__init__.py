import requests
import json
import datetime
import logging
import pprint
from requests.adapters import HTTPAdapter

from django.utils.translation import ugettext as _
from django.utils.text import slugify
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
    from copy import copy
    data = {}
    versions_map = {}
    is_physical = kwargs.get('is_physical', False)
    is_logical = kwargs.get('is_logical', False)
    fields_version = kwargs.get('fields_version', [])
    fields_data = kwargs.get('fields_data', [])
    doc_type = kwargs.get('doc_type', '')
    paths = kwargs.get('paths', [])
    tag = kwargs.get('tag', None)
    # logger.debug(u'walk :: paths: {}'.format(paths))
    # logger.debug(u'walk :: node: {}'.format(node))
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
                field = field_items[-1]
                versions_map.setdefault(field, {})
                versions_map[field][1] = item
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
            # logger.debug(u'walk :: field: {} target_version: {} item: {}'.format(field, target_version, item))
            if isinstance(item, dict):
                data[field] = walk(item, **kwargs)
            elif item and isinstance(item, (list, tuple)) and isinstance(item[0], dict):
                data[field] = map(lambda x: walk(x, **kwargs), item)
            else:
                data[field] = item
    elif is_logical:
        # logger.debug(u'walk :: fields_data: {}'.format(fields_data))
        for key, item in node.items():
            # key like 'status', item like 'ok', ['ok', 'right'], 67 or { field: value }, etc...
            # logger.debug(u'walk :: type: {} key: {} item: {}'.format(doc_type, key, item))
            if fields_data:
                if tag:
                    # like status__v7
                    field = map(lambda x: x,
                                filter(lambda y: y['field-version__field__v1'] == key, fields_data))[0]
                else:
                    fields = map(lambda x: x['_source']['field-version__field__v1'], fields_data)
                    # logger.debug(u'walk :: fields: {}'.format(fields))
                    # field: {version}
                    # logger.debug(u'walk :: versions_map: {} fields: {}'.format(versions_map, fields))
                    # like status__v7
                    # logger.debug(u'walk :: list1: {}'.format(filter(lambda x: x.split('__')[-2] == key, fields)))
                    fields_key = filter(lambda x: x.split('__')[-2] == key, fields)
                    # logger.debug(u'walk :: fields_key: {}'.format(fields_key))
                    if len(fields_key) > 1:
                        raise exceptions.XimpiaAPIException(u'More than one field for type: {} key: {} '
                                                            u'fields: {}'.format(
                                                                doc_type,
                                                                key,
                                                                fields
                                                            ))
                    # if key not in paths:
                    # paths.append(key)
                    # We need unit test for this, starting with basic documents
                    # Simple fields: user_name -> user__user_name__v1
                    # Links: app.slug -> app_v1.app__slug__v1
                    # Objects: my_obj.key -> doc_type__my_obj__v1.
                    # Idea, fields build physical data. What we do meanwhile???
                    """logger.debug(u'walk :: paths: {}'.format(paths))
                    paths_final = copy(paths)
                    paths_final.append(key)
                    for field_final_target in fields_key:
                        field_final_target_base = u'__'.join(field_final_target.split('__')[:-1])
                        logger.debug(u'walk :: field_final_target: {} field_final_target_base: {} '
                                     u'checked_to: {}'.format(
                                         field_final_target,
                                         field_final_target_base,
                                         u'__'.join(paths)
                                     ))
                        if u'__'.join(paths) in field_final_target_base:
                            field = field_final_target
                            break"""
                    if fields_key:
                        field = fields_key[0]
                    else:
                        if key == 'id':
                            field = 'id'
            else:
                field = u'{doc_type}__{key}__v1'.format(
                    doc_type=doc_type,
                    key=key
                )
            # logger.debug(u'walk :: field: {}'.format(field))
            if isinstance(item, dict):
                # logger.debug(u'walk :: I detect dict! paths: {}'.format(paths))
                paths_new = copy(paths)
                paths_new.append(key)
                kwargs['paths'] = paths_new
                # logger.debug(u'walk :: I detect dict! sent paths: {}'.format(paths_new))
                data[field] = walk(item, **kwargs)
            elif isinstance(item, (list, tuple)) and item and isinstance(item[0], dict):
                paths_new = copy(paths)
                paths_new.append(key)
                kwargs['paths'] = paths_new
                data[field] = map(lambda x: walk(x, **kwargs), item)
            else:
                data[field] = item
    return data


def to_logical_doc(doc_type, document, tag=None, user=None, **kwargs):
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
            },
            "from": 0, "size": 500,
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
                get_path_search('field-version', **kwargs),
                data=json.dumps(query_dsl)
            )
        )
        fields_version = map(lambda x: x['field__v1'], es_response['hits']['hits'])
    return walk(document, is_physical=True, fields_version=fields_version)


def to_physical_doc(doc_type, document, tag=None, user=None, **kwargs):
    """
    Logical document will have fields without version

    :param doc_type:
    :param document:
    :param tag:
    :param user:
    :return:
    """
    logger.debug(u'to_physical_doc :: doc_type: {} tag: {} user: {} document: {}'.format(
        doc_type, tag, user, document
    ))
    query = {
        'query': {
            'bool': {
                'must': [
                    {
                        "term": {
                            "field-version__doc_type__v1.raw__v1": doc_type
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
    # logger.debug(u'to_physical_doc :: query: {}'.format(query))
    es_response = get_es_response(
        req_session.get(get_path_search('field-version', **kwargs),
                        data=json.dumps(query)))
    # logger.debug(u'to_physical_doc :: response: {}'.format(es_response))
    return walk(document, is_logical=True, fields_data=es_response['hits']['hits'], tag=tag, doc_type=doc_type,
                paths=[doc_type])


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
            index = kwargs.pop('index')
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
            if isinstance(value, (list, tuple)):
                query_items.append({
                    'terms': {
                        field: value
                    }
                })
            else:
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
        root_field_data = mapping_piece[field]
        version = field.split('__')[-1]
        if version == 'id':
            version = None
            field_name = field.split('__')[-1]
        else:
            field_name = field.split('__')[-2]
        field_type = mapping_piece[field].get('type', 'object')
        if field_type in ['object', 'nested']:
            data.extend(walk_mapping(root_field_data['properties']))
            data.append(
                {
                    'field': field,
                    'version': version,
                    'field_name': field_name,
                }
            )
        else:
            # object type. Needs to do nested as well
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
                'field-version__created_on__v1': now_es,
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


class Validator(object):

    check = False
    errors = {}

    def __init__(self, check, errors):
        self.check = check
        self.errors = errors

    def __call__(self, *args, **kwargs):
        return self.check

    def __str__(self, *args, **kwargs):
        return 'true' if self.check else 'false : {}'.format(self.errors)

    def add_error(self, field, error):
        self.errors.setdefault(field, [])
        self.errors[field].append(error)
        self.check = False

    def valid(self):
        self.check = True

    def invalid(self):
        self.check = False


class DocumentDefinition(object):

    logical_source = {}
    doc_type = None
    branch_name = None
    tag_name = None
    field_map = {}
    docs = {}
    mappings = {}
    physical = {}
    user = None

    def __init__(self, logical, doc_type, user, tag_name=settings.REST_FRAMEWORK['DEFAULT_VERSION'],
                 branch_name=None, index=settings.SITE_BASE_INDEX):
        """
        Document definition entity that generates all data associated with a document definition

        * Mapping: For new document we generate mapping that later allows writing data into document
        * Physical Definition: Physical data for document definition mapping, with "_meta" as normal fields
          and fields inside a nested "fields" node.
        * Logical Definition: Logical document with some injections for tag, branch and _meta having same
        physical structure
        * Logical Source: Access to source logical document received (logical_source class attribute)

        :param logical:
        :param doc_type:
        :param user:
        :param tag_name:
        :param branch_name:
        :param index:
        :return:
        """
        self.logical_source = logical
        pprint.PrettyPrinter(indent=2).pprint(logical)
        self.doc_type = doc_type
        self.branch_name = branch_name
        self.tag_name = tag_name
        self.field_map = {}
        self.logical = None
        self.index = index
        self.docs = {}
        self._get_documents()
        self.user = user
        self.physical = {}

    def _get_field_index(self, field_instance):
        """
        Get field index, for link and links fields

        :param field_instance:
        :return:
        """
        if 'app' in field_instance and field_instance['app']:
            index = u'{app}'.format(
                app=field_instance['app']
            )
        else:
            index = self.index
        return index

    def _get_documents(self):
        """
        We can get documents like tag, branch and also link field, links field

        :return:
        """
        from base import get_mapping
        # We need the document definition, doc_type and tag would be enough
        # We would need the physical data, that we inject into Link and Links field types
        # We do bulk query for this
        documents = {}
        bulk_queries = {}
        bulk_queries_keys = []
        if not self.logical:
            self.logical = self.get_logical()
        print
        print
        pprint.PrettyPrinter(indent=2).pprint(self.logical)
        for field_name in self.logical.keys():
            logger.debug(u'DocumentDefinition._get_documents :: field_name: {}'.format(field_name))
            if field_name == '_meta':
                continue
            if field_name in self.field_map:
                field_instance = self.field_map[field_name]
            else:
                self._do_field_instance(field_name)
                field_instance = self.field_map[field_name]
            if field_instance.type in ['link', 'links']:
                index = self._get_field_index(field_instance)
                # mappings
                if field_instance.type_remote not in self.mappings:
                    self.mappings[field_instance.type_remote] = get_mapping(
                        field_instance.type_remote,
                        index=index
                    )
                # data
                query_key = u'{doc_type}-{field_name}'.format(
                    doc_type=field_instance.type_remote,
                    field_name=field_instance.name
                )
                if field_instance.type == 'link':
                    values = [self.logical[field_instance['name']]['id']]
                else:
                    values = [self.logical[field_instance['name']]['ids']]
                bulk_queries_keys.append(query_key)
                # query by id
                bulk_queries[query_key] = (json.dumps(
                    {
                        'index': index,
                        'type': field_instance.type_remote
                    }
                ), json.dumps(
                    {
                        'query': {
                            'ids': {
                                'type': field_instance.type_remote,
                                'values': values
                            }
                        }
                    }
                )
                )
        if self.tag_name:
            # We need data for tag, so insert into field-version tag embedded object
            bulk_queries_keys.append('tag_data')
            bulk_queries['tag_data'] = (json.dumps(
                {
                    'index': settings.SITE_BASE_INDEX,
                    'type': 'tag'
                }
            ), json.dumps(
                {
                    'query': {
                        'match_all': {}
                    },
                    'filter': {
                        'term': {
                            'tag__slug__v1.raw__v1': slugify(self.tag_name)
                        }
                    }
                }
            )
            )
        if self.branch_name:
            bulk_queries_keys.append('branch_data')
            bulk_queries['branch_data'] = (json.dumps(
                {
                    'index': settings.SITE_BASE_INDEX,
                    'type': 'branch'
                }
            ), json.dumps(
                {
                    'query': {
                        'match_all': {}
                    },
                    'filter': {
                        'term': {
                            'branch__slug__v1.raw__v1': slugify(self.branch_name)
                        }
                    }
                }
            )
            )
        # Make ES request
        bulk_queries_request = map(lambda x: bulk_queries[x], bulk_queries_keys)
        es_response_raw = requests.get(
            '{host}/_msearch'.format(
                host=settings.ELASTIC_SEARCH_HOST
            ),
            data=''.join(map(lambda x: '{}\n'.format(x[0]) + '{}\n'.format(x[1]), bulk_queries_request))
        )
        es_response = es_response_raw.json()
        logger.info(u'DocumentDefinition._get_documents :: response validations: {}'.format(
            es_response
        ))
        responses = es_response.get('responses', [])
        # update self.logical with tag and branch
        if 'tag_data' in bulk_queries_keys:
            try:
                response = responses[bulk_queries_keys.index('tag_data')]['hits']['hits'][0]
                self.docs['tag'] = response['_source']
                self.docs['tag']['tag__id'] = response['_id']
            except IndexError:
                pass
        if 'branch_data' in bulk_queries_keys:
            try:
                response = responses[bulk_queries_keys.index('branch_data')]['hits']['hits'][0]
                self.docs['branch'] = response['_source']
                self.docs['branch']['branch__id'] = response['_id']
            except IndexError:
                pass
        # parse link and links
        for key in bulk_queries_keys:
            if key not in ['tag_data', 'branch_data']:
                response = responses[bulk_queries_keys.index(key)]['hits']['hits']
                doc_type, field_name = key.split('-')
                if doc_type == 'link':
                    self.docs[field_name] = response[0]['_source']
                    self.docs[field_name][u'{}__id'.format(doc_type)] = response[0]['_id']
                elif doc_type == 'links':
                    values = []
                    for value_raw in response['hits']['hits']:
                        value = {'id': value_raw['_id']}
                        value.update(value_raw['_source'])
                        values.append(value)
                    self.docs[field_name] = values
        return documents

    def _do_field_instance(self, field_name):
        """
        Process field instance

        :param field_name:
        :return:
        """
        instance_data = self.logical[field_name]
        logger.debug(u'DocumentDefinition._do_field_instance :: field_name: {} instance_data: {}'.format(
            field_name, instance_data
        ))
        module = 'document.fields'
        instance = __import__(module)
        for comp in module.split('.')[1:]:
            instance = getattr(instance, comp)
        logger.debug(u'DocumentDefinition._do_field_instance :: instance: {} {}'.format(instance,
                                                                                        dir(instance)))
        field_class = getattr(instance, '{}Field'.format(instance_data['type'].capitalize()))
        logger.debug(u'DocumentDefinition._do_field_instance :: field_class: {}'.format(field_class))
        field_type_raw = instance_data['type']
        field_type = field_type_raw
        if '<' in field_type_raw:
            field_type = field_type_raw.split('<'[0])
        logger.debug(u'DocumentDefinition._do_field_instance :: field type: {}'.format(field_type))
        instance_data['name'] = field_name
        instance_data['doc_type'] = self.doc_type
        field_instance = field_class(**instance_data)
        self.field_map[field_name] = field_instance
        logger.debug(u'DocumentDefinition._do_field_instance :: field_map: {}'.format(self.field_map))

    def get_mapping(self):
        """
        Would generate mappings for document. No mapping generated for document definition.

        :return:
        """
        doc_mapping = {
            self.doc_type: {
                'dynamic': 'strict',
                '_timestamp': {
                    "enabled": True
                },
                "properties": {
                }
            }
        }
        # travel fields and get mapping for whole document
        if not self.logical:
            self.logical = self.get_logical()
        for field_name in self.logical.keys():
            if field_name == '_meta':
                continue
            if field_name in self.field_map:
                field_instance = self.field_map[field_name]
            else:
                self._do_field_instance(field_name)
                field_instance = self.field_map[field_name]
            field_mapping = field_instance.make_mapping()
            if field_instance.type in ['link', 'links']:
                if field_instance.type_remote in self.mappings:
                    doc_type = field_instance.type_remote
                    index = self._get_field_index(field_instance)
                    field_mapping.update(
                        self.mappings[field_instance.type_remote][index]['mappings'][doc_type]['properties']
                    )
            doc_mapping[self.doc_type]['properties'].update(field_mapping)
        return doc_mapping

    def get_logical(self):
        """
        Get parsed logical

        :return:
        """
        input_document = dict()
        input_document['_meta'] = {}
        input_document_request = self.logical_source
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
                            choice_name: choice_list
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
        input_document['fields'] = {}
        for field in input_document_request:
            if field != '_meta':
                # we check validations. Only support is-unique, exists and not-exists
                field_data = input_document_request[field]
                if 'active' not in field_data:
                    field_data['active'] = True
                field_data['name'] = field
                if 'validations' in field_data and filter(lambda x: x['type'] == 'is-unique',
                                                          field_data['validations']):
                    validations_new = []
                    for validation_data in field_data['validations']:
                        if validation_data['type'] == 'is-unique':
                            validation_data_item = {
                                'type': 'not-exists',
                                'path': '{doc_type}.{field}'.format(
                                    doc_type=self.doc_type,
                                    field=field
                                ),
                                'value': 'self'
                            }
                            validations_new.append(validation_data_item)
                    field_data['validations'] = validations_new
                input_document['fields'][field] = field_data
        return input_document

    def put_timestamp(self, user):
        """
        Put timestamp for document definition and user data into physical doc for db writing.
        Physical could have been created or not yet.

        :param user:
        :return:
        """
        from datetime import datetime
        self.physical[u'created_on__v1'] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        if self.user:
            self.physical[u'created_by__v1'] = {
                u'created_by__id': user.id,
                u'created_by__user_name__v1': user.username
                }

    def get_physical(self):
        """
        Get physical for document definition doc-type

        :return:
        """
        if not self.logical:
            self.logical = self.get_logical()
        # Write physical meta fields into main root node
        for meta_item in self.logical['_meta']:
            meta_field = u'{field}__v1'.format(
                field=meta_item
            )
            self.physical[meta_field] = self.logical['_meta'][meta_item]
        for field_name in self.logical:
            if field_name == '_meta':
                continue
            if field_name in self.field_map:
                field_instance = self.field_map[field_name]
            else:
                self._do_field_instance(field_name)
                field_instance = self.field_map[field_name]
            self.physical['document-definition__fields__v1'].setdefault(
                u'fields__{}__v1'.format(field_instance.type),
                []
            )
            fields_node = self.physical['document-definition__fields__v1']
            type_field = u'fields__{}__v1'.format(field_instance.type)
            fields_node[type_field].append(field_instance.get_def_physical())
        return self.physical

    def get_field_versions(self, index, user):
        """
        Get field versions

        :param index:
        :param user:
        :return:
        """
        from datetime import datetime
        fields_version_str = ''
        now_es = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        if not self.logical:
            self.logical = self.get_logical()
        for field_name in self.logical.keys():
            if field_name == '_meta':
                continue
            if field_name in self.field_map:
                field_instance = self.field_map[field_name]
            else:
                self._do_field_instance(field_name)
                field_instance = self.field_map[field_name]
            field_items = field_instance.get_field_items()
            bulk_header = '{ "create": { "_index": "' + index + '", "_type": "field-version"} }\n'
            # Note: field__v1 would need to be generated by fields, since changes for links, string fields, etc...
            bulk_data = json.dumps(
                {
                    'field-version__doc_type__v1': self.doc_type,
                    'field-version__field__v1': field_items['field'],
                    'field-version__field_name__v1': field_items['field_name'],
                    'field-version__type__v1': field_instance.type,
                    'field-version__version__v1': settings.REST_FRAMEWORK['DEFAULT_VERSION'],
                    'tag__v1': self.logical['_meta']['tag'],
                    'branch__v1': self.logical['_meta']['branch'],
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
        return fields_version_str
