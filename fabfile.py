# -*- coding: utf-8 -*-
from fabric.api import env
from chut import fab

env.forward_agent = True

fab.chutifab()


def upgrade():
    fab.run('rfsync', '-h')
    fab.sudo('rfsync', '-h')
