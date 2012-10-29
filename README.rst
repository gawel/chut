====
Chut
====

Chut is a small tool to help you to interact with shell pipes.

Basically it will help to write some shell script in python

This is more like a toy than a real tool but... It may be useful sometimes.

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

When I said what you want it's mean that ``ch.whatyouwant`` will call a binary named ``whatyouwant``

Let's check if an error occurred with ``whatyouwant``::

    >>> str(ch.whatyouwant()) # doctest: +ELLIPSIS
    Traceback (most recent call last):
    ...
    OSError: whatyouwant

But an error can also occured if the binary exist::

    >>> cmd = ch.cat('whatyouwant')
    >>> output = str(cmd)
    >>> print(cmd.returncodes)
    [1]
    >>> print(cmd.stderr)
    cat: whatyouwant: No such file or directory

The pipe context manager
========================

A context manager can help you to check for some errors::

    >>> with ch.pipe(ch.cat('fff') | ch.grep('fff')) as p: # doctest: +ELLIPSIS
    ...    print(p)
    Traceback (most recent call last):
    ...
    OSError: cat: fff: No such file or directory

Use predefined pipe
====================

Define an pipe::

    >>> chut = ch.cat('README.rst') | ch.grep('chut')

And use it::

    >>> chut | ch.head('-n1')
    'cat README.rst | grep chut | head -n1'

The original defined pipe stay as this (everything is copied)::

    >>> chut
    'cat README.rst | grep chut'

You can also extract parts of the pipe using slices::

    >>> chut[1:]
    'grep chut'

Use python !!
=============

Finally you can use some python code ad the end of the pipe (and only at the end)::

    >>> @ch.wraps
    ... def check_chut(stdin):
    ...     for line in stdin:
    ...         if line.startswith(b'Chut'):
    ...             yield b'Chut rocks!\n'
    ...             break

    >>> with ch.pipe(ch.cat('README.rst') | check_chut) as cmd:
    ...     for line in cmd:
    ...         print(line)
    Chut rocks!
    <BLANKLINE>

Input
=====

You can use a python string as input::

    >>> print(ch.stdin(b'gawel\nfoo') | ch.grep('gawel'))
    gawel

The input can be a file but the file is not streamed by ``stdin()``

Output
======

You can get the output as string::

    >>> output = str(ch.cat('README.rst') | check_chut)

As an iterator (iterate over each lines of the output)::

    >>> chut_stdout = ch.cat('README.rst') | check_chut

And can use some redirection::

    >>> chut_stdout > 'chut.txt'
    >>> print(ch.cat('chut.txt'))
    Chut rocks!
    >>> chut_stdout >> 'chut.txt'
    >>> print(ch.cat('chut.txt'))
    Chut rocks!
    Chut rocks!

Parentheses are needed with ``>>`` only (due to the way the python operator work)

..

    >>> ch.rm('-f chut.txt')
    'sh rm -f chut.txt'

Exceptions
==========

By default a command do not launch a shell. But if you need you can use one::

    >>> ch.ls(shell=True)
    'sh ls'

    >>> ch.ls(sh=True)
    'sh ls'

By default a command is piped. But you can avoid this::

    >>> ch.ls(pipe=False)
    'ls'

Some commands do not use a pipe by default. This mean that they are executed immediately::

    >>> ch.not_piped
    ['cp', 'mkdir', 'mv', 'rm', 'rsync', 'scp', 'touch']

The ssh command take a host first and is gziped by default::

    >>> ch.ssh('sandy', 'ls ~')
    'sh ssh sandy "ls ~ | gzip" | gunzip'

But you can avoid gzip::

    >>> ch.ssh('sandy', 'ls ~', gzip=False)
    'sh ssh sandy "ls ~"'

Notice that a ssh command always use a shell.

Debugging
==========

You can print you pipe::

    >>> ch.cat('README.txt') | check_chut
    'cat README.txt | check_chut'

You can also activate logging::

    >>> import logging
    >>> logging.basicConfig(level=logging.DEBUG)

Cheers.
