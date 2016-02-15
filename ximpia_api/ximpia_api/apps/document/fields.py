import logging
from datetime import datetime

from django.conf import settings
from django.utils.translation import ugettext as _

from base import exceptions

__author__ = 'jorgealegre'

logger = logging.getLogger(__name__)


class StringField(object):

    allowed_attributes = {
        u'add_summary',
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
        logger.debug(u'StringField :: kwargs: {}'.format(kwargs))
        not_validated_fields = filter(lambda x: x not in self.allowed_attributes, kwargs)
        if not_validated_fields:
            raise exceptions.XimpiaAPIException(_(u'Fields not validated: {}'.format(not_validated_fields)))
        for attr_name in kwargs:
            setattr(self, attr_name, kwargs[attr_name])
        if 'version' not in kwargs:
            self.version = settings.REST_FRAMEWORK['DEFAULT_VERSION']

    def make_mapping(self):
        """
        Create the mapping structure to create mappings and update mappings

        :return:
        """
        # We could set analyzer. Default analyzer??? International chars???
        # How we set version fields??? We get field versions for name
        mappings = {
            u'{}__{}__{}'.format(
                self.doc_type, self.name, self.version
            ): {
                u'type': u'string',
                u'fields': {
                    u'{doc_type}__{field_name}__{version}'.format(
                        doc_type=self.doc_type,
                        field_name=self.name,
                        version=self.version): {
                            u'type': u'string'
                    },
                    u'raw__{version}'.format(version=self.version): {
                        u'type': u'string',
                        u'index': u'not_analyzed'
                    }
                }
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
        check = True
        # min_length and max_length for string
        min_length = field_config.get('min_length', None)
        max_length = field_config.get('max_length', None)
        field_choices = field_config.get('choices', None)
        validations = field_config.get('validations', None)
        if min_length:
            if len(value) < min_length:
                check = False
                # logger.debug(u'StringField.validate :: min length error!')
        if max_length:
            if len(value) > max_length:
                check = False
                # logger.debug(u'StringField.validate :: max length error!')
        if field_choices and value != '':
            # If we have some value in field, validate with choices
            choice_name = field_choices['choice_name']
            choice_value = filter(lambda x: x['choice_item_name'] == value,
                                  doc_config['choices'][choice_name])
            if choice_value:
                if choice_value[0]['choice_item_name'] != value:
                    check = False
                    # logger.debug(u'StringField.validate :: choice {} error!'.format(choice_name))
            else:
                check = False
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
                    check = False
                    break
        return check


class NumberField(object):

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
        check = True
        min_value = field_config.get('min_value', None)
        max_value = field_config.get('max_value', None)
        only_positive = field_config.get('only_positive', None)
        only_negative = field_config.get('only_negative', None)
        validations = field_config.get('validations', None)
        if max_value and value > max_value:
            check = False
        if min_value and value < min_value:
            check = False
        if only_positive and value < 0:
            check = False
        if only_negative and value > 0:
            check = False
        if validations:
            for validation_data in validations:
                validation_name = validation_data.get('name',
                                                      '{field_name}.{type}'.format(
                                                          field_name=field_config['name'],
                                                          type=validation_data['type']
                                                      ))
                value = patterns_data[validation_name]
                if not value:
                    check = False
                    break
        return check


class TextField(object):

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

    def __init__(self, **kwargs):
        """
        Constructor

        :param kwargs:
        :return:
        """
        logger.debug(u'TextField :: kwargs: {}'.format(kwargs))
        not_validated_fields = filter(lambda x: x not in self.allowed_attributes, kwargs)
        if not_validated_fields:
            raise exceptions.XimpiaAPIException(_(u'Fields not validated: {}'.format(not_validated_fields)))
        for attr_name in kwargs:
            setattr(self, attr_name, kwargs[attr_name])
        if 'version' not in kwargs:
            self.version = settings.REST_FRAMEWORK['DEFAULT_VERSION']

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
        check = True
        max_length = field_config.get('max_length', None)
        min_length = field_config.get('min_length', None)
        if max_length and len(value) > max_length:
            check = False
        if min_length and len(value) < min_length:
            check = False
        return check


class CheckField(object):

    allowed_attributes = {
        u'hint',
        u'comment',
        u'default',
        u'display_name',
        u'type',
        u'name',
        u'doc_type',
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

    def __init__(self, **kwargs):
        """
        Constructor

        :param kwargs:
        :return:
        """
        logger.debug(u'CheckField :: kwargs: {}'.format(kwargs))
        not_validated_fields = filter(lambda x: x not in self.allowed_attributes, kwargs)
        if not_validated_fields:
            raise exceptions.XimpiaAPIException(_(u'Fields not validated: {}'.format(not_validated_fields)))
        for attr_name in kwargs:
            setattr(self, attr_name, kwargs[attr_name])
        if 'version' not in kwargs:
            self.version = settings.REST_FRAMEWORK['DEFAULT_VERSION']

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
        check = True
        return check


class DateTimeField(object):

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

    def __init__(self, **kwargs):
        """
        Constructor

        :param kwargs:
        :return:
        """
        logger.debug(u'CheckField :: kwargs: {}'.format(kwargs))
        not_validated_fields = filter(lambda x: x not in self.allowed_attributes, kwargs)
        if not_validated_fields:
            raise exceptions.XimpiaAPIException(_(u'Fields not validated: {}'.format(not_validated_fields)))
        for attr_name in kwargs:
            setattr(self, attr_name, kwargs[attr_name])
        if 'version' not in kwargs:
            self.version = settings.REST_FRAMEWORK['DEFAULT_VERSION']

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
        check = True
        min_datetime = field_config.get('min_datetime', None)
        max_datetime = field_config.get('max_datetime', None)
        is_create_date = field_config.get('is_create_date', None)
        is_timestamp = field_config.get('is_timestamp', None)
        default = field_config.get('default', None)
        if (default or value) and (is_timestamp or is_create_date):
            check = False
        if not value:
            value = default
        # Check date ranges
        date_format = '%Y-%m-%dT%H:%M:%S'
        value_obj = datetime.strptime(value, date_format)
        if min_datetime:
            min_obj = datetime.strptime(min_datetime, date_format)
            if value_obj < min_obj:
                check = False
        if max_datetime:
            max_obj = datetime.strptime(max_datetime, date_format)
            if value_obj > max_obj:
                check = False
        return check


class MapField(object):

    allowed_attributes = {
        u'hint',
        u'comment',
        u'display_name',
        u'type',
        u'name',
        u'doc_type',
        u'add_summary',
        u'items',
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
        not_validated_fields = filter(lambda x: x not in self.allowed_attributes, kwargs)
        if not_validated_fields:
            raise exceptions.XimpiaAPIException(_(u'Fields not validated: {}'.format(not_validated_fields)))
        for attr_name in kwargs:
            setattr(self, attr_name, kwargs[attr_name])
        if 'version' not in kwargs:
            self.version = settings.REST_FRAMEWORK['DEFAULT_VERSION']

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
        check = True
        items = field_config.get('items', None)
        name = field_config.get('name', None)
        logger.debug(u'MapField.validate :: field_config: {}'.format(field_config))
        logger.debug(u'MapField.validate :: items: {}'.format(items))
        logger.debug(u'MapField.validate :: name: {}'.format(name))
        doc_type = doc_config.get('', None)
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
            value = values[name][field_data['name']]
            field_pattern_data = None
            if patterns_data and field_data_key in patterns_data:
                field_pattern_data = patterns_data[field_data_key]
            check = field_instance.validate(value, field_data, doc_config, patterns_data=field_pattern_data)
            logger.debug(u'MapField.validate :: item check: {}'.format(check))
        logger.debug(u'MapField.validate :: return check: {}'.format(check))
        return check
