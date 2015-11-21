from django.test import RequestFactory, Client
from base.tests import XimpiaTestCase

__author__ = 'jorgealegre'


class SessionTestCase(XimpiaTestCase):

    def setUp(self):
        self.c = Client()
        self.req_factory = RequestFactory()

    def tearDown(self):
        pass

    def base(self):
        print 'SessionTest.base...'
        session = self.c.session
        session['key'] = 'value'
        session.save()
