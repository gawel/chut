Sudo
====

You can for sure use sudo::

    >>> from chut import sudo
    >>> sudo.ls() | sudo.grep('chut')
    '/usr/bin/sudo -s ls | /usr/bin/sudo -s grep chut'

Sudo wont work with ssh except if it does not require a password on the server
side.


