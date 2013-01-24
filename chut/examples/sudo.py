# -*- coding: utf-8 -*-
from chut import * # noqa


@console_script
def safe_upgrade(args):
    sudo.aptitude('update') > 1
    sudo.aptitude('safe-upgrade -y') > 1
