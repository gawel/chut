# -*- coding: utf-8 -*-
from chut import * # noqa


@console_script
def safe_upgrade(args):
    """Usage: %prog

    Update && upgrade a debian based system
    """
    sudo.aptitude('update') > 1
    sudo.aptitude('safe-upgrade') > 1
