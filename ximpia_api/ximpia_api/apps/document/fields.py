import logging
from datetime import datetime

from django.conf import settings
from django.utils.translation import ugettext as _

from base import exceptions
from . import Validator

__author__ = 'jorgealegre'

logger = logging.getLogger(__name__)


class Field(object):

    allowed_attributes = {}
    field_data = {}
    type = None
    name = None

    boolean_attributes = {'add_summary', 'active', 'only_positive', 'only_negative'}
    string_attributes = {'display_name', 'type', 'name', 'doc_type', 'mode',
                         'type_remote', 'app', 'embedded_into'}
    text_attributes = {'hint', 'comment'}
    number_attributes = {'max_length', 'min_length', 'min_value', 'max_value'}

    def get_def_physical(self):
        """
        Get physical for document-definition type

        Example for StringField document definition physical:
        {
          document-definition__fields__string__active__v1: True,
          document-definition__fields__string__validations__v1: [
            document-definition__fields__string__validations__type__v1: ,
            document-definition__fields__string__validations__path__v1: ,
            document-definition__fields__string__validations__value__v1: ,
            document-definition__fields__string__validations__modes__v1: ,
            document-definition__fields__string__validations__context__v1:
          ],
          document-definition__fields__string__choices__v1: {
            document-definition__fields__string__choices__choice_name__v1: '',
            document-definition__fields__string__choices__default_value__v1: '',
          },
          document-definition__fields__string__default__v1: '',
          document-definition__fields__string__add_summary__v1: True,
          document-definition__fields__string__hint__v1: '',
          document-definition__fields__string__comment__v1: '',
          document-definition__fields__string__display_name__v1: '',
          document-definition__fields__string__max_length__v1: None,
          document-definition__fields__string__min_length__v1: None,
          document-definition__fields__string__is_autocomplete__v1: False
        }

        mappings is the fields mappings for document definition

        :return:
        {
            "physical": ...
            "mappings": ...
        }
        """
        physical = {}
        for key in self.allowed_attributes:
            # We catch complex structures for all fields
            if key in ['validations', 'choices']:
                physical[u'document-definition__fields__{type}__{field}__v1'.format(
                    type=self.type,
                    field=key
                )] = {}
            elif key == 'items' and self.type == 'map':
                physical[u'items'] = {}
            elif key == 'items' and self.type == 'map-list':
                physical[u'items'] = []
            else:
                physical[u'document-definition__fields__{type}__{field}__v1'.format(
                    type=self.type,
                    field=key
                )] = None
            if key == 'validations':
                validations_node = physical[u'document-definition__fields__{type}__validations__v1'.format(
                    type=self.type
                )]
                """
                "validations": [
                    {
                        "type": "is-unique"
                    }
                ]
                """
                prefix = u'document-definition__fields__{type}__validations'.format(
                    type=self.type
                )
                if key in self.field_data and self.field_data[key]:
                    validations_node[u'{}prefix__type__v1'.format(prefix=prefix)] = None
                    validations_node[u'{}prefix__path__v1'.format(prefix=prefix)] = None
                    validations_node[u'{}prefix__value__v1'.format(prefix=prefix)] = None
                    validations_node[u'{}prefix__modes__v1'.format(prefix=prefix)] = None
                    validations_node[u'{}prefix__context__v1'.format(prefix=prefix)] = None
                    if self.field_data[key]['type']:
                        validations_node[u'{}prefix__type__v1'.format(
                            prefix=prefix
                        )] = self.field_data[key]['type']
                    if self.field_data[key]['path']:
                        validations_node[u'{}prefix__path__v1'.format(
                            prefix=prefix
                        )] = self.field_data[key]['path']
                    if self.field_data[key]['value']:
                        validations_node[u'{}prefix__value__v1'.format(
                            prefix=prefix
                        )] = self.field_data[key]['value']
                    if self.field_data[key]['modes']:
                        validations_node[u'{}prefix__modes__v1'.format(
                            prefix=prefix
                        )] = self.field_data[key]['modes']
                    if self.field_data[key]['context']:
                        validations_node[u'{}prefix__context__v1'.format(
                            prefix=prefix
                        )] = self.field_data[key]['context']
            elif key == 'choices':
                """
                "choices": {
                    "name": "customer_status",
                    "default": "created"
                }
                """
                choice_node = physical[u'document-definition__fields__{type}__choices__v1'.format(
                    type=self.type
                )]
                prefix = u'document-definition__fields__{type}__choices'.format(
                    type=self.type
                )
                if key in self.field_data and self.field_data[key]:
                    choice_node[u'{prefix}__choice_name__v1'.format(
                        prefix=prefix
                    )] = self.field_data[key]['name']
                    choice_node[u'{prefix}__default_value__v1'.format(
                        prefix=prefix
                    )] = self.field_data[key]['default']
            elif key == 'items':
                """
                "items": {
                    "field": {
                        "type": "string,
                        ...
                    }
                }
                """
                # MapField: dict MapListField: list
                if self.type == 'map':
                    items_node = physical[u'items']
                    for map_field in self.field_data[key]:
                        # We need to instance field
                        key_instance_data = self.field_data[key][map_field]
                        module = 'document.fields'
                        key_instance = __import__(module)
                        for comp in module.split('.')[1:]:
                            key_instance = getattr(key_instance, comp)
                        logger.debug(u'Field.get_def_physical :: instance: {} {}'.format(key_instance,
                                                                                         dir(key_instance)))
                        field_class = getattr(key_instance, '{}Field'.format(key_instance_data['type'].capitalize()))
                        logger.debug(u'Field.get_def_physical :: field_class: {}'.format(field_class))
                        field_type_raw = key_instance_data['type']
                        field_type = field_type_raw
                        if '<' in field_type_raw:
                            field_type = field_type_raw.split('<'[0])
                        logger.debug(u'Field.get_def_physical :: field type: {}'.format(field_type))
                        key_instance_data[u'name'] = map_field
                        key_instance_data[u'doc_type'] = None
                        if u'embedded_into' in key_instance_data:
                            key_instance_data[u'embedded_into'] += u'.{}'.format(self.name)
                        else:
                            key_instance_data[u'embedded_into'] = self.name
                        key_field_instance = field_class(**key_instance_data)
                        items_node[u'document-definition__fields__{type}__items__{field}__v1'.format(
                            type=self.type,
                            field=map_field
                        )] = key_field_instance.get_def_physical()
                if self.type == 'map-list':
                    items_node = physical[u'items']
                    for map_dict in self.field_data[key]:
                        map_dict_ = {}
                        for map_field in map_dict:
                            key_instance_data = self.field_data[key][map_field]
                            module = 'document.fields'
                            key_instance = __import__(module)
                            for comp in module.split('.')[1:]:
                                key_instance = getattr(key_instance, comp)
                            logger.debug(u'Field.get_def_physical :: instance: {} {}'.format(key_instance,
                                                                                             dir(key_instance)))
                            field_class = getattr(key_instance, '{}Field'.format(key_instance_data['type'].capitalize()))
                            logger.debug(u'Field.get_def_physical :: field_class: {}'.format(field_class))
                            field_type_raw = key_instance_data['type']
                            field_type = field_type_raw
                            if '<' in field_type_raw:
                                field_type = field_type_raw.split('<'[0])
                            logger.debug(u'Field.get_def_physical :: field type: {}'.format(field_type))
                            key_instance_data[u'name'] = map_field
                            key_instance_data[u'doc_type'] = None
                            if u'embedded_into' in key_instance_data:
                                key_instance_data[u'embedded_into'] += u'.{}'.format(self.name)
                            else:
                                key_instance_data[u'embedded_into'] = self.name
                            key_field_instance = field_class(**key_instance_data)
                            map_dict_[u'document-definition__fields__{type}__items__{field}__v1'.format(
                                type=self.type,
                                field=map_field
                            )] = key_field_instance.get_def_physical()
                        items_node.append(map_dict_)
            else:
                if key in self.field_data and self.field_data[key]:
                    field_name = u'document-definition__fields__{type}__{field}__v1'.format(
                        type=self.type,
                        field=key
                    )
                    physical[field_name] = self.field_data[key]
        return physical

    def get_def_mappings(self):
        """
        Get mapping for field for document definition

        :return:
        """
        mappings = {}
        for key in self.allowed_attributes:
            if key == 'validations':
                mappings[u"document-definition__fields__{type}__validations__v1".format(type=self.type)] = {
                    u"type": u"nested",
                    u"properties": {
                        u"document-definition__fields__{type}__validations__type__v1".format(type=self.type): {
                            u"type": u"string",
                            u"index": u"not_analyzed"
                        },
                        u"document-definition__fields__{type}__validations__path__v1".format(type=self.type): {
                            u"type": u"string",
                            u"index": u"not_analyzed"
                        },
                        u"document-definition__fields__{type}__validations__value__v1".format(type=self.type): {
                            u"type": u"string",
                            u"index": u"no"
                        },
                        u"document-definition__fields__{type}__validations__modes__v1".format(type=self.type): {
                            u"type": u"string",
                            u"index": u"not_analyzed"
                        },
                        u"document-definition__fields__{type}__validations__context__v1".format(type=self.type): {
                            u"type": u"string",
                            u"index": u"not_analyzed"
                        }
                    }
                }
            elif key == 'choices':
                mappings[u"document-definition__fields__{type}__choices__v1".format(type=self.type)] = {
                    u"type": u"object",
                    u"properties": {
                        u"document-definition__fields__{type}__choices__choice_name__v1".format(type=self.type): {
                            u"type": u"string",
                            u"fields": {
                                u"document-definition__fields__{type}__choices__choice_name__v1".format(
                                    type=self.type): {
                                    u"type": u"string"
                                },
                                u"raw__v1": {
                                    u"type": u"string",
                                    u"index": u"not_analyzed"
                                }
                            }
                        },
                        u"document-definition__fields__{type}__choices__default_value__v1".format(type=self.type): {
                            u"type": u"string",
                            u"fields": {
                                u"document-definition__fields__{type}__choices__default_value__v1".format(
                                    type=self.type): {
                                    u"type": u"string"
                                },
                                u"raw__v1": {
                                    u"type": u"string",
                                    u"index": u"not_analyzed"
                                }
                            }
                        }
                    }
                }
            else:
                field_name = u'document-definition__fields__{type}__{field}__v1'.format(
                    type=self.type,
                    field=key
                )
                if key in self.string_attributes:
                    mappings[field_name] = StringField.build_mapping(field_name)
                elif key in self.text_attributes:
                    mappings[field_name] = TextField.build_mapping()
                elif key in self.boolean_attributes:
                    mappings[field_name] = CheckField.build_mapping()
                elif key in self.number_attributes:
                    mappings[field_name] = NumberField.build_mapping(mode='integer')
                elif key == 'default':
                    if self.type == 'number':
                        mappings[field_name] = NumberField.build_mapping(mode='integer')
                    elif self.type == 'string':
                        mappings[field_name] = StringField.build_mapping(field_name)
                    elif self.type == 'text':
                        mappings[field_name] = TextField.build_mapping()
                    elif self.type == 'date':
                        mappings[field_name] = DateTimeField.build_mapping()
                    elif self.type == 'check':
                        mappings[field_name] = CheckField.build_mapping()
        return mappings


class StringField(Field):

    allowed_attributes = {
        u'add_summary',
        u'active',
        u'choices',
        u'default',
        u'hint',
        u'comment',
        u'display_name',
        u'max_length',
        u'min_length',
        u'type',
        u'name',
        u'doc_type',
        u'validations',
        u'embedded_into',
    }

    name = None
    default = None
    choices = None
    add_to_summary = None
    hint = None
    comment = None
    display_name = None
    max_length = None
    min_length = None
    validations = None
    is_autocomplete = None
    doc_type = None
    type = None
    version = None
    validation_errors = []
    field_data = {}
    embedded_into = None

    def __init__(self, **kwargs):
        """
        Document contains a list of fields, each with configuration for validation, db checks,
        and additional logic.

        *Attributes*

        * name
        * add_summary
        * choices
        * default
        * hint
        * comment
        * display_name

        :param args:
        :param kwargs:
        :return:
        """
        self.type = 'string'
        logger.debug(u'StringField :: kwargs: {}'.format(kwargs))
        self.field_data = kwargs
        not_validated_fields = filter(lambda x: x not in self.allowed_attributes, kwargs)
        if not_validated_fields:
            raise exceptions.XimpiaAPIException(_(u'Fields not validated: {}'.format(not_validated_fields)))
        for attr_name in kwargs:
            setattr(self, attr_name, kwargs[attr_name])
        if 'version' not in kwargs:
            self.version = settings.REST_FRAMEWORK['DEFAULT_VERSION']

    @classmethod
    def build_mapping(cls, field_name):
        """
        Return mapping that corresponds to this field, no matter if goes for document definition
        or structure for document

        :param field_name:
        :return:
        """
        return {
            'type': 'string',
            'fields': {
                field_name: {
                    'type': 'string'
                },
                'raw__v1': {
                    'type': 'string',
                    'index': 'not_analyzed'
                }
            }
        }

    def make_mapping(self):
        """
        Create the mapping structure for document to be created

        :return:
        """
        # We could set analyzer. Default analyzer??? International chars???
        # How we set version fields??? We get field versions for name
        mappings = {
            u'{}__{}__{}'.format(
                self.doc_type, self.name, self.version
            ): self.build_mapping(u'{doc_type}__{field_name}__{version}'.format(
                doc_type=self.doc_type,
                field_name=self.name,
                version=self.version))
            }
        if self.add_to_summary:
            mappings[u'copy_to'] = u'text__v1'
        if self.is_autocomplete:
            mappings[u'{}__{}'.format(self.name, self.version)][u'fields'][u'completion__v1'] = {
                u"type": u"{doc_tyoe}__{field_name}_completion".format(
                    doc_type=self.doc_type,
                    field_name=self.name
                ),
                u"analyzer": u"simple_whitespace",
                u"payloads": True,
                u"preserve_separators": True,
                u"preserve_position_increments": True,
                u"max_input_length": 50
            }
        return mappings

    def get_field_items(self):
        """
        Get field items

        :return:

        {
            'field': 'doc__field__v1',
            'field_name': 'field'
        }

        """
        return {
            'field': '{doc_type}__{field_name}__{version}'.format(
                doc_type=self.doc_type,
                field_name=self.name,
                version=self.version
            ),
            'field_name': self.name,
        }

    def get_physical(self, value):
        """
        Get physical field

        :param value:

        :return:
        """
        field_items = self.get_field_items()
        return {
            field_items['field']: value
        }

    def get_logical(self):
        """
        Get logical field

        :return:
        """
        field_items = self.get_field_items()
        return field_items['field_name']

    @classmethod
    def validate(cls, value, field_config, doc_config, patterns_data=None):
        """
        Run all validations for the field

        *Notes*

        * In case choices, validate against choice keys.
        * Run field validations
        * Run db checks through

        :param value: Field value
        :param field_config: Field config object
        :param doc_config: Document config object

        :return:
        """
        logger.debug(u'StringField.validate :: value: {} field_config: {} doc_config: {}'.format(
            value, field_config, doc_config
        ))
        check = Validator(True, {})
        # min_length and max_length for string
        name = field_config.get('name', 'general')
        min_length = field_config.get('min_length', None)
        max_length = field_config.get('max_length', None)
        field_choices = field_config.get('choices', None)
        validations = field_config.get('validations', None)
        if min_length:
            if len(value) < min_length:
                check.add_error(name, u'min length error')
        if max_length:
            if len(value) > max_length:
                check.add_error(name, u'max length error')
        if field_choices and value != '':
            # If we have some value in field, validate with choices
            choice_name = field_choices['name']
            choice_value = filter(lambda x: x['choice_item_name'] == value,
                                  doc_config['choices'][choice_name])
            if choice_value:
                if choice_value[0]['choice_item_name'] != value:
                    check.add_error(name, u'choice {} error'.format(choice_name))
            else:
                check.invalid()
        # field validations
        if validations:
            for validation_data in validations:
                validation_name = validation_data.get('name',
                                                      '{field_name}.{type}'.format(
                                                          field_name=field_config['name'],
                                                          type=validation_data['type']
                                                      ))
                value = patterns_data[validation_name]
                if not value:
                    check.add_error(name, u'Error in validation {}'.format(validation_name))
                    break
        return check


class NumberField(Field):

    allowed_attributes = {
        u'add_summary',
        u'default',
        u'hint',
        u'comment',
        u'display_name',
        u'type',
        u'name',
        u'min_value',
        u'max_value',
        u'only_positive',
        u'only_negative',
        u'doc_type',
        u'mode',
        u'validations',
        u'embedded_into',
    }

    allowed_modes = {'long', 'integer', 'short', 'byte', 'double', 'float'}

    type = None
    name = None
    default = None
    add_to_summary = None
    hint = None
    comment = None
    display_name = None
    validations = None
    is_autocomplete = None
    doc_type = None
    min_value = None
    max_value = None
    only_positive = None
    only_negative = None
    mode = None
    version = None
    validation_errors = []
    embedded_into = None

    def __init__(self, **kwargs):
        """
        Document contains a list of fields, each with configuration for validation, db checks,
        and additional logic.

        *Attributes*

        * name
        * add_summary
        * choices
        * default
        * hint
        * comment
        * mode: long|integer|short|byte|double|float. Default: long
        * display_name

        :param args:
        :param kwargs:
        :return:
        """
        logger.debug(u'NumberField :: kwargs: {}'.format(kwargs))
        self.type = 'number'
        self.field_data = kwargs
        not_validated_fields = filter(lambda x: x not in self.allowed_attributes, kwargs)
        if not_validated_fields:
            raise exceptions.XimpiaAPIException(_(u'Fields not validated: {}'.format(not_validated_fields)))
        for attr_name in kwargs:
            setattr(self, attr_name, kwargs[attr_name])
        if not self.mode:
            self.mode = 'long'
        if self.mode not in self.allowed_modes:
            raise exceptions.XimpiaAPIException(u'Number mode not allowed')
        if 'version' not in kwargs:
            self.version = settings.REST_FRAMEWORK['DEFAULT_VERSION']

    @classmethod
    def build_mapping(cls, mode='long'):
        return {
            'type': mode
        }

    def make_mapping(self):
        """
        Make Number mapping

        :return:
        """
        mappings = {
            u'{}__{}__{}'.format(
                self.doc_type, self.name, self.version
            ): {
                u'type': self.mode,
            }
        }
        if self.add_to_summary:
            mappings[u'copy_to'] = u'text__v1'
        if self.is_autocomplete:
            mappings[u'{}__{}'.format(self.name, self.version)][u'fields'][u'completion__v1'] = {
                u"type": u"{doc_tyoe}__{field_name}_completion".format(
                    doc_type=self.doc_type,
                    field_name=self.name
                ),
                u"analyzer": u"simple_whitespace",
                u"payloads": True,
                u"preserve_separators": True,
                u"preserve_position_increments": True,
                u"max_input_length": 50
            }
        return mappings

    def get_field_items(self):
        """
        Get field items

        :return:

        {
            'field': 'doc__field__v1',
            'field_name': 'field'
        }

        """
        return {
            'field': '{doc_type}__{field_name}__{version}'.format(
                doc_type=self.doc_type,
                field_name=self.name,
                version=self.version
            ),
            'field_name': self.name,
        }

    def get_physical(self, value):
        """
        Get physical field

        :param value:

        :return:
        """
        field_items = self.get_field_items()
        return {
            field_items['field']: value
        }

    def get_logical(self):
        """
        Get logical field

        :return:
        """
        field_items = self.get_field_items()
        return field_items['field_name']

    @classmethod
    def validate(cls, value, field_config, doc_config, patterns_data=None):
        """
        Validate field

        :param value:
        :param field_config:
        :param doc_config:
        :param patterns_data:
        :return:
        """
        check = Validator(True, {})
        name = field_config.get('name', 'general')
        min_value = field_config.get('min_value', None)
        max_value = field_config.get('max_value', None)
        only_positive = field_config.get('only_positive', None)
        only_negative = field_config.get('only_negative', None)
        validations = field_config.get('validations', None)
        if max_value and value > max_value:
            check.add_error(name, u'error max_value')
        if min_value and value < min_value:
            check.add_error(name, u'error min_value')
        if only_positive and value < 0:
            check.add_error(name, u'error only_positive')
        if only_negative and value > 0:
            check.add_error(name, u'error only_negative')
        if validations:
            for validation_data in validations:
                validation_name = validation_data.get('name',
                                                      '{field_name}.{type}'.format(
                                                          field_name=field_config['name'],
                                                          type=validation_data['type']
                                                      ))
                value = patterns_data[validation_name]
                if not value:
                    check.add_error(name, u'error validation {}'.format(validation_name))
                    break
        return check


class TextField(Field):

    allowed_attributes = {
        u'add_summary',
        u'default',
        u'hint',
        u'comment',
        u'display_name',
        u'type',
        u'name',
        u'doc_type',
        u'validations',
        u'max_length',
        u'min_length',
        u'embedded_into',
    }

    type = None
    name = None
    default = None
    add_to_summary = None
    hint = None
    comment = None
    display_name = None
    validations = None
    max_length = None
    min_length = None
    doc_type = None
    version = None
    validation_errors = []
    embedded_into = None

    def __init__(self, **kwargs):
        """
        Constructor

        :param kwargs:
        :return:
        """
        logger.debug(u'TextField :: kwargs: {}'.format(kwargs))
        self.field_data = kwargs
        not_validated_fields = filter(lambda x: x not in self.allowed_attributes, kwargs)
        if not_validated_fields:
            raise exceptions.XimpiaAPIException(_(u'Fields not validated: {}'.format(not_validated_fields)))
        for attr_name in kwargs:
            setattr(self, attr_name, kwargs[attr_name])
        if 'version' not in kwargs:
            self.version = settings.REST_FRAMEWORK['DEFAULT_VERSION']

    @classmethod
    def build_mapping(cls):
        """
        Return mapping that corresponds to this field, no matter if goes for document definition
        or structure for document

        :param field_name:
        :return:
        """
        return {
            'type': 'string',
        }

    def make_mapping(self):
        """
        Make Text mapping

        :return:
        """
        mappings = {
            u'{}__{}__{}'.format(
                self.doc_type, self.name, self.version
            ): {
                u'type': 'string',
            }
        }
        if self.add_to_summary:
            mappings[u'copy_to'] = u'text__v1'
        return mappings

    def get_field_items(self):
        """
        Get field items

        :return:

        {
            'field': 'doc__field__v1',
            'field_name': 'field'
        }

        """
        return {
            'field': '{doc_type}__{field_name}__{version}'.format(
                doc_type=self.doc_type,
                field_name=self.name,
                version=self.version
            ),
            'field_name': self.name,
        }

    def get_physical(self, value):
        """
        Get physical field

        :param value:

        :return:
        """
        field_items = self.get_field_items()
        return {
            field_items['field']: value
        }

    def get_logical(self):
        """
        Get logical field

        :return:
        """
        field_items = self.get_field_items()
        return field_items['field_name']

    @classmethod
    def validate(cls, value, field_config, doc_config, patterns_data=None):
        """
        Validate field

        :param value:
        :param field_config:
        :param doc_config:
        :param patterns_data:
        :return:
        """
        check = Validator(True, {})
        name = field_config.get('name', 'general')
        max_length = field_config.get('max_length', None)
        min_length = field_config.get('min_length', None)
        if max_length and len(value) > max_length:
            check.add_error(name, u'error max_length')
        if min_length and len(value) < min_length:
            check.add_error(name, u'error min_length')
        return check


class CheckField(Field):

    allowed_attributes = {
        u'hint',
        u'comment',
        u'default',
        u'display_name',
        u'type',
        u'name',
        u'doc_type',
        u'embedded_into',
    }

    type = None
    name = None
    default = None
    add_to_summary = None
    hint = None
    comment = None
    display_name = None
    validations = None
    doc_type = None
    version = None
    validation_errors = []
    embedded_into = None


    def __init__(self, **kwargs):
        """
        Constructor

        :param kwargs:
        :return:
        """
        logger.debug(u'CheckField :: kwargs: {}'.format(kwargs))
        self.type = 'check'
        self.field_data = kwargs
        not_validated_fields = filter(lambda x: x not in self.allowed_attributes, kwargs)
        if not_validated_fields:
            raise exceptions.XimpiaAPIException(_(u'Fields not validated: {}'.format(not_validated_fields)))
        for attr_name in kwargs:
            setattr(self, attr_name, kwargs[attr_name])
        if 'version' not in kwargs:
            self.version = settings.REST_FRAMEWORK['DEFAULT_VERSION']

    @classmethod
    def build_mapping(cls):
        return {
            'type': 'bool'
        }

    def make_mapping(self):
        """
        Make check mapping

        :return:
        """
        mappings = {
            u'{}__{}__{}'.format(
                self.doc_type, self.name, self.version
            ): {
                u'type': 'boolean',
            }
        }
        return mappings

    def get_field_items(self):
        """
        Get field items

        :return:

        {
            'field': 'doc__field__v1',
            'field_name': 'field'
        }

        """
        return {
            'field': '{doc_type}__{field_name}__{version}'.format(
                doc_type=self.doc_type,
                field_name=self.name,
                version=self.version
            ),
            'field_name': self.name,
        }

    def get_physical(self, value):
        """
        Get physical field

        :param value:

        :return:
        """
        field_items = self.get_field_items()
        return {
            field_items['field']: value
        }

    def get_logical(self):
        """
        Get logical field

        :return:
        """
        field_items = self.get_field_items()
        return field_items['field_name']

    @classmethod
    def validate(cls, value, field_config, doc_config, patterns_data=None):
        """
        Validate field

        :param value:
        :param field_config:
        :param doc_config:
        :param patterns_data:
        :return:
        """
        check = Validator(True, {})
        return check


class DateTimeField(Field):

    allowed_attributes = {
        u'hint',
        u'comment',
        u'display_name',
        u'type',
        u'name',
        u'doc_type',
        u'add_summary',
        u'default',
        u'min_datetime',
        u'max_datetime',
        u'is_create_date',
        u'is_timestamp',
        u'embedded_into',
    }

    type = None
    name = None
    add_to_summary = None
    hint = None
    comment = None
    display_name = None
    validations = None
    doc_type = None
    version = None
    min_datetime = None
    max_datetime = None
    default = None
    is_create_date = None
    is_timestamp = None
    validation_errors = []
    embedded_into = None

    def __init__(self, **kwargs):
        """
        Constructor

        :param kwargs:
        :return:
        """
        logger.debug(u'CheckField :: kwargs: {}'.format(kwargs))
        self.type = 'datetime'
        self.field_data = kwargs
        not_validated_fields = filter(lambda x: x not in self.allowed_attributes, kwargs)
        if not_validated_fields:
            raise exceptions.XimpiaAPIException(_(u'Fields not validated: {}'.format(not_validated_fields)))
        for attr_name in kwargs:
            setattr(self, attr_name, kwargs[attr_name])
        if 'version' not in kwargs:
            self.version = settings.REST_FRAMEWORK['DEFAULT_VERSION']

    @classmethod
    def build_mapping(cls):
        return {
            u'type': u'date',
            u"format": u"dateOptionalTime"
        }

    def make_mapping(self):
        """
        Make datetime mapping

        :return:
        """
        mappings = {
            u'{}__{}__{}'.format(
                self.doc_type, self.name, self.version
            ): {
                u'type': u'date',
                u"format": u"dateOptionalTime"
            }
        }
        return mappings

    def get_field_items(self):
        """
        Get field items

        :return:

        {
            'field': 'doc__field__v1',
            'field_name': 'field'
        }

        """
        return {
            'field': '{doc_type}__{field_name}__{version}'.format(
                doc_type=self.doc_type,
                field_name=self.name,
                version=self.version
            ),
            'field_name': self.name,
        }

    def get_physical(self, value):
        """
        Get physical field

        :param value:

        :return:
        """
        field_items = self.get_field_items()
        return {
            field_items['field']: value
        }

    def get_logical(self):
        """
        Get logical field

        :return:
        """
        field_items = self.get_field_items()
        return field_items['field_name']

    @classmethod
    def validate(cls, value, field_config, doc_config, patterns_data=None):
        """
        Validate field

        :param value:
        :param field_config:
        :param doc_config:
        :param patterns_data:
        :return:
        """
        check = Validator(True, {})
        name = field_config.get('name', 'general')
        min_datetime = field_config.get('min_datetime', None)
        max_datetime = field_config.get('max_datetime', None)
        is_create_date = field_config.get('is_create_date', None)
        is_timestamp = field_config.get('is_timestamp', None)
        default = field_config.get('default', None)
        if (default or value) and (is_timestamp or is_create_date):
            check.add_error(name,
                            u'Timestamp or create date defined and I receive also "default" or "value" for field')
        if not value:
            value = default
        # Check date ranges
        date_format = '%Y-%m-%dT%H:%M:%S'
        value_obj = datetime.strptime(value, date_format)
        if min_datetime:
            min_obj = datetime.strptime(min_datetime, date_format)
            if value_obj < min_obj:
                check.add_error(name, u'error min_datetime')
        if max_datetime:
            max_obj = datetime.strptime(max_datetime, date_format)
            if value_obj > max_obj:
                check.add_error(name, u'error max_datetime')
        return check


class MapField(Field):

    allowed_attributes = {
        u'hint',
        u'comment',
        u'display_name',
        u'type',
        u'name',
        u'doc_type',
        u'add_summary',
        u'items',
        u'embedded_into',
    }

    type = None
    name = None
    add_to_summary = None
    hint = None
    comment = None
    display_name = None
    doc_type = None
    version = None
    items = None
    embedded_into = None

    def __init__(self, **kwargs):
        """
        Constructor

        Logical
        =======
        {
          count: 34,
          my_section: {
            name1: "James",
            profile: {
              last_name: "Stuart",
              age: 34
            }
          }
        }

        Document Definition
        ===================
        {
          my_section: {
            type: map,
            display_name: My Section
            items: {
              name1: {
                type: string
                ...
              },
              name2: {
                type: map,
                items: {
                }
              }
            }
          }
        }

        Mappings
        ========
        type__my_section__v1: {
          type: object
          properties: {
            type__my_section__name1__v1: {
              type: string,
              fields: {
                ...
              }
            },
            type__my_section__name2__v1: {
              type: object,
              properties: {
              }
            }
          }
        }

        :param kwargs:
        :return:
        """
        logger.debug(u'MapField :: kwargs: {}'.format(kwargs))
        self.field_data = kwargs
        not_validated_fields = filter(lambda x: x not in self.allowed_attributes, kwargs)
        if not_validated_fields:
            raise exceptions.XimpiaAPIException(_(u'Fields not validated: {}'.format(not_validated_fields)))
        for attr_name in kwargs:
            setattr(self, attr_name, kwargs[attr_name])
        if 'version' not in kwargs:
            self.version = settings.REST_FRAMEWORK['DEFAULT_VERSION']
        self.type = 'map'

    def make_mapping(self):
        """
        Make datetime mapping

        :return:
        """
        object_properties = {}
        for field_data_key in self.items:
            field_data = self.items[field_data_key]
            field_data['name'] = field_data_key
            logger.debug(u'MapField.make_mapping :: field_data: {}'.format(field_data))
            item_doc_type = u'{}__{}'.format(self.doc_type, self.name)
            module = 'document.fields'
            instance = __import__(module)
            for comp in module.split('.')[1:]:
                instance = getattr(instance, comp)
            logger.debug(u'MapField.make_mapping :: instance: {}'.format(instance))
            field_class = getattr(instance, '{}Field'.format(field_data['type'].capitalize()))
            field_data['doc_type'] = item_doc_type
            field_instance = field_class(**field_data)
            field_mapping = field_instance.make_mapping()
            logger.debug(u'MapField.make_mapping :: field_mapping: {}'.format(field_mapping))
            object_properties.update(field_mapping)
        mappings = {
            u'{}__{}__{}'.format(
                self.doc_type, self.name, self.version
            ): {
                u'type': 'object',
                u'properties': object_properties
            }
        }
        return mappings

    def get_field_items(self):
        """
        Get field items

        :return:

        {
            'field': 'doc__field__v1',
            'field_name': 'field'
        }

        """
        return {
            'field': '{doc_type}__{field_name}__{version}'.format(
                doc_type=self.doc_type,
                field_name=self.name,
                version=self.version
            ),
            'field_name': self.name,
        }

    def get_physical(self, values):
        """
        Get physical field

        We need: logical -> physical

        Return whole physical structure for all fields inside having logical

        :param values:
        {
          my_section: {
            name1: "James",
            profile: {
              last_name: "Stuart",
              age: 34
            }
          }
        }
        This provides values for fields

        :return:
        {
          type__my_section__v1: {
            type__my_section__name1__v1: "James",
            type__my_section__profile__v1: {
              type__my_section__profile__last_name__v1: "Stuart",
              type__my_section__profile__age__v1: 34
            }
          }
        }

        """
        logger.debug(u'MapField.get_physical :: values: {}'.format(values))
        logger.debug(u'MapField.get_physical :: name: {}'.format(self.name))
        items_map = {}
        for field_data_key in self.items:
            field_data = self.items[field_data_key]
            field_data['name'] = field_data_key
            logger.debug(u'MapField.get_physical :: field_data: {}'.format(field_data))
            item_doc_type = u'{}__{}'.format(self.doc_type, self.name)
            module = 'document.fields'
            instance = __import__(module)
            for comp in module.split('.')[1:]:
                instance = getattr(instance, comp)
            logger.debug(u'MapField.get_physical :: instance: {}'.format(instance))
            field_class = getattr(instance, '{}Field'.format(field_data['type'].capitalize()))
            field_data['doc_type'] = item_doc_type
            field_instance = field_class(**field_data)
            logger.debug(u'MapField.get_physical :: field_instance: {}'.format(field_instance))
            logger.debug(u'MapField.get_physical :: values: {}'.format(values))
            if self.name in values:
                target_value = values[self.name][field_data['name']]
            else:
                target_value = values[field_data['name']]
            item_physical = field_instance.get_physical(
                target_value
            )
            items_map.update(item_physical)
        physical = {
            self.get_field_items()['field']: items_map
        }
        return physical

    @classmethod
    def validate(cls, values, field_config, doc_config, patterns_data=None):
        """
        Validate field: We call validate for all fields

        :param values:
        :param field_config:
        :param doc_config:
        :param patterns_data:
        :return:
        """
        check = Validator(True, {})
        items = field_config.get('items', None)
        name = field_config.get('name', 'general')
        logger.debug(u'MapField.validate :: field_config: {}'.format(field_config))
        logger.debug(u'MapField.validate :: items: {}'.format(items))
        logger.debug(u'MapField.validate :: name: {}'.format(name))
        doc_type = doc_config.get('doc_type', None)
        for field_data_key in items:
            field_data = items[field_data_key]
            field_data['name'] = field_data_key
            logger.debug(u'MapField.validate :: key: {}'.format(field_data_key))
            logger.debug(u'MapField.validate :: field_data: {}'.format(field_data))
            item_doc_type = u'{}__{}'.format(doc_type, name)
            module = 'document.fields'
            instance = __import__(module)
            for comp in module.split('.')[1:]:
                instance = getattr(instance, comp)
            logger.debug(u'MapField.validate :: instance: {}'.format(instance))
            field_class = getattr(instance, '{}Field'.format(field_data['type'].capitalize()))
            field_data['doc_type'] = item_doc_type
            field_instance = field_class(**field_data)
            logger.debug(u'MapField.validate :: field_instance: {}'.format(field_instance))
            if name in values:
                value = values[name][field_data['name']]
            else:
                value = values[field_data['name']]
            # value = values[name][field_data['name']]
            field_pattern_data = None
            if patterns_data and field_data_key in patterns_data:
                field_pattern_data = patterns_data[field_data_key]
            check_item = field_instance.validate(value, field_data, doc_config,
                                                 patterns_data=field_pattern_data)
            if not check_item:
                check.add_error(name, check_item.errors.values()[0])
            logger.debug(u'MapField.validate :: item check: {}'.format(check))
        logger.debug(u'MapField.validate :: return check: {}'.format(check))
        return check


class MapListField(Field):

    allowed_attributes = {
        u'hint',
        u'comment',
        u'display_name',
        u'type',
        u'name',
        u'doc_type',
        u'add_summary',
        u'items',
        u'embedded_into',
    }

    type = None
    name = None
    add_to_summary = None
    hint = None
    comment = None
    display_name = None
    doc_type = None
    version = None
    items = None
    embedded_into = None

    def __init__(self, **kwargs):
        """
        Constructor

        Logical
        =======
        {
          count: 34,
          my_sections: [
            {
              name1: "James",
              profile: {
                last_name: "Stuart",
                age: 34
              }
            },
            {

            }
          ]
        }

        Document Definition
        ===================
        {
          my_section: {
            type: map-list,
            display_name: My Section
            items: [
              {
                name1: {
                  type: string
                  ...
                },
                name2: {
                  type: map,
                  items: {
                  }
                }
              },
              {
              ...
              }
            ]
          }
        }

        Mappings
        ========
        type__my_section__v1: {
          type: nexted
          properties: {
            type__my_section__name1__v1: {
              type: string,
              fields: {
                ...
              }
            },
            type__my_section__name2__v1: {
              type: object,
              properties: {
              }
            }
          }
        }

        :param kwargs:
        :return:
        """
        logger.debug(u'MapListField :: kwargs: {}'.format(kwargs))
        self.field_data = kwargs
        not_validated_fields = filter(lambda x: x not in self.allowed_attributes, kwargs)
        if not_validated_fields:
            raise exceptions.XimpiaAPIException(_(u'Fields not validated: {}'.format(not_validated_fields)))
        for attr_name in kwargs:
            setattr(self, attr_name, kwargs[attr_name])
        if 'version' not in kwargs:
            self.version = settings.REST_FRAMEWORK['DEFAULT_VERSION']
        self.type = 'map-list'

    def make_mapping(self):
        """
        Make datetime mapping

        :return:
        """
        object_properties = {}
        for field_data_key in self.items:
            field_data = self.items[field_data_key]
            field_data['name'] = field_data_key
            logger.debug(u'MapListField.make_mapping :: field_data: {}'.format(field_data))
            item_doc_type = u'{}__{}'.format(self.doc_type, self.name)
            module = 'document.fields'
            instance = __import__(module)
            for comp in module.split('.')[1:]:
                instance = getattr(instance, comp)
            logger.debug(u'MapListField.make_mapping :: instance: {}'.format(instance))
            field_class = getattr(instance, '{}Field'.format(field_data['type'].capitalize()))
            field_data['doc_type'] = item_doc_type
            field_instance = field_class(**field_data)
            field_mapping = field_instance.make_mapping()
            logger.debug(u'MapListField.make_mapping :: field_mapping: {}'.format(field_mapping))
            object_properties.update(field_mapping)
        mappings = {
            u'{}__{}__{}'.format(
                self.doc_type, self.name, self.version
            ): {
                u'type': 'nested',
                u"include_in_parent": True,
                u"dynamic": False,
                u'properties': object_properties
            }
        }
        return mappings

    def get_field_items(self):
        """
        Get field items

        :return:

        {
            'field': 'doc__field__v1',
            'field_name': 'field'
        }

        """
        return {
            'field': '{doc_type}__{field_name}__{version}'.format(
                doc_type=self.doc_type,
                field_name=self.name,
                version=self.version
            ),
            'field_name': self.name,
        }

    def get_physical(self, values):
        """
        Get physical field

        We need: logical -> physical

        Return whole physical structure for all fields inside having logical

        :param values:
        {
          my_sections: [
            {
              name1: "James",
              profile: {
                last_name: "Stuart",
                age: 34
              }
            },
            {
            ...
            }
          ]
        }
        This provides values for fields

        :return:
        {
          type__my_sections__v1: [
            {
              type__my_section__name1__v1: "James",
              type__my_section__profile__v1: {
                type__my_section__profile__last_name__v1: "Stuart",
                type__my_section__profile__age__v1: 34
              }
            },
            {
            ...
            }
          ]
        }

        """
        logger.debug(u'MapListField.get_physical :: values: {}'.format(values))
        logger.debug(u'MapListField.get_physical :: name: {}'.format(self.name))
        items_list = []
        for value_item in values[self.name]:
            logger.debug(u'MapListField.get_physical :: value_item: {}'.format(value_item))
            items_map = {}
            for field_data_key in self.items:
                field_data = self.items[field_data_key]
                field_data['name'] = field_data_key
                logger.debug(u'MapListField.get_physical :: field_data: {}'.format(field_data))
                item_doc_type = u'{}__{}'.format(self.doc_type, self.name)
                module = 'document.fields'
                instance = __import__(module)
                for comp in module.split('.')[1:]:
                    instance = getattr(instance, comp)
                logger.debug(u'MapListField.get_physical :: instance: {}'.format(instance))
                field_class = getattr(instance, '{}Field'.format(field_data['type'].capitalize()))
                field_data['doc_type'] = item_doc_type
                field_instance = field_class(**field_data)
                logger.debug(u'MapListField.get_physical :: field_instance: {}'.format(field_instance))
                logger.debug(u'MapListField.get_physical :: values: {}'.format(values))
                if self.name in value_item:
                    target_value = value_item[self.name][field_data['name']]
                else:
                    target_value = value_item[field_data['name']]
                item_physical = field_instance.get_physical(
                    target_value
                )
                items_map.update(item_physical)
            items_list.append(items_map)
        physical = {
            self.get_field_items()['field']: items_list
        }
        return physical

    @classmethod
    def validate(cls, values, field_config, doc_config, patterns_data=None):
        """
        Validate field: We call validate for all fields

        :param values:
        :param field_config:
        :param doc_config:
        :param patterns_data:
        :return:
        """
        check = Validator(True, {})
        items = field_config.get('items', None)
        name = field_config.get('name', None)
        logger.debug(u'MapListField.validate :: field_config: {}'.format(field_config))
        logger.debug(u'MapListField.validate :: items: {}'.format(items))
        logger.debug(u'MapListField.validate :: name: {}'.format(name))
        doc_type = doc_config.get('', None)
        for value_item in values[name]:
            for field_data_key in items:
                field_data = items[field_data_key]
                field_data['name'] = field_data_key
                logger.debug(u'MapListField.validate :: key: {}'.format(field_data_key))
                logger.debug(u'MapListField.validate :: field_data: {}'.format(field_data))
                item_doc_type = u'{}__{}'.format(doc_type, name)
                module = 'document.fields'
                instance = __import__(module)
                for comp in module.split('.')[1:]:
                    instance = getattr(instance, comp)
                logger.debug(u'MapListField.validate :: instance: {}'.format(instance))
                field_class = getattr(instance, '{}Field'.format(field_data['type'].capitalize()))
                field_data['doc_type'] = item_doc_type
                field_instance = field_class(**field_data)
                logger.debug(u'MapListField.validate :: field_instance: {}'.format(field_instance))
                if name in value_item:
                    value = value_item[name][field_data['name']]
                else:
                    value = value_item[field_data['name']]
                field_pattern_data = None
                if patterns_data and field_data_key in patterns_data:
                    field_pattern_data = patterns_data[field_data_key]
                check_item = field_instance.validate(value, field_data, doc_config,
                                                     patterns_data=field_pattern_data)
                if not check_item:
                    check.add_error(name, check_item.errors.values()[0])
                logger.debug(u'MapListField.validate :: item check: {}'.format(check))
        logger.debug(u'MapListField.validate :: return check: {}'.format(check))
        return check


class ListField(Field):

    allowed_attributes = {
        u'hint',
        u'comment',
        u'display_name',
        u'type',
        u'name',
        u'doc_type',
        u'add_summary',
        u'mode',
        u'embedded_into',
    }

    type = None
    name = None
    add_to_summary = None
    hint = None
    comment = None
    display_name = None
    doc_type = None
    version = None
    mode = None
    items = None
    embedded_into = None

    def __init__(self, **kwargs):
        """
        Constructor

        :param kwargs:
        :return:
        """
        logger.debug(u'ListField :: kwargs: {}'.format(kwargs))
        self.field_data = kwargs
        item_type = kwargs['type'].split('<')[1][:-1]
        if item_type == 'string':
            allowed_attributes = StringField.allowed_attributes
        elif item_type == 'date':
            allowed_attributes = DateTimeField.allowed_attributes
        elif item_type == 'number':
            allowed_attributes = NumberField.allowed_attributes
        elif item_type == 'check':
            allowed_attributes = CheckField.allowed_attributes
        else:
            raise exceptions.XimpiaAPIException(_(u'Type not supported'))
        not_validated_fields = filter(lambda x: x not in allowed_attributes, kwargs)
        if not_validated_fields:
            raise exceptions.XimpiaAPIException(_(u'Fields not validated: {}'.format(not_validated_fields)))
        for attr_name in kwargs:
            setattr(self, attr_name, kwargs[attr_name])
        if 'version' not in kwargs:
            self.version = settings.REST_FRAMEWORK['DEFAULT_VERSION']
        self.type = 'list'

    def make_mapping(self):
        """
        Make mapping

        :return:
        """
        item_type = self.type.split('<')[1][:-1]
        mappings = None
        if item_type == 'date':
            mappings = {
                u'{}__{}__{}'.format(
                    self.doc_type, self.name, self.version
                ): {
                    'type': 'date',
                    "format": "dateOptionalTime"
                }
            }
        elif item_type == 'string':
            mappings = {
                u'{}__{}__{}'.format(
                    self.doc_type, self.name, self.version
                ): {
                    'type': 'string',
                    'fields': {
                        u'{}__{}__{}'.format(
                            self.doc_type, self.name, self.version
                        ): {
                            'type': 'string'
                        },
                        'raw__v1': {
                            'type': 'string',
                            'index': 'not_analyzed'
                        }
                    }
                }
            }
        elif item_type == 'number':
            mappings = {
                u'{}__{}__{}'.format(
                    self.doc_type, self.name, self.version
                ): {
                    u'type': self.mode,
                }
            }
        elif item_type == 'check':
            mappings = {
                u'{}__{}__{}'.format(
                    self.doc_type, self.name, self.version
                ): {
                    u'type': 'boolean',
                }
            }
        if mappings:
            if self.add_to_summary:
                mappings[u'copy_to'] = u'text__v1'
            return mappings

    def get_field_items(self):
        """
        Get field items

        :return:

        {
            'field': 'doc__field__v1',
            'field_name': 'field'
        }

        """
        return {
            'field': '{doc_type}__{field_name}__{version}'.format(
                doc_type=self.doc_type,
                field_name=self.name,
                version=self.version
            ),
            'field_name': self.name,
        }

    def get_physical(self, values):
        """
        Get physical field

        We need: logical -> physical

        Return whole physical structure for all fields inside having logical

        :param values:

        :return:

        """
        return {
            self.get_field_items()['field']: values
        }

    @classmethod
    def validate(cls, values, field_config, doc_config, patterns_data=None):
        """
        Validate field: We call validate for all fields

        :param values:
        :param field_config:
        :param doc_config:
        :param patterns_data:
        :return:
        """
        check = Validator(True, {})
        name = field_config.get('name', None)
        type_ = field_config.get('type', None)
        item_type = type_.split('<')[1][:-1]
        if item_type == 'string':
            for value in values:
                logger.debug(u'ListField.validate :: value: {}'.format(value))
                check_field = StringField.validate(value, field_config, doc_config,
                                                   patterns_data=patterns_data)
                if not check_field:
                    check.add_error(name, check_field.errors.values()[0] + u' value: {}'.format(value))
        elif item_type == 'number':
            for value in values:
                check_field = NumberField.validate(value, field_config, doc_config,
                                                   patterns_data=patterns_data)
                if not check_field:
                    check.add_error(name, check_field.errors.values()[0] + u' value: {}'.format(value))
        elif item_type == 'date':
            for value in values:
                check_field = DateTimeField.validate(value, field_config, doc_config,
                                                     patterns_data=patterns_data)
                if not check_field:
                    check.add_error(name, check_field.errors.values()[0] + u' value: {}'.format(value))
        return check


class LinkField(Field):

    allowed_attributes = {
        u'hint',
        u'comment',
        u'display_name',
        u'type',
        u'name',
        u'doc_type',
        u'add_summary',
        u'type_remote',
        u'app',
        u'embedded_into',
    }

    type = None
    name = None
    add_to_summary = None
    hint = None
    comment = None
    display_name = None
    doc_type = None
    version = None
    type_remote = None
    app = None
    embedded_into = None

    def __init__(self, **kwargs):
        """
        Constructor

        Logical
        =======
        {doc_type}: {
          "id": "idshhjds77787LL"
        }

        Physical
        ========
        {doc_type}__v1: {
          "id": "",
          ... [ Rest of document fields ]
        }

        Mapping
        =======
        We get from document type mapping

        :param kwargs:
        :return:
        """
        logger.debug(u'LinkField :: kwargs: {}'.format(kwargs))
        self.field_data = kwargs
        not_validated_fields = filter(lambda x: x not in self.allowed_attributes, kwargs)
        if not_validated_fields:
            raise exceptions.XimpiaAPIException(_(u'Fields not validated: {}'.format(not_validated_fields)))
        for attr_name in kwargs:
            setattr(self, attr_name, kwargs[attr_name])
        if 'version' not in kwargs:
            self.version = settings.REST_FRAMEWORK['DEFAULT_VERSION']
        self.doc_type = kwargs.get('name', None)
        self.type = 'link'

    def make_mapping(self):
        """
        Make mapping

        :return:
        """
        mappings = {
            u'{}__{}'.format(
                self.doc_type, self.version
            ): {
                'type': 'object',
                'properties': {
                    'id': {
                        'type': 'string',
                        'index': 'not_analyzed'
                    }
                }
            }
        }
        return mappings

    def get_field_items(self):
        """
        Get field items

        :return:

        {
            'field': 'doc__field__v1',
            'field_name': 'field'
        }

        """
        return {
            'field': '{doc_type}__{version}'.format(
                doc_type=self.doc_type,
                version=self.version
            ),
            'field_name': self.doc_type,
        }

    def get_physical(self, values):
        """
        Get physical field

        We need: logical -> physical

        Return whole physical structure for all fields inside having logical

        :param values:

        :return:

        """
        return {
            self.get_field_items()['field']: values
        }

    @classmethod
    def validate(cls, value, field_config, doc_config, patterns_data=None):
        """
        Validate field: We check id exists for document type

        :param value:
        :param field_config:
        :param doc_config:
        :param patterns_data:
        :return:
        """
        check = Validator(True, {})
        name = field_config.get('name', 'general')
        value = patterns_data['exists']
        if not value:
            check.add_error(name, u'Error in validation {}'.format('exists'))
        return check


class LinksField(Field):

    allowed_attributes = {
        u'hint',
        u'comment',
        u'display_name',
        u'type',
        u'name',
        u'field_name',
        u'doc_type',
        u'add_summary',
        u'type_remote',
        u'app',
        u'embedded_into',
    }

    type = None
    name = None
    add_to_summary = None
    hint = None
    comment = None
    display_name = None
    doc_type = None
    version = None
    field_name = None
    type_remote = None
    app = None
    embedded_into = None

    def __init__(self, **kwargs):
        """
        Constructor

        Logical
        =======
        {doc_type}: {
          "ids": ["idshhjds77787LL", "28982jjkKK"]
        }

        Physical
        ========
        {doc_type}__v1: [
          {
            "id": "",
            ... [ Rest of document fields ]
          }
        ]

        Mapping
        =======
        We get from document type mapping

        :param kwargs:
        :return:
        """
        logger.debug(u'LinkField :: kwargs: {}'.format(kwargs))
        self.field_data = kwargs
        not_validated_fields = filter(lambda x: x not in self.allowed_attributes, kwargs)
        if not_validated_fields:
            raise exceptions.XimpiaAPIException(_(u'Fields not validated: {}'.format(not_validated_fields)))
        for attr_name in kwargs:
            setattr(self, attr_name, kwargs[attr_name])
        if 'version' not in kwargs:
            self.version = settings.REST_FRAMEWORK['DEFAULT_VERSION']
        self.doc_type = kwargs.get('name', None)
        self.type = 'links'

    def make_mapping(self):
        """
        Make mapping

        :return:
        """
        mappings = {
            u'{}__{}'.format(
                self.field_name, self.version
            ): {
                'type': 'nested',
                "include_in_parent": True,
                "dynamic": False,
                'properties': {
                    'id': {
                        'type': 'string',
                        'index': 'not_analyzed'
                    }
                }
            }
        }
        return mappings

    def get_field_items(self):
        """
        Get field items

        :return:

        {
            'field': 'doc__field__v1',
            'field_name': 'field'
        }

        """
        return {
            'field': '{field_name}__{version}'.format(
                field_name=self.field_name,
                version=self.version
            ),
            'field_name': self.field_name,
        }

    def get_physical(self, values):
        """
        Get physical field

        We need: logical -> physical

        Return whole physical structure for all fields inside having logical

        :param values:

        :return:

        """
        return {
            self.get_field_items()['field']: map(lambda x: {
                'id': x
            }, values['ids'])
        }

    @classmethod
    def validate(cls, values, field_config, doc_config, patterns_data=None):
        """
        Validate field: We check id exists for document type

        :param values:
        :param field_config:
        :param doc_config:
        :param patterns_data:
        :return:
        """
        check = Validator(True, {})
        name = field_config.get('name', 'general')
        for value in patterns_data['exists'].values():
            if not value:
                check.add_error(name, u'Error in validation {}'.format('exists'))
        return check