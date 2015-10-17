# -*- coding: utf-8 -*-
from __future__ import with_statement
from fabric.api import run, local, cd, task
from fabric.utils import abort

__author__ = 'jorgealegre'


@task
def deploy_dev(branch):
    """
    Deploy development

    :param branch:
    :return:
    """
    current_branch = local('git rev-parse --symbolic-full-name --abbrev-ref HEAD', capture=True)
    print 'current:', current_branch
    print 'branch:', branch
    if current_branch != branch:
        abort('"deploy_dev" command pushes current git branch to your user environment. '
              'Your current branch is different from branch you want to push. Please do "git checkout {}"'
              .format(branch))

    local('git fetch')
    local('git pull origin {}'.format(branch))
    local('git push origin {}'.format(branch))
    git_dir = '/mnt/src/ximpia-api'
    with cd(git_dir):
        run('git fetch')
        run('git checkout {}'.format(branch))
        run('git pull origin {}'.format(branch))
        run('/home/ximpia/envs/ximpia-api/bin/pip install -r /mnt/config/configs/ximpia-api-dev-requirements.txt')
        run('touch /mnt/config/ximpia-api.uwsgi.ini')
