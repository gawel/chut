Chut!

Chut is a small tool to help you to interact with shell pipes and commands.

Basically it will help to write some shell script in python

This is more like a toy than a real tool but... It may be useful sometimes.

It's `tested <https://travis-ci.org/gawel/chut>`_ with py2.6+ and py3.2+:

.. image:: https://secure.travis-ci.org/gawel/chut.png

Full documentation can be found
`here <https://chut.readthedocs.org/en/latest/>`_

Installation
============

Using pip::

    $ pip install chut

This will also install docopt and allow you to use the ``@console_script`` decorator.

Quick start
===========

Import the shell::

    >>> import chut as sh

Get a file content if he contains "Chut"::

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

Use docopt to write a console script. This script will take an iface as
argument and return a code 1 if no addresses are found::

    >>> @sh.console_script
    ... def got_inet_addr(args):
    ...     """Usage: got_inet_addr <iface>"""
    ...     if sh.ifconfig(args['<iface>']) | sh.grep('inet addr:'):
    ...         return 1

    >>> if __name__ == '__main__':
    ...     got_inet_addr()

