import json
import logging
import requests
import pprint

from django.test import RequestFactory
# from django.core.urlresolvers import reverse
from rest_framework.reverse import reverse
from django.conf import settings

from base.tests import XimpiaClient as Client, XimpiaTestCase
from document import Document
from base import refresh_index
from patterns import NotExists
from . import pattern_validate_field

__author__ = 'jorgealegre'

logger = logging.getLogger(__name__)


class StringFieldTest(XimpiaTestCase):

    def setUp(self):
        self.c = Client()
        self.req_factory = RequestFactory()

    def tearDown(self):
        pass

    def test_string(self):
        from document.fields import StringField
        user = self.connect_user(user='my_site_admin', is_admin=True)
        with open('ximpia_api/apps/document/tests/data/doc_string.json') as f:
            doc_string_str = f.read()
        doc_string = json.loads(doc_string_str)
        request_attributes = '?access_token={access_token}&site={site}'.format(
            access_token=user['token'],
            site='my-site'
        )
        doc_type = 'test-string-field'
        index = 'my-site__base'
        response = self.c.post(
            reverse('document-definition-list',
                    kwargs={
                        'doc_type': doc_type
                    }) + request_attributes,
            json.dumps(doc_string),
            content_type="application/json",
        )
        response_data = json.loads(response.content)
        import pprint
        logger.debug(u'test_string:: create document: {}'.format(
            pprint.PrettyPrinter(indent=4).pformat(response_data)
        ))
        refresh_index('ximpia-api__base')
        refresh_index('my-site__base')
        # Check document definition created
        es_response_raw = requests.get(
            '{host}/{index}/{doc_type}/{id}'.format(
                host=settings.ELASTIC_SEARCH_HOST,
                index=index,
                doc_type=doc_type,
                id=response_data['_id']
            )
        )
        es_response = es_response_raw.json()
        self.assertTrue(es_response_raw.status_code == 200)
        self.assertTrue(es_response['found'])
        # Check mappings created
        es_response_raw = requests.get(
            '{host}/{index}/_mapping/{doc_type}'.format(
                host=settings.ELASTIC_SEARCH_HOST,
                index=index,
                doc_type=doc_type
            )
        )
        es_response = es_response_raw.json()
        self.assertTrue(es_response_raw.status_code == 200)
        self.assertTrue('test-string-field' in es_response[es_response.keys()[0]]['mappings'])
        # Check fields created
        response = Document.objects.filter(
            'field-version',
            **{
                'field-version__doc_type__v1.raw__v1': doc_type,
                'index': index
            }
        )
        self.assertTrue(response is not None)
        self.assertTrue(len(response) > 0)
        # ========
        # VALIDATE
        # ========
        self.assertTrue(pattern_validate_field(
            index, 'name', 'amazing', doc_string, StringField,
            pattern=NotExists(
                {
                    'path': '{doc_type}.name'.format(doc_type=doc_type),
                    'value': 'amazing'
                }
            )))
        self.assertTrue(not pattern_validate_field(
            index, 'name', 'coc', doc_string, StringField,
            pattern=NotExists(
                {
                    'path': '{doc_type}.name'.format(doc_type=doc_type),
                    'value': 'coc'
                }
            )))
        self.assertTrue(not pattern_validate_field(
            index, 'name', '1234567890111', doc_string, StringField,
            pattern=NotExists(
                {
                    'path': '{doc_type}.name'.format(doc_type=doc_type),
                    'value': '1234567890111'
                }
            )))


class NumberFieldTest(XimpiaTestCase):

    def setUp(self):
        self.c = Client()
        self.req_factory = RequestFactory()

    def tearDown(self):
        pass

    def test_number(self):
        from document.fields import NumberField
        user = self.connect_user(user='my_site_admin', is_admin=True)
        with open('ximpia_api/apps/document/tests/data/doc_number.json') as f:
            doc_number_str = f.read()
        doc_number = json.loads(doc_number_str)
        request_attributes = '?access_token={access_token}&site={site}'.format(
            access_token=user['token'],
            site='my-site'
        )
        doc_type = 'test-number-field'
        index = 'my-site__base'
        response = self.c.post(
            reverse('document-definition-list',
                    kwargs={
                        'doc_type': doc_type
                    }) + request_attributes,
            json.dumps(doc_number),
            content_type="application/json",
        )
        response_data = json.loads(response.content)
        logger.debug(u'NumberFieldTest :: write response: {}'.format(response_data))
        refresh_index('ximpia-api__base')
        refresh_index('my-site__base')
        # Check document definition created
        es_response_raw = requests.get(
            '{host}/{index}/{doc_type}/{id}'.format(
                host=settings.ELASTIC_SEARCH_HOST,
                index=index,
                doc_type=doc_type,
                id=response_data['_id']
            )
        )
        es_response = es_response_raw.json()
        logger.debug(u'NumberFieldTest :: get response: {}'.format(es_response))
        self.assertTrue(es_response_raw.status_code == 200)
        self.assertTrue(es_response['found'])
        # Check mappings created
        es_response_raw = requests.get(
            '{host}/{index}/_mapping/{doc_type}'.format(
                host=settings.ELASTIC_SEARCH_HOST,
                index=index,
                doc_type=doc_type
            )
        )
        es_response = es_response_raw.json()
        self.assertTrue(es_response_raw.status_code == 200)
        self.assertTrue('test-number-field' in es_response[es_response.keys()[0]]['mappings'])
        # Check fields created
        response = Document.objects.filter(
            'field-version',
            **{
                'field-version__doc_type__v1.raw__v1': doc_type,
                'index': index
            }
        )
        self.assertTrue(response is not None)
        self.assertTrue(len(response) > 0)
        # ========
        # VALIDATE
        # ========
        self.assertTrue(pattern_validate_field(
            index, 'like_count', 54, doc_number, NumberField,
            pattern=NotExists(
                {
                    'path': '{doc_type}.like_count'.format(doc_type=doc_type),
                    'value': 54
                }
            )))
        self.assertTrue(not pattern_validate_field(
            index, 'like_count', -10, doc_number, NumberField,
            pattern=NotExists(
                {
                    'path': '{doc_type}.like_count'.format(doc_type=doc_type),
                    'value': 54
                }
            )))
        self.assertTrue(pattern_validate_field(
            index, 'number_tries', 5, doc_number, NumberField,
            pattern=NotExists(
                {
                    'path': '{doc_type}.number_tries'.format(doc_type=doc_type),
                    'value': 5
                }
            )))
        self.assertTrue(not pattern_validate_field(
            index, 'number_tries', 50, doc_number, NumberField,
            pattern=NotExists(
                {
                    'path': '{doc_type}.number_tries'.format(doc_type=doc_type),
                    'value': 50
                }
            )))
        self.assertTrue(not pattern_validate_field(
            index, 'number_tries', -5, doc_number, NumberField,
            pattern=NotExists(
                {
                    'path': '{doc_type}.number_tries'.format(doc_type=doc_type),
                    'value': -5
                }
            )))
        self.assertTrue(pattern_validate_field(
            index, 'amount', 250, doc_number, NumberField,
            pattern=NotExists(
                {
                    'path': '{doc_type}.number_tries'.format(doc_type=doc_type),
                    'value': 250
                }
            )))
        self.assertTrue(not pattern_validate_field(
            index, 'amount', 50, doc_number, NumberField,
            pattern=NotExists(
                {
                    'path': '{doc_type}.number_tries'.format(doc_type=doc_type),
                    'value': 50
                }
            )))


class MapFieldTest(XimpiaTestCase):

    def setUp(self):
        self.c = Client()
        self.req_factory = RequestFactory()

    def tearDown(self):
        pass

    def test_map(self):
        from document.fields import MapField
        print
        print
        print
        user = self.connect_user(user='my_site_admin', is_admin=True)
        with open('ximpia_api/apps/document/tests/data/doc_map.json') as f:
            doc_map_str = f.read()
        doc_map = json.loads(doc_map_str)
        doc_type = 'test-map-field'
        field_data = doc_map['settings']
        field_data['name'] = 'settings'
        field_data['doc_type'] = doc_type
        # Test make_mapping
        field = MapField(**field_data)
        mappings = field.make_mapping()
        import pprint
        pprint.PrettyPrinter(indent=4).pprint(mappings)
        physical = field.get_physical(
            {
                'settings': {
                    'age': 45,
                    'name': 'James',
                    'profile': {
                        'fb': {
                            'name': 'james0067',
                            'url': 'http://facebook.com/'
                        },
                        'twitter': 'james0009'
                    }
                }
            }
        )
        pprint.PrettyPrinter(indent=4).pprint(physical)
        check = field.validate(
            {
                'settings': {
                    'age': 45,
                    'name': 'James',
                    'profile': {
                        'fb': {
                            'name': 'james0067',
                            'url': 'http://facebook.com/'
                        },
                        'twitter': 'james0009'
                    }
                }
            },
            field_data,
            doc_map
        )
        logger.debug(u'MapFieldTest :: check: {}'.format(check))


class MapListFieldTest(XimpiaTestCase):

    def setUp(self):
        self.c = Client()
        self.req_factory = RequestFactory()

    def tearDown(self):
        pass

    def test_list_map(self):
        from document.fields import MapListField
        print
        print
        print
        user = self.connect_user(user='my_site_admin', is_admin=True)
        with open('ximpia_api/apps/document/tests/data/doc_map_list.json') as f:
            doc_map_str = f.read()
        doc_map = json.loads(doc_map_str)
        doc_type = 'test-map-list-field'
        field_data = doc_map['settings']
        field_data['name'] = 'settings'
        field_data['doc_type'] = doc_type
        # Test make_mapping
        field = MapListField(**field_data)
        mappings = field.make_mapping()
        import pprint
        pprint.PrettyPrinter(indent=4).pprint(mappings)
        physical = field.get_physical(
            {
                'settings': [
                    {
                        'age': 45,
                        'name': 'James',
                        'profile': {
                            'fb': {
                                'name': 'james0067',
                                'url': 'http://facebook.com/'
                            },
                            'twitter': 'james0009'
                        }
                    },
                    {
                        'age': 23,
                        'name': 'John',
                        'profile': {
                            'fb': {
                                'name': 'john0067',
                                'url': 'http://facebook.com/john'
                            },
                            'twitter': 'john0009'
                        }
                    }
                ]
            }
        )
        pprint.PrettyPrinter(indent=4).pprint(physical)
        check = field.validate(
            {
                'settings': [
                    {
                        'age': 45,
                        'name': 'James',
                        'profile': {
                            'fb': {
                                'name': 'james0067',
                                'url': 'http://facebook.com/'
                            },
                            'twitter': 'james0009'
                        }
                    },
                    {
                        'age': 23,
                        'name': 'John',
                        'profile': {
                            'fb': {
                                'name': 'john0067',
                                'url': 'http://facebook.com/john'
                            },
                            'twitter': 'john0009'
                        }
                    }
                ]
            },
            field_data,
            doc_map
        )
        logger.debug(u'MapFieldTest :: check: {}'.format(check))


class ListFieldTest(XimpiaTestCase):

    def setUp(self):
        self.c = Client()
        self.req_factory = RequestFactory()

    def tearDown(self):
        pass

    def test_list(self):
        from document.fields import ListField
        print
        print
        print
        user = self.connect_user(user='my_site_admin', is_admin=True)
        with open('ximpia_api/apps/document/tests/data/doc_string_list.json') as f:
            doc_map_str = f.read()
        doc_map = json.loads(doc_map_str)
        doc_type = 'test-list-field'
        field_data = doc_map['status']
        field_data['name'] = 'status'
        field_data['doc_type'] = doc_type
        doc_config = doc_map['_meta']
        del doc_config['choices']
        doc_config['choices'] = {}
        doc_config['choices']['customer_status'] = [
            {
                'choice_item_name': 'approved'
            },
            {
                'choice_item_name': 'created'
            },
            {
                'choice_item_name': 'pending'
            }
        ]
        # Test make_mapping
        field = ListField(**field_data)
        mappings = field.make_mapping()
        import pprint
        pprint.PrettyPrinter(indent=4).pprint(mappings)
        physical = field.get_physical(
            [
                'approved', 'created', 'pending'
            ]
        )
        pprint.PrettyPrinter(indent=4).pprint(physical)
        check = field.validate(
            [
                'approved', 'created', 'pending'
            ],
            field_data,
            doc_config
        )
        logger.debug(u'ListFieldTest :: check: {}'.format(check))


class LinkFieldTest(XimpiaTestCase):

    def setUp(self):
        self.c = Client()
        self.req_factory = RequestFactory()

    def tearDown(self):
        pass

    def test_link(self):
        from document.fields import LinkField
        print
        print
        print
        user = self.connect_user(user='my_site_admin', is_admin=True)
        with open('ximpia_api/apps/document/tests/data/doc_link.json') as f:
            doc_map_str = f.read()
        doc_map = json.loads(doc_map_str)
        doc_type = 'test-link-field'
        field_data = doc_map['tag']
        field_data['name'] = 'tag'
        doc_config = doc_map['_meta']
        # Test make_mapping
        field = LinkField(**field_data)
        mappings = field.make_mapping()
        import pprint
        pprint.PrettyPrinter(indent=4).pprint(mappings)
        physical = field.get_physical(
            {
                'id': 'Lolskklsk88999'
            }
        )
        pprint.PrettyPrinter(indent=4).pprint(physical)
        check = field.validate(
            {
                'id': 'Lolskklsk88999'
            },
            field_data,
            doc_config,
            patterns_data={
                'exists': True
            }
        )
        logger.debug(u'LinkFieldTest :: check: {}'.format(check))


class LinksFieldTest(XimpiaTestCase):

    def setUp(self):
        self.c = Client()
        self.req_factory = RequestFactory()

    def tearDown(self):
        pass

    def test_links(self):
        from document.fields import LinksField
        print
        print
        print
        user = self.connect_user(user='my_site_admin', is_admin=True)
        with open('ximpia_api/apps/document/tests/data/doc_links.json') as f:
            doc_map_str = f.read()
        doc_map = json.loads(doc_map_str)
        doc_type = 'test-links-field'
        field_data = doc_map['tags']
        field_data['field_name'] = 'tags'
        doc_config = doc_map['_meta']
        # Test make_mapping
        field = LinksField(**field_data)
        mappings = field.make_mapping()
        import pprint
        pprint.PrettyPrinter(indent=4).pprint(mappings)
        physical = field.get_physical(
            {
                'ids': ['Lolskklsk88999', 'dsdsjkjs77877']
            }
        )
        pprint.PrettyPrinter(indent=4).pprint(physical)
        """check = field.validate(
            {
                'id': 'Lolskklsk88999'
            },
            field_data,
            doc_config,
            patterns_data={
                'exists': True
            }
        )
        logger.debug(u'LinkFieldTest :: check: {}'.format(check))"""


class DocumentDefinitionTest(XimpiaTestCase):

    def setUp(self):
        self.c = Client()
        self.req_factory = RequestFactory()

    def tearDown(self):
        pass

    def test_mappings(self):
        from document import DocumentDefinition
        user = self.connect_user(user='my_site_admin', is_admin=True)
        with open('ximpia_api/apps/document/tests/data/doc_string.json') as f:
            doc_string_str = f.read()
        doc_string = json.loads(doc_string_str)
        doc_type = 'test-string-field'
        index = 'my-site__base'
        document_definition = DocumentDefinition(doc_string, doc_type, user, index=index)
        logger.debug(u'DocumentDefinitionTest.test_mappings :: {}'.format(document_definition))
        mappings = document_definition.get_mappings()
        # pprint.PrettyPrinter(indent=4).pprint(mappings)
        self.assertTrue('name__v1' in mappings[doc_type]['properties'])
        with open('ximpia_api/apps/document/tests/data/doc_all.json') as f:
            doc_all_str = f.read()
        doc_all = json.loads(doc_all_str)
        doc_type = 'test-all'
        index = 'my-site__base'
        document_definition = DocumentDefinition(doc_all, doc_type, user, index=index)
        logger.debug(u'DocumentDefinitionTest.test_mappings :: {}'.format(document_definition))
        mappings = document_definition.get_mappings()
        pprint.PrettyPrinter(indent=2).pprint(mappings)
        # link
        with open('ximpia_api/apps/document/tests/data/doc_link.json') as f:
            doc_link_str = f.read()
        doc_link = json.loads(doc_link_str)
        doc_type = 'test-link'
        index = 'my-site__base'
        document_definition = DocumentDefinition(doc_link, doc_type, user, index=index)
        logger.debug(u'DocumentDefinitionTest.test_physical :: {}'.format(document_definition))
        mappings = document_definition.get_mappings()
        pprint.PrettyPrinter(indent=2).pprint(mappings)

    def test_physical(self):
        from document import DocumentDefinition
        user = self.connect_user(user='my_site_admin', is_admin=True)
        with open('ximpia_api/apps/document/tests/data/doc_string.json') as f:
            doc_string_str = f.read()
        doc_string = json.loads(doc_string_str)
        doc_type = 'test-string-field'
        index = 'my-site__base'
        document_definition = DocumentDefinition(doc_string, doc_type, user, index=index)
        logger.debug(u'DocumentDefinitionTest.test_physical :: {}'.format(document_definition))
        physical = document_definition.get_physical()
        # pprint.PrettyPrinter(indent=2).pprint(physical)
        self.assertTrue(len(physical['fields__v1']) > 0)
        with open('ximpia_api/apps/document/tests/data/doc_all.json') as f:
            doc_all_str = f.read()
        doc_all = json.loads(doc_all_str)
        doc_type = 'test-all'
        index = 'my-site__base'
        document_definition = DocumentDefinition(doc_all, doc_type, user, index=index)
        logger.debug(u'DocumentDefinitionTest.test_physical :: {}'.format(document_definition))
        physical = document_definition.get_physical()
        pprint.PrettyPrinter(indent=2).pprint(physical)
        self.assertTrue(len(physical['fields__v1']) > 0)
        # link
        with open('ximpia_api/apps/document/tests/data/doc_link.json') as f:
            doc_link_str = f.read()
        doc_link = json.loads(doc_link_str)
        doc_type = 'test-link'
        index = 'my-site__base'
        document_definition = DocumentDefinition(doc_link, doc_type, user, index=index)
        logger.debug(u'DocumentDefinitionTest.test_physical :: {}'.format(document_definition))
        physical = document_definition.get_physical()
        pprint.PrettyPrinter(indent=2).pprint(physical)
        self.assertTrue(len(physical['fields__v1']) > 0)

    def test_field_versions(self):
        from document import DocumentDefinition
        from xp_user.backends import XimpiaAuthBackend
        user_response = self.connect_user(user='my_site_admin', is_admin=True)
        user = XimpiaAuthBackend.get_user(user_response['id'])
        with open('ximpia_api/apps/document/tests/data/doc_all.json') as f:
            doc_all_str = f.read()
        doc_all = json.loads(doc_all_str)
        doc_type = 'test-all'
        index = 'my-site__base'
        document_definition = DocumentDefinition(doc_all, doc_type, user, index=index)
        logger.debug(u'DocumentDefinitionTest.test_field_versions :: {}'.format(document_definition))
        field_versions = document_definition.get_field_versions(index, user)
        # pprint.PrettyPrinter(indent=2).pprint(physical)
        logger.debug(u'DocumentDefinitionTest.test_field_versions :: field_versions: {}'.format(
            field_versions
        ))


class DocDefAllCreateTest(XimpiaTestCase):

    def setUp(self):
        self.c = Client()
        self.req_factory = RequestFactory()

    def tearDown(self):
        pass

    def test_main(self):
        print
        print
        print
        with open('ximpia_api/apps/document/tests/data/doc_all.json') as f:
            doc_definition_str = f.read()
        doc_definition = json.loads(doc_definition_str)
        user = self.connect_user(user='my_site_admin', is_admin=True)
        request_attributes = '?access_token={access_token}&site={site}'.format(
            access_token=user['token'],
            site='my-site'
        )
        doc_type = 'test-doc-all'
        index = 'my-site__base'
        response = self.c.post(
            reverse('document-definition-list',
                    kwargs={
                        'doc_type': doc_type
                    }) + request_attributes,
            json.dumps(doc_definition),
            content_type="application/json",
        )
        response_data = json.loads(response.content)
        import pprint
        logger.debug(u'DocDefCreate:: create document: {}'.format(
            pprint.PrettyPrinter(indent=4).pformat(response_data)
        ))
        """refresh_index('ximpia-api__base')
        refresh_index('my-site__base')
        # Check document definition created
        es_response_raw = requests.get(
            '{host}/{index}/{doc_type}/{id}'.format(
                host=settings.ELASTIC_SEARCH_HOST,
                index=index,
                doc_type=doc_type,
                id=response_data['_id']
            )
        )
        es_response = es_response_raw.json()
        self.assertTrue(es_response_raw.status_code == 200)
        self.assertTrue(es_response['found'])
        # Check mappings created
        es_response_raw = requests.get(
            '{host}/{index}/_mapping/{doc_type}'.format(
                host=settings.ELASTIC_SEARCH_HOST,
                index=index,
                doc_type=doc_type
            )
        )
        es_response = es_response_raw.json()
        self.assertTrue(es_response_raw.status_code == 200)
        self.assertTrue('test-string-field' in es_response[es_response.keys()[0]]['mappings'])
        # Check fields created
        response = Document.objects.filter(
            'field-version',
            **{
                'field-version__doc_type__v1.raw__v1': doc_type,
                'index': index
            }
        )
        self.assertTrue(response is not None)
        self.assertTrue(len(response) > 0)"""


class DocDefAllLinkCreateTest(XimpiaTestCase):

    def setUp(self):
        self.c = Client()
        self.req_factory = RequestFactory()

    def tearDown(self):
        pass

    def test_main(self):
        print
        print
        print
        with open('ximpia_api/apps/document/tests/data/doc_all.json') as f:
            doc_definition_str = f.read()
        doc_definition = json.loads(doc_definition_str)
        user = self.connect_user(user='my_site_admin', is_admin=True)
        request_attributes = '?access_token={access_token}&site={site}'.format(
            access_token=user['token'],
            site='my-site'
        )
        doc_type = 'test-doc-all'
        index = 'my-site__base'
        response = self.c.post(
            reverse('document-definition-list',
                    kwargs={
                        'doc_type': doc_type
                    }) + request_attributes,
            json.dumps(doc_definition),
            content_type="application/json",
        )
        response_data = json.loads(response.content)
        import pprint
        logger.debug(u'DocDefCreate:: create document: {}'.format(
            pprint.PrettyPrinter(indent=4).pformat(response_data)
        ))
        """refresh_index('ximpia-api__base')
        refresh_index('my-site__base')
        # Check document definition created
        es_response_raw = requests.get(
            '{host}/{index}/{doc_type}/{id}'.format(
                host=settings.ELASTIC_SEARCH_HOST,
                index=index,
                doc_type=doc_type,
                id=response_data['_id']
            )
        )
        es_response = es_response_raw.json()
        self.assertTrue(es_response_raw.status_code == 200)
        self.assertTrue(es_response['found'])
        # Check mappings created
        es_response_raw = requests.get(
            '{host}/{index}/_mapping/{doc_type}'.format(
                host=settings.ELASTIC_SEARCH_HOST,
                index=index,
                doc_type=doc_type
            )
        )
        es_response = es_response_raw.json()
        self.assertTrue(es_response_raw.status_code == 200)
        self.assertTrue('test-string-field' in es_response[es_response.keys()[0]]['mappings'])
        # Check fields created
        response = Document.objects.filter(
            'field-version',
            **{
                'field-version__doc_type__v1.raw__v1': doc_type,
                'index': index
            }
        )
        self.assertTrue(response is not None)
        self.assertTrue(len(response) > 0)"""


class LogicalToPhysicalTest(XimpiaTestCase):

    def setUp(self):
        self.c = Client()
        self.req_factory = RequestFactory()

    def tearDown(self):
        pass

    def test_main(self):
        print
        print
        print
        with open('ximpia_api/apps/document/tests/data/doc_all.json') as f:
            doc_definition_str = f.read()
        doc_definition = json.loads(doc_definition_str)
        with open('ximpia_api/apps/document/tests/data/doc_all_logical.json') as f:
            doc_logical_str = f.read()
        doc_logical = json.loads(doc_logical_str)


class FieldDocDefTest(XimpiaTestCase):

    def setUp(self):
        self.c = Client()
        self.req_factory = RequestFactory()

    def tearDown(self):
        pass

    def test_mappings(self):
        from document.fields import StringField, NumberField, DateTimeField, CheckField, ListField, \
            LinkField, LinksField, MapField, MapListField
        # string
        mapping = StringField().get_def_mappings()
        self.assertTrue(len(mapping) != 0)
        # pprint.PrettyPrinter(indent=4).pprint(mapping)
        # number
        mapping = NumberField().get_def_mappings()
        self.assertTrue(len(mapping) != 0)
        # pprint.PrettyPrinter(indent=4).pprint(mapping)
        # datetime
        mapping = DateTimeField().get_def_mappings()
        self.assertTrue(len(mapping) != 0)
        # pprint.PrettyPrinter(indent=4).pprint(mapping)
        # check
        mapping = CheckField().get_def_mappings()
        self.assertTrue(len(mapping) != 0)
        # pprint.PrettyPrinter(indent=4).pprint(mapping)
        # list
        mapping = ListField(**{'type': 'list-string'}).get_def_mappings()
        self.assertTrue(len(mapping) != 0)
        # pprint.PrettyPrinter(indent=4).pprint(mapping)
        # link
        mapping = LinkField().get_def_mappings()
        self.assertTrue(len(mapping) != 0)
        # pprint.PrettyPrinter(indent=4).pprint(mapping)
        # links
        mapping = LinksField().get_def_mappings()
        self.assertTrue(len(mapping) != 0)
        # pprint.PrettyPrinter(indent=4).pprint(mapping)
        # map
        mapping = MapField().get_def_mappings()
        self.assertTrue(len(mapping) != 0)
        # pprint.PrettyPrinter(indent=4).pprint(mapping)
        # map-list
        mapping = MapListField().get_def_mappings()
        self.assertTrue(len(mapping) != 0)
        # pprint.PrettyPrinter(indent=4).pprint(mapping)

    def test_string(self):
        from document.fields import StringField
        with open('ximpia_api/apps/document/tests/data/doc_string.json') as f:
            doc_string_str = f.read()
        doc_string = json.loads(doc_string_str)
        field_data = doc_string['status']
        field_data['name'] = 'status'
        field = StringField(**field_data)
        physical = field.get_def_physical()
        pprint.PrettyPrinter(indent=4).pprint(physical)
        self.assertTrue(len(physical) != 0)

    def test_number(self):
        from document.fields import NumberField
        with open('ximpia_api/apps/document/tests/data/doc_number.json') as f:
            doc_number_str = f.read()
        doc_number = json.loads(doc_number_str)
        field_data = doc_number['number_tries']
        field_data['name'] = 'number_tries'
        field = NumberField(**field_data)
        physical = field.get_def_physical()
        pprint.PrettyPrinter(indent=4).pprint(physical)
        self.assertTrue(len(physical) != 0)

    def test_list(self):
        from document.fields import ListField
        with open('ximpia_api/apps/document/tests/data/doc_string_list.json') as f:
            doc_string_list_str = f.read()
        doc_string_list = json.loads(doc_string_list_str)
        field_data = doc_string_list['status']
        field_data['name'] = 'status'
        field = ListField(**field_data)
        physical = field.get_def_physical()
        pprint.PrettyPrinter(indent=4).pprint(physical)
        self.assertTrue(len(physical) != 0)

    def test_map(self):
        from document.fields import MapField
        with open('ximpia_api/apps/document/tests/data/doc_map-simple.json') as f:
            doc_map_str = f.read()
        doc_map = json.loads(doc_map_str)
        field_data = doc_map['settings']
        field_data['name'] = 'settings'
        field = MapField(**field_data)
        physical = field.get_def_physical()
        pprint.PrettyPrinter(indent=4).pprint(physical)
        self.assertTrue(len(physical) != 0)
        with open('ximpia_api/apps/document/tests/data/doc_map.json') as f:
            doc_map_str = f.read()
        doc_map = json.loads(doc_map_str)
        field_data = doc_map['settings']
        field_data['name'] = 'settings'
        field = MapField(**field_data)
        physical = field.get_def_physical()
        pprint.PrettyPrinter(indent=4).pprint(physical)
        self.assertTrue(len(physical) != 0)

    def test_map_list(self):
        from document.fields import MapListField
        with open('ximpia_api/apps/document/tests/data/doc_map_list.json') as f:
            doc_map_list_str = f.read()
        doc_map_list = json.loads(doc_map_list_str)
        field_data = doc_map_list['settings']
        field_data['name'] = 'settings'
        field = MapListField(**field_data)
        physical = field.get_def_physical()
        pprint.PrettyPrinter(indent=4).pprint(physical)
        self.assertTrue(len(physical) != 0)
