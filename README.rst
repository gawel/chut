====
Chut
====

Chut is a small tool to help you to interact with shell pipes.

Basically it will help to write some shell script in python

This is more like a toy than a real tool but... It may be useful sometimes.

It's `tested <https://travis-ci.org/gawel/chut>`_ with py2.6+ and py3.2+:

.. image:: https://secure.travis-ci.org/gawel/chut.png

.. contents::

Installation
============

Using pip::

    $ pip install chut

Usage
=====

Import the shell::

    >>> from chut import ch

Then run what you want::

    >>> print(ch.cat('README.rst') | ch.grep('Chut') | ch.head("-n1"))
    Chut

When I said what you want it's mean that ``ch.whatyouwant`` will call a binary
named ``whatyouwant``

Let's check if an error occurred with ``whatyouwant``::

    >>> str(ch.whatyouwant()) # doctest: +ELLIPSIS
    Traceback (most recent call last):
    ...
    OSError: whatyouwant

About imports
=============

You can import ch and sudo::

    >>> from chut import ch, sudo

But you can also import some specific commands::

    >>> from chut import cat, grep, gzip, gunzip
    >>> from chut.sudo import ifconfig

The pipe context manager
========================

An error can occur if the binary exist::

    >>> cmd = ch.cat('whatyouwant')
    >>> output = str(cmd)
    >>> output.succeeded
    False
    >>> print(output.stderr)
    cat: whatyouwant: No such file or directory

A context manager can help you to check for some errors::

    >>> with ch.pipe(cat('fff') | grep('fff')) as p: # doctest: +ELLIPSIS
    ...    print(p)
    Traceback (most recent call last):
    ...
    OSError: cat: fff: No such file or directory

Basically it checks return codes at the end of the pipe

Use predefined pipe
====================

Define an pipe::

    >>> chut = cat('README.rst') | grep('chut')

And use it::

    >>> chut | ch.head('-n1')
    'cat README.rst | grep chut | head -n1'

The original defined pipe stay as this (everything is copied)::

    >>> chut
    'cat README.rst | grep chut'

You can also extract parts of the pipe using slices::

    >>> chut[1:]
    'grep chut'

SSH
===

The ssh command take a host first and is gziped by default::

    >>> from chut import ssh
    >>> srv1 = ssh('gawel@srv')
    >>> srv1.ls('~')
    'ssh gawel@srv ls ~'

For example you can backup your mysql database locally::

    >>> srv1.mysqldump('db | gzip') | gzip
    "ssh gawel@srv 'mysqldump db | gzip' | gzip"

Or on another server::

    >>> srv2 = ssh('gawel@srv2')
    >>> srv1(ch.mysqldump('db') | gzip | srv2('gunzip > ~/backup.db'))
    'ssh gawel@srv "mysqldump db | gzip | ssh gawel@srv2 \'gunzip > ~/backup.db\'"'

You can use your ssh instance to get some remote file::

    >>> ch.rsync(srv1.join('~/p0rn'), '.', pipe=True)
    'rsync gawel@srv:~/p0rn .'

Sudo
====

You can for sure use sudo::

    >>> from chut import sudo
    >>> sudo.ls() | sudo.grep('chut')
    'sudo -s ls | sudo -s grep chut'

Sudo wont work with ssh except if it does not require a password

Testing
=======

You can use the test command::

    >>> from chut import test

    >>> # test -f chut.py
    >>> bool(test.f('chut.py'))
    True

    >>> # test -x chut.py
    >>> if test.x('chut.py'):
    ...     print('Chut.py is executable')

Use python !!
=============

Finally you can use some python code ad the end of the pipe (and only at the
end)::

    >>> @ch.wraps
    ... def check_chut(stdin):
    ...     for line in stdin:
    ...         if line.startswith(b'Chut'):
    ...             yield b'Chut rocks!\n'
    ...             break

    >>> with ch.pipe(cat('README.rst') | check_chut) as cmd:
    ...     for line in cmd:
    ...         print(line)
    Chut rocks!
    <BLANKLINE>

Input
=====

You can use a python string as input::

    >>> print(ch.stdin(b'gawel\nfoo') | grep('gawel'))
    gawel

The input can be a file but the file is not streamed by ``stdin()``.
Notice that the file must be open in binary mode (``rb``)::

    >>> print(ch.stdin(open('README.rst', 'rb'))
    ...               | grep('Chut') | ch.head('-n1'))
    Chut

Output
======

You can get the output as string::

    >>> output = str(cat('README.rst') | check_chut)
    >>> output = (cat('README.rst') | check_chut)()

As an iterator (iterate over each lines of the output)::

    >>> chut_stdout = cat('README.rst') | check_chut

And can use some redirection::

    >>> ret = chut_stdout > 'chut.txt'
    >>> ret.succeeded
    True
    >>> print(cat('chut.txt'))
    Chut rocks!

    >>> ret = chut_stdout >> 'chut.txt'
    >>> ret.succeeded
    True
    >>> print(cat('chut.txt'))
    Chut rocks!
    Chut rocks!

Parentheses are needed with ``>>`` only (due to the way the python operator work)

..

    >>> ch.rm('-f chut.txt')
    'rm -f chut.txt'

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

    >>> print(repr(cat('README.txt') | check_chut))
    'cat README.txt | check_chut()'

You can also activate logging::

    >>> import logging
    >>> logging.basicConfig(level=logging.DEBUG)
    >>> log = logging.getLogger('chut')
    >>> # set level/handler

Cheers.
