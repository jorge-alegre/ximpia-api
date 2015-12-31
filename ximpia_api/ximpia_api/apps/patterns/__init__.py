from document import Document
from base import exceptions

__author__ = 'jorgealegre'

u"""

We need to define a pattern interface as we advance development on document definition and documents

path:
document.field

No app definition when we want a pattern

{
    'customer-code': {
        'type': 'string',
        'validations': [
            {
                'type': 'not-exists',
                'path': 'customer.customer-code',
                'value': 'sjs68ss'
            }
        ]
    }
}

Data Optimization
-----------------

How could we send all validations in same query????

We could send bulk query and then parse results!!!

Have a nice way to implement in code

One way is having aa lazy mode, but would be called from the API endpoint, so we only execute once.

This would require that field validate is called from API endpoint and have a different design

"""


class NotExists(object):

    data = None

    def __init__(self, data):
        self.data = data

    def build_query(self):
        """
        Build query

        :return:
        """
        path = self.data['path']
        value = self.data['value']
        path_fields = path.split('.')
        document = path_fields[0]
        query = Document.objects.build_bulk_query(
            document,
            **{
                path_fields[1:].replace('.', '__'): value
            }
        )
        return query

    @classmethod
    def validate(cls, result):
        """
        Not exists validation

        This actually is building a bulk query, which gets executed by API endpoint to validate
        document in one query.

        Based on build_query, validate processes result sent by API endpoint.

        This way we are sure that we only hit index once.

        :param result: This is the logical representation of query sent

        :return:
        """
        if result:
            return False
        else:
            return True


class Exists(object):

    data = None

    def __init__(self, data):
        self.data = data

    def build_query(self):
        """
        Build query

        :return:
        """
        path = self.data['path']
        value = self.data['value']
        path_fields = path.split('.')
        document = path_fields[0]
        query = Document.objects.build_bulk_query(
            document,
            **{
                path_fields[1:].replace('.', '__'): value
            }
        )
        return query

    @classmethod
    def validate(cls, result):
        """
        Exists validation

        :return:
        """
        if result:
            return True
        else:
            return False
