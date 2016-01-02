
from django.conf import settings
from django.utils.translation import ugettext as _
from django.utils.text import slugify

from base import exceptions
from document import Document

__author__ = 'jorgealegre'


u"""
Info on how document definition will work

Create Document Definition
==========================

This is simple example of just status with choices definition

String Field
------------

Here we see need to reference other values, which is made in python code by using method, variable, etc...
Would be good to have something generic. Need for choices, default values, etc...

Here ref: is reserved symbol to make reference anywhere in system. Definition is on the target item. After ref:
we have a path.

hint, display_name and other fields that are international chars would go somewhere where guys can translate easily.
Translation not defined in the document definition. We have a list of internationalized attribute names.

{
    'status': {
        'type': 'string',
        'choices': 'ref:choices.status',
        'default': 'ref:choices.draft',
        'hint': 'Content status for documents',
        'display_name': 'Status',
        'max_length': 100,
        'min_length': 25
    }
}

You can also define defaults relative to settings

{
    'place': {
        'type': 'string',
        'default': 'ref:settings.places.coffee_shop',
    }
}

JSON structure bellow 'status' would be document field definition.

field = StringField(**status_definition)

This way we build document definition with all fields, and we can generate ES mappings for all fields
in a document, check validations, etc...

Validations:
We would have a list of validation rules, that would be parsed by pattern definitions internally. First release
would have limited set of validations, like exists, not-exists. Keep in mind that validation rules would be
free type, parsed by the pattern classes. Idea is that we can build patterns on demand to apply new logic,
business logic into create operations, etc...

This would create in case document customer-code is unique.
{
    'customer-code': {
        'type': 'string',
        'validations': [
            {
                'type': 'not-exists',
            }
        ]
    }
}

Above definition would generate a query to check that document has customer_code for field value.

"""


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

        *Notes*

        * Django like field instance in Document??? Dictionary type?
        * Have in mind we will not use directly in code, like Django model
        * We would create/update document_definition document with configuration, validations, etc...

        :param args:
        :param kwargs:
        :return:
        """
        not_validated_field = filter(lambda x: x not in self.allowed_attributes, kwargs)
        if not_validated_field:
            raise exceptions.XimpiaAPIException(_(u''))
        for attr_name in kwargs:
            setattr(self, attr_name, kwargs[attr_name])

    def make_mapping(self):
        """
        Create the mapping structure to create mappings and update mappings

        :return:
        """
        # We could set analyzer. Default analyzer??? International chars???
        # How we set version fields??? We get field versions for name
        # TODO: integrate version
        version = ''
        mappings = {
            u'{}__{}'.format(
                self.name, version
            ): {
                u'type': u'string',
                u'fields': {
                    u'{}__{}'.format(
                        self.name, version): {
                            u'type': u'string'
                    },
                    u'raw__{}'.format(version): {
                        u'type': u'string',
                        u'index': u'not_analyzed'
                    }
                }
            }
        }
        if self.default:
            mappings[u'null_value'] = self.default
        if self.add_to_summary:
            mappings[u'copy_to'] = u'text__v1'
        if self.is_autocomplete:
            mappings[u'{}__{}'.format(self.name, version)][u'fields'][u'completion__v1'] = {
                u"type": u"completion",
                u"analyzer": u"simple_whitespace",
                u"payloads": True,
                u"preserve_separators": True,
                u"preserve_position_increments": True,
                u"max_input_length": 50
            }
        return mappings

    @classmethod
    def validate(cls, value, field_config, doc_config):
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
        max_length = field_config.get('min_length', None)
        field_choices = field_config.get('choices', None)
        validations = field_config.get('validations', None)
        if min_length:
            if len(value) < min_length:
                check = False
        if max_length:
            if len(value) > max_length:
                check = False
        if field_choices and value != '':
            # If we have some value in field, validate with choices
            choice_name = field_choices['choice_name']
            choice_value = filter(lambda x: x['choice_item_name'] == value,
                                  doc_config['choices'][choice_name])
            if choice_value:
                if choice_value[0]['choice_item_name'] != value:
                    check = False
            else:
                check = False
        # field validations
        if validations:
            for validation in validations:
                pass
        return check
