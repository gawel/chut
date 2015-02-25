Chut!

Chut is a small tool to help you to interact with shell pipes and commands.

Basically it will help to write some shell script in python

This is more like a toy than a real tool but... It may be useful sometimes.

It's `tested <https://travis-ci.org/gawel/chut>`_ with py2.6+ and py3.2+:

.. image:: https://secure.travis-ci.org/gawel/chut.png

Full documentation can be found
`here <https://chut.readthedocs.org/en/latest/>`_

Quick quick start
=================

Get the `chutify
<https://raw.github.com/gawel/chut/master/docs/_static/binaries/chutify>`_ script::

    $ wget https://raw.github.com/gawel/chut/master/docs/_static/binaries/chutify
    $ chmod +x chutify

Write a console script::

    $ cat << EOF > myscript.py
    from chut import *

    __version__ = '0.1'

    @console_script
    def mycmd(args):
        """Usage: %prog [options] <directory>

        Print all chut scripts found in <directory>

        Options:

        %options
        """
        for filename in find('-name *.py') | grep('@console_script'):
            print(filename)
    EOF

Run ``chutify`` in development mode::

    $ ./chutify --devel
    chmod +x bin/mycmd

And use/debug the newly created script::

    $ ./bin/mycmd -h

When your script is ready for production then generate the standalone version::

    $ ./chutify
    chmod +x dist/scripts/mycmd

Also have a look at the `examples <https://chut.readthedocs.org/en/latest/examples.html>`_.

Installation
============

Using pip::

    $ pip install chut

This will also install docopt and allow you to use the ``@console_script`` decorator.

Another option is to get `chutify
<https://raw.github.com/gawel/chut/master/docs/_static/binaries/chutify>`_
standalone version::

    $ wget https://raw.github.com/gawel/chut/master/docs/_static/binaries/chutify
    $ chmod +x chutify

Quick start
===========

Import the shell::

    >>> import chut as sh

Get a file content if it contains "Chut"::

    >>> grep_chut = sh.cat('README.rst') | sh.grep('Chut')
    >>> if grep_chut:
    ...     print(grep_chut | sh.head("-n1"))
    Chut!

Redirect output to a file::

    >>> ret = (grep_chut | sh.head("-n1")) > '/tmp/chut.txt'
    >>> ret.succeeded
    True
    >>> print(sh.cat('/tmp/chut.txt'))
    Chut!

Or to stdout::

    >>> sh.cat('/tmp/chut.txt') > 1  # doctest: +SKIP
    Chut!

Redirect stdout to stderr::

    >>> sh.cat('/tmp/chut.txt') > 2  # doctest: +SKIP
    Chut!

Run many command with a pool of processes::

    >>> [ret.succeeded for ret in sh.ls.map(['.', ['-l', '/tmp']])]
    [True, True]

Use docopt to write a console script. This script will take an iface as
argument and return a code 1 if no address is found::

    >>> @sh.console_script
    ... def got_inet_addr(args):
    ...     """Usage: got_inet_addr <iface>"""
    ...     if sh.ifconfig(args['<iface>']) | sh.grep('inet addr:'):
    ...         return 1

