__author__ = 'jorgealegre'

ACCESS_TOKEN_NOT_FOUND = 'ACCESS_TOKEN_NOT_FOUND'
USER_ID_NOT_FOUND = 'USER_ID_NOT_FOUND'
SOCIAL_NETWORK_AUTH_ERROR = 'SOCIAL_NETWORK_AUTH_ERROR'


class XimpiaAPIException(Exception):

    def __init__(self, message, code=''):
        self.message = message
        self.code = code

    def __str__(self):
        if self.code:
            return u'{} [{}]'.format(self.message, self.code)
        return u'{}'.format(self.message)


class DocumentNotFound(Exception):

    def __init__(self, message):
        self.message = message

    def __str__(self):
        return u'{}'.format(self.message)
