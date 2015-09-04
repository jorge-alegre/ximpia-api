from collections import OrderedDict

from base import exceptions

__author__ = 'jorgealegre'


def walk(node, **kwargs):
    """
    Walk through dictionary

    field1__v1
    field1__v2

    In this case, I should get field1 as key and field1__v2 as value

    :param node:
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
        if isinstance(item, (list, tuple)) and isinstance(item[0], dict):
            data[key] = map(lambda x: walk(x, **kwargs), item)
        elif isinstance(item, dict):
            data[key] = walk(item, **kwargs)
        else:
            if is_physical:
                field, version = key.split('__')
                version_int = int(version[1:])
                versions_map.setdefault(field, {})
                versions_map[field][version_int] = item
            elif is_logical:
                # we need to generate version
                # we need to know latest field version from index to know
                # we have this info from mappings
                pass
    if is_physical:
        for field in versions_map:
            if not version:
                target_version = max(versions_map[field].keys())
            else:
                target_version = version
            data[field] = versions_map[field][target_version]
    elif is_logical:
        pass
    return data


def to_logical_doc(document, version=''):
    """
    Physical documents will have versioned fields

    :param document:
    :param version: Version to build document on. If none, we build latest version
    :return:
    """
    # we need to go through tree
    logical_document = {}
    fields = document.keys()
    return logical_document


def to_physical_doc(document):
    """
    Logical document will have fields without version

    :param document:
    :return:
    """
    # we need to get mappings from index
    physical_document = {}
    fields = document.keys()

    versions = {}

    # 1. get main fields
    # 2. walk fields: if list, walk :
    # 3. manage versions

    return physical_document
