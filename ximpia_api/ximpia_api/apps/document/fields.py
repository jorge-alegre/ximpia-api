import logging

from django.conf import settings
from django.utils.translation import ugettext as _
from django.utils.text import slugify

from base import exceptions
from document import Document

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
            self.version = settings.REST_FRAMEWORK.get['DEFAULT_VERSION']

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

    def get_physical(self):
        """
        Get physical field

        :return:
        """
        field_items = self.get_field_items()
        return field_items['field']

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
            self.version = settings.REST_FRAMEWORK.get['DEFAULT_VERSION']

    def make_mapping(self):
        """
        Make Number mapping

        :param version:
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

    def get_physical(self):
        """
        Get physical field

        :return:
        """
        field_items = self.get_field_items()
        return field_items['field']

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
            self.version = settings.REST_FRAMEWORK.get['DEFAULT_VERSION']

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

    def get_physical(self):
        """
        Get physical field

        :return:
        """
        field_items = self.get_field_items()
        return field_items['field']

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
