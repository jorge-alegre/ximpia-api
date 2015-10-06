#!/usr/bin/env python
import os
import sys

sys.path.append('{}/ximpia_api/apps/'.format(os.getcwd()))
sys.path.append('ximpia_api')

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ximpia_api.settings")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
