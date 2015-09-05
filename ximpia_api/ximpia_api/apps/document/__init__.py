import requests
from requests.adapters import HTTPAdapter

from collections import OrderedDict

from django.conf import settings

from base import exceptions, get_es_response

__author__ = 'jorgealegre'

MAX_RETRIES = 3

req_session = requests.Session()
req_session.mount('https://{}'.format(settings.SEARCH_HOST),
                  HTTPAdapter(max_retries=MAX_RETRIES))


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
    version = kwargs.get('version', None)
    if is_physical is False and is_logical is False:
        raise exceptions.XimpiaAPIException(u'Need physical or logical filter')
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
            if not version:
                target_version = max(versions_map[field].keys())
            else:
                target_version = int(version.split('v')[1])
            print 'target_version: {}'.format(target_version)
            item = versions_map[field][target_version]
            if isinstance(item, dict):
                data[field] = walk(item, **kwargs)
            elif isinstance(item, (list, tuple)) and isinstance(item[0], dict):
                data[field] = map(lambda x: walk(x, **kwargs), item)
            else:
                data[field] = item
    elif is_logical:
        pass
    return data


def to_logical_doc(doc_type, document, tag=None):
    """
    Physical documents will have versioned fields

    :param document:
    :return:
    """
    # get fields active for doc_type and tag
    if tag:
        es_response = get_es_response(
            req_session.get(
                '',
            )
        )
    return walk(document, is_physical=True)


def to_physical_doc(doc_type, document, tag=None):
    """
    Logical document will have fields without version

    :param document:
    :param version: Version to build document on. If none, we build latest version
    :return:
    """
    # We need to get mappings for doc_type
    return walk(document, is_logical=True)
