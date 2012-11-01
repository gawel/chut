Sudo
====

You can for sure use sudo::

    >>> from chut import sudo
    >>> sudo.ls() | sudo.grep('chut')
    'sudo -s ls | sudo -s grep chut'

Sudo wont work with ssh except if it does not require a password


