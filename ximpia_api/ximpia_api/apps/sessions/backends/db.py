import requests
import logging

from django.contrib.sessions.backends.base import CreateError, SessionBase
from django.core.exceptions import SuspiciousOperation
from django.db import IntegrityError, router, transaction
from django.utils import timezone
from django.utils.encoding import force_text


__author__ = 'jorgealegre'


class SessionStore(SessionBase):
    """
    Implements database session store.
    """
    def __init__(self, session_key=None):
        super(SessionStore, self).__init__(session_key)

    def load(self):
        pass

    def exists(self, session_key):
        return True

    def create(self):
        pass

    def save(self, must_create=False):
        """
        Saves the current session data to the database. If 'must_create' is
        True, a database error will be raised if the saving operation doesn't
        create a *new* entry (as opposed to possibly updating an existing
        entry).
        """
        pass

    def delete(self, session_key=None):
        pass

    @classmethod
    def clear_expired(cls):
        pass
