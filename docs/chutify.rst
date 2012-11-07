Generate scripts
================

Chut allow you to generate some standalone scripts. Scripts will include chut
and docopts (and a few other modules if you want) encoded in base64.

How it works
-------------

..
    >>> import chut as ch
    >>> from chut import test
    >>> ch.rm('-Rf', 'dist/scripts').succeeded
    True
    >>> ch.env['PATH'] = 'bin:/bin:/usr/bin'
    >>>

Write a file with a function in it::

    >>> ch.stdin(b'''
    ... import chut as ch
    ... @ch.console_script
    ... def my_script(arguments):
    ...     """Usage: %prog [-h]
    ...
    ...     -h, --help    Print this help
    ...     """
    ...     print('Hello world')
    ... ''') > 'myscript.py'
    ''

Then run chutify on it::

    >>> print(ch.chutify('myscript.py', combine_stderr=True))
    writing dist/scripts/my_script
    chmod +x dist/scripts/my_script

And check the result in ``dist/scripts``::

    >>> bool(test.x('dist/scripts/my_script'))
    True

    >>> print(ch.pipe('dist/scripts/my_script'))
    Hello world

    >>> print(ch.pipe('dist/scripts/my_script', '-h'))
    Usage: my_script [-h]
    <BLANKLINE>
    -h, --help    Print this help

..
    >>> print(ch.pipe('python2.7', 'dist/scripts/my_script'))
    Hello world
    >>> print(ch.pipe('python3', 'dist/scripts/my_script'))
    Hello world
    >>> ch.rm('-f myscript.*', shell=True).succeeded
    True

