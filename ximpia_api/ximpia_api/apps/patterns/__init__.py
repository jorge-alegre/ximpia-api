import json
import logging

logger = logging.getLogger(__name__)

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

    def build_query(self, index=None):
        """
        Build query

        :param index: Optional index

        :return:
        """
        path = self.data['path']
        value = self.data['value']
        path_fields = path.split('.')
        document = path_fields[0]
        query = {
            'query': {
                'filtered': {
                    'filter': {
                        'term': {
                            '.'.join(path_fields[1:]): value
                        }
                    }
                }
            }
        }
        if index:
            return '{header}\n{body}\n'.format(
                header=json.dumps({'index': index, 'type': document}),
                body=json.dumps(query)
            )
        else:
            return '{header}\n{body}\n'.format(
                header=json.dumps({}),
                body=json.dumps(query)
            )

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
        count = result['hits']['total']
        if count >= 1:
            return False
        else:
            return True


class Exists(object):

    data = None

    def __init__(self, data):
        self.data = data

    def build_query(self, index=None):
        """
        Build query

        :param index: Optional index

        :return:
        """
        path = self.data['path']
        value = self.data['value']
        path_fields = path.split('.')
        document = path_fields[0]
        query = {
            'query': {
                'filtered': {
                    'filter': {
                        'term': {
                            '.'.join(path_fields[1:]): value
                        }
                    }
                }
            }
        }
        if index:
            return '{header}\n{body}\n'.format(
                header=json.dumps({'index': index, 'type': document}),
                body=json.dumps(query)
            )
        else:
            return '{header}\n{body}\n'.format(
                header=json.dumps({}),
                body=json.dumps(query)
            )

    @classmethod
    def validate(cls, result):
        """
        Exists validation

        :return:
        """
        count = result['hits']['total']
        if count >= 1:
            return True
        else:
            return False
