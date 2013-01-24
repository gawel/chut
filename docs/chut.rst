==========
Internals
==========

.. _imports:

Imports
=======

Those elements are imported when you use ``from chut import *``:

.. literalinclude:: ../chut/__init__.py
   :lines: 17-32

Also noticed that commands which don't use pipes are listed here.

Pipe
====

.. autoclass:: chut.Pipe
   :members:

..
    >>> import chut as sh
    >>> from chut import cat, grep

Environ
=======

.. autoclass:: chut.Environ
   :members:

Input
=====

You can use a python string as input::

    >>> print(sh.stdin(b'gawel\nfoo') | grep('gawel'))
    gawel

The input can be a file but the file is not streamed by ``stdin()``.
Notice that the file must be open in binary mode (``rb``)::

    >>> print(sh.stdin(open('README.rst', 'rb'))
    ...               | grep('Chut') | sh.head('-n1'))
    Chut!

.. autoclass:: chut.Stdin
   :members:

Output
======

You can get the output as string (see :class:`~chut.Stdout`)::

    >>> output = str(cat('README.rst') | grep('Chut'))
    >>> output = (cat('README.rst') | grep('Chut'))()

As an iterator (iterate over each lines of the output)::

    >>> chut_stdout = cat('README.rst') | grep('Chut') | sh.head('-n1')

And can use some redirection::

    >>> ret = chut_stdout > '/tmp/chut.txt'
    >>> ret.succeeded
    True
    >>> print(cat('/tmp/chut.txt'))
    Chut!

    >>> ret = chut_stdout >> '/tmp/chut.txt'
    >>> ret.succeeded
    True
    >>> print(cat('/tmp/chut.txt'))
    Chut!
    Chut!

Parentheses are needed with ``>>`` (due to the way the python operator work)::

    cat('README.rst') | grep >> '/tmp/chut.txt' # wont work
    (cat('README.rst') | grep) >> '/tmp/chut.txt' # work

.. autoclass:: chut.Stdout
   :members:

Ini files
=========

.. autofunction:: chut.ini

Example::

    >>> from chut import ini
    >>> config = ini('/tmp/chut.ini')
    >>> config.my = dict(key='value')
    >>> config.write()
    >>> config = ini('/tmp/chut.ini')
    >>> print(config.my.key)
    value
