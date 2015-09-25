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
req_session.mount('https://{}'.format(settings.SEARCH_HOST),
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
            field, version_str = key.split('__')
            version_int = int(version_str[1:])
            versions_map.setdefault(field, {})
            versions_map[field][version_int] = item
    print versions_map
    if is_physical:
        for field in versions_map:
            print field
            if not fields_version:
                target_version = max(versions_map[field].keys())
            else:
                target_version = int(filter(lambda x: x.split('__')[0] == field,
                                            fields_version)[0].split('__')[1][1:])
            print 'target_version: {}'.format(target_version)
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
            if tag:
                # like status__v7
                field = map(lambda x: x,
                            filter(lambda y: y['field__v1'] == key, fields_data))[0]
            else:
                fields = map(lambda x: x['field__v1'], fields_data)
                # field: {version}
                versions_map = map(lambda x: (x['field__v1'].split('__')[0], {x['field__v1'].split('__')[1]}),
                                   fields_data)
                # like status__v7
                field = map(lambda y: max(list(versions_map[y.split('__')[0]])),
                            filter(lambda x: x.split('__')[0] == key, fields))
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
                                "doc_type__v1": doc_type
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
        if user:
            query_dsl['query']['bool']['should'] = [
                {
                    'nested': {
                        'path': 'tag__v1.permissions__v1.users__v1',
                        'filter': {
                            {
                                'term': {
                                    'tag__v1.permissions__v1.users__v1.id': user['id']
                                }
                            }
                        }
                    }
                },
                {
                    'nested': {
                        'path': 'tag__v1.permissions__v1.groups__v1',
                        'filter': {
                            {
                                'term': {
                                    'tag__v1.permissions__v1.groups__v1.id': u' OR '.join(user['groups'])
                                }
                            }
                        }
                    }
                },
                {
                    'term': {
                        'tag__v1.public__v1': True
                    }
                }
            ]
        es_response = get_es_response(
            req_session.get(
                get_path_search('_field_version'),
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
                            "doc_type__v1": doc_type
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
    es_response = get_es_response(
        req_session.get(get_path_search('_field_version'),
                        data=json.dumps(query)))
    return walk(document, is_logical=True, fields_data=es_response['hits']['hits'], tag=tag)


class DocumentManager(object):

    @classmethod
    def get(cls, document_type, **kwargs):
        """
        Get document

        :param document_type:
        :param kwargs:
        :return:
        """
        if 'es_path' in kwargs:
            es_path = kwargs.pop('es_path')
        else:
            es_path = 'http://{host}/{index}/{document_type}/{id_}'.format(
                host=settings.ELASTIC_SEARCH_HOST,
                index=settings.SITE_BASE_INDEX,
                document_type=document_type,
                id_=kwargs['id'])
        if len(kwargs) == 1 and 'id' in kwargs:
            # do logic for get by id
            es_response_raw = req_session.get(es_path)
            if es_response_raw.status_code != 200 or 'status' in es_response_raw and es_response_raw['status'] != 200:
                raise exceptions.DocumentNotFound(_(u'Document "{}" with id "{}" does not exist'.format(
                    document_type, kwargs['id']
                )))
            es_response = es_response_raw.json()
            return es_response['_source']
        else:
            raise exceptions.XimpiaAPIException(u'We only support get document by id')

    @classmethod
    def filter(cls, document_type, **kwargs):
        """
        Filter document. We use ES filters without queries

        We support IN operator

        :param document_type:
        :param kwargs:
        :return:
        """
        if 'es_path' in kwargs:
            es_path = kwargs.pop('es_path')
        else:
            es_path = 'http://{host}/{index}/{document_type}/_search'.format(
                host=settings.ELASTIC_SEARCH_HOST,
                index=settings.SITE_BASE_INDEX,
                document_type=document_type)

        filter_data = {}
        for field in kwargs:
            op = None
            field_name = field
            value = kwargs[field]
            if '__' in field:
                op = field.split('__')[1]
                field_name = field.split('__')[0]
            if op == 'in':
                value = u' OR '.join(map(lambda x: u'{}'.format(x), value))
            if op and op not in ['in']:
                raise exceptions.XimpiaAPIException(u'Only IN operator is supported')
            if isinstance(value, (datetime.date, datetime.datetime)):
                value = value.strftime('"%Y-%m-%dT%H:%M:%S"')
            filter_data[field_name] = value

        query_dsl = {
            'query': {
                'filtered': {
                    'filter': {
                        {
                            'and': map(lambda x: {
                                'term': {
                                    x[0]: x[1]
                                }
                            }, filter_data)
                        }
                    }
                }
            }
        }

        es_response_raw = req_session.get(es_path,
                                          data=json.dumps(query_dsl))
        es_response = es_response_raw.json()
        return es_response['hits']['hits']

    @classmethod
    def update_partial(cls, document_type, id_, partial_document):
        """
        Update partial document

        :param document_type:
        :param id_:
        :param partial_document:
        :return:
        """
        es_response_raw = req_session.post(
            'http://{host}/{index}/{document_type}/{id_}'.format(
                host=settings.ELASTIC_SEARCH_HOST,
                index=settings.SITE_BASE_INDEX,
                document_type=document_type,
                id_=id_),
            data=json.dumps({
                'doc': partial_document
            })
        )
        if es_response_raw.status_code != 200:
            raise exceptions.XimpiaAPIException(_(u'Could no partially update document {} '
                                                  u'with id {} doc: {}'.format(
                                                      document_type,
                                                      id_,
                                                      partial_document)))
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
            'http://{host}/{index}/{document_type}/{id_}'.format(
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
