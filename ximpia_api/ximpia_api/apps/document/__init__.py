__author__ = 'jorgealegre'


def walk(node, is_logical=None, is_physical=True):
    """
    Walk through dictionary

    field1__v1
    field1__v2

    In this case, I should get field1 as key and field1__v2 as value

    :param node:
    :return:
    """
    data = {}
    for key, item in node.items():
        # key might have version, or key should strip version
        if isinstance(item, (list, tuple)):
            data[key] = ''
        elif isinstance(item, dict):
            pass
        else:
            pass
    return data


def to_logical_doc(document):
    """
    Physical documents will have versioned fields

    :param document:
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
    physical_document = {}
    fields = document.keys()

    versions = {}

    # 1. get main fields
    # 2. walk fields: if list, walk :
    # 3. manage versions

    return physical_document
