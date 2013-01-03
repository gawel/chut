=============
Chut's basics
=============

About imports
=============

You can import chut and use commands::

    >>> import chut as sh
    >>> sh.ls()
    'ls'

You can import sudo::

    >>> from chut import sudo

But you can also import some specific commands::

    >>> from chut import cat, grep, gzip, gunzip
    >>> from chut.sudo import ifconfig

Or import "all" commands. Where "all" is a ``unexaustive set`` of commands::

    >>> from chut import *


Exceptions
==========

The ``cd`` command use python ``os.chdir()``

Some commands do not use a pipe by default. This mean that they are executed immediately::

    >>> sh.not_piped
    ['cp', 'mkdir', 'mv', 'rm', 'touch', 'mv']

By default a command is piped. But you can avoid this::

    >>> sh.ls(pipe=False)
    'ls'

By default a command do not use a shell. But if you need you can use one::

    >>> sh.ls(shell=True)
    'ls'

    >>> sh.ls(sh=True)
    'ls'

Aliases
========

You can define some aliases::

  >>> sh.aliases['ll'] = '/usr/local/bin/ls -l'
  >>> sh.aliases['python'] = '/opt/python3/bin/python3'
  >>> print(repr(sh.ll('.')))
  '/usr/local/bin/ls -l .'
  >>> print(repr(sh.python('-c "import sys"')))
  '/opt/python3/bin/python3 -c "import sys"'

Environ
=======

..
  >>> sh.env.old_path = sh.env.path

Chut use a copy of ``os.environ`` but you can modify values::

  >>> from chut import env
  >>> env.path = '/usr/bin:/usr/local/bin'
  >>> env.path
  ['/usr/bin', '/usr/local/bin']
  >>> env.path = ['/usr/bin', '/usr/local/bin']
  >>> env.path
  ['/usr/bin', '/usr/local/bin']
  >>> env.path += ['bin']
  >>> env.path
  ['/usr/bin', '/usr/local/bin', 'bin']

Only ``path`` return a list. Other values return a string.

..
  >>> env.path = env.old_path

You can also pass a copy to your commands::

  >>> env = sh.env()
  >>> sh.cat('-', env=env)
  'cat -'

The test command
================

You can use the test command::

    >>> from chut import test

    >>> # test -f chut/scripts.py
    >>> bool(test.f('chut/scripts.py'))
    True

    >>> # test -x chut/scripts.py
    >>> if test.x('chut/scripts.py'):
    ...     print('chut/scripts.py is executable')

Run a large amount of processes
===============================

You can use the :meth:`chut.Pipe.map` method to run a large amount of commands with the
same binary. Arguments must be a list of string or list::

    >>> results = sh.ls.map(['.', ['-l', '.']])
    >>> [res.succeeded for res in results]
    [True, True]

Debugging
==========

You can print your pipe::

    >>> print(repr(cat('README.txt') | grep('Chut')))
    'cat README.txt | grep Chut'

You can also activate logging::

    >>> sh.set_debug()
    >>> print(cat('README.rst') | grep('Chut') | sh.head('-n1')) # doctest: +ELLIPSIS
    Popen(['cat', 'README.rst'], **{...})
    Popen(['grep', 'Chut'], **{...})
    Popen(['head', '-n1'], **{...})
    Chut!
 

Cheers.
