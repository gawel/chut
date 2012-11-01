=============
Chut's basics
=============



You can use the test command::

    >>> from chut import test

    >>> # test -f chut.py
    >>> bool(test.f('chut.py'))
    True

    >>> # test -x chut.py
    >>> if test.x('chut.py'):
    ...     print('Chut.py is executable')

About imports
=============

You can import ch and sudo::

    >>> from chut import ch, sudo

But you can also import some specific commands::

    >>> from chut import cat, grep, gzip, gunzip
    >>> from chut.sudo import ifconfig


Exceptions
==========

The ``cd`` command use python ``os.chdir()``

Some commands do not use a pipe by default. This mean that they are executed immediately::

    >>> ch.not_piped
    ['cp', 'mkdir', 'mv', 'rm', 'rsync', 'scp', 'touch']

By default a command is piped. But you can avoid this::

    >>> ch.ls(pipe=False)
    'ls'

By default a command do not launch a shell. But if you need you can use one::

    >>> ch.ls(shell=True)
    'ls'

    >>> ch.ls(sh=True)
    'ls'

Debugging
==========

You can print your pipe::

    >>> print(repr(cat('README.txt') | grep('Chut')))
    'cat README.txt | grep Chut'

You can also activate logging::

    >>> import logging
    >>> logging.basicConfig(level=logging.DEBUG)
    >>> log = logging.getLogger('chut')
    >>> # set level/handler

Cheers.
