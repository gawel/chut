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

Or import "all" commands. Where "all" is a unexaustive set of commands::

    >>> from chut import *  # doctest: +SKIP

See :ref:`imports`

Exceptions
==========

The ``cd`` command use python ``os.chdir()``

Some commands do not use a pipe by default. This mean that they are executed immediately. See :ref:`imports`

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

  >>> env = sh.env.copy()
  >>> sh.cat('-', env=env)
  'cat -'

The environment can also be temporarily modified with a "with" statement.
In this example, "HOME" is modified only inside the "with" block and restored
at the end::

  >>> with sh.env(HOME="/home/foo"):
  ...     str(sh.echo("$HOME", sh=True))
  ... 
  '/home/foo'


The test command
================

You can use the test command::

    >>> from chut import test

    >>> # test -f chut/recipe.py
    >>> bool(test.f('chut/recipe.py'))
    True

    >>> # test -x chut/recipe.py
    >>> if test.x('chut/recipe.py'):
    ...     print('chut/recipe.py is executable')


Logging
=======

Chut provide logging facility::

    >>> import sys
    >>> log = sh.logopts(fmt='brief', stream=sys.stdout)
    >>> log.info('info message')
    [INFO] info message


When logging is configured you can use those simple functions::

    >>> from chut import debug, info, error
    >>> info('info message')
    [INFO] info message
    >>> debug('debug message')
    >>> error('error message')
    [ERROR] error message

Notice that if you use ``%options`` in a ``console_script`` docstring then you
don't need to use ``logopts``. The decorator will do the job for you.

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
