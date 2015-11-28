from django.contrib.auth.signals import user_logged_in
from django.contrib.auth.models import update_last_login

__author__ = 'jorgealegre'


def update_last_login_mine(sender, user, **kwargs):
    """
    A signal receiver which updates the last_login date for
    the user logging in.
    """
    pass

user_logged_in.disconnect(update_last_login)
user_logged_in.connect(update_last_login_mine)
