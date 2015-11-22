import time

from django.test import RequestFactory, Client
from base.tests import XimpiaTestCase

__author__ = 'jorgealegre'


class SessionTestCase(XimpiaTestCase):

    def setUp(self):
        self.c = Client()
        self.req_factory = RequestFactory()

    def tearDown(self):
        pass

    def save(self):
        session = self.c.session
        session['key'] = 'value'
        session.save()
        self.assertTrue(len(session.load()) != 0)

    def delete(self):
        session = self.c.session
        session['key'] = 'value'
        session.save()
        del session['key']
        session.save()
        self.assertTrue(len(session.load()) == 0)
