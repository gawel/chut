====
Chut
====

Chut is a small tool to help you to interact with shell pipes.

Basically it will help to write some shell script in python

This is more like a toy than a real tool but... it may be usefull sometimes.

Installation
============

::

    $ pip install chut

Usage
=====

Import the shell::

    >>> from chut import ch

Then run what you want::

    >>> print(ch.cat('/etc/passwd') | ch.grep('root') | ch.cut("-d: -f1"))
    root

When I said what you want it's mean that ``ch.whatyouwant`` will call a binary named ``whatyouwant``

Let's check if an error occured with ``whatyouwant``::

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

Use python !!
=============

Finally you can use some python code ad the end of the pipe (and only at the end)::

    >>> @ch.wraps
    ... def check_root(stdin):
    ...     for line in stdin:
    ...         if line.startswith(b'root'):
    ...             yield b'User ' + line.split(b':', 1)[0] + b' exist\n'

    >>> with ch.pipe(ch.cat('/etc/passwd') | check_root) as cmd:
    ...     for line in cmd:
    ...         print(line)
    User root exist
    <BLANKLINE>

Output
======

You can get the output as string::

    >>> output = str(ch.cat('/etc/passwd') | check_root)

As an iterator (iter over each lines of the output)::

    >>> output = ch.cat('/etc/passwd') | check_root

And can use some redirection::

    >>> ch.cat('/etc/passwd') | check_root > 'users.txt'
    >>> print(ch.cat('users.txt'))
    User root exist
    >>> (ch.cat('/etc/passwd') | check_root) >> 'users.txt'
    >>> print(ch.cat('users.txt'))
    User root exist
    User root exist

Parentheses are needed with ``>>`` only (due to the way the python operator work)

..

    >>> with ch.pipe(ch.rm(' -f users.txt')) as cmd:
    ...     output = str(cmd)

Cheers.
