# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import os
import sys
import subprocess
from contextlib import contextmanager


class Pipe(object):

    def __init__(self, args='', encoding='utf-8'):
        self.args = args
        self.previous = None
        self.processes = []
        self.encoding = encoding

    @property
    def returncodes(self):
        for p in self.processes:
            p.wait()
        codes = [p.poll() for p in self.processes]
        if set(codes) == set([0]):
            return []
        return codes

    @property
    def stderr(self):
        stderr = [p.stderr.read() for p in self.processes]
        output = b'\n'.join(stderr).strip()
        return output.decode(self.encoding)

    @property
    def stdout(self):
        self.processes = []
        cmds = [self]
        previous = self.previous
        while previous is not None:
            cmds.insert(0, previous)
            previous = previous.previous
        stdin = sys.stdin
        for cmd in cmds:
            if not isinstance(cmd, PyPipe):
                encoding = cmd.encoding
                binary = cmd.__class__.__name__
                for dirname in ('/usr/bin', '/usr/sbin'):
                    filename = os.path.join(dirname, binary)
                    if os.path.isfile(filename):
                        binary = filename
                args = [binary] + cmd.args.split()
                try:
                    p = subprocess.Popen(args,
                            stdin=stdin, stderr=subprocess.PIPE,
                            stdout=subprocess.PIPE)
                except OSError:
                    raise OSError(' '.join(args))
                self.processes.append(p)
                stdin = p.stdout
            else:
                cmd.encoding = encoding
                cmd.stdin = p.stdout
                stdin = cmd._stdout
        return stdin

    def __iter__(self):
        for line in self.stdout:
            yield line.decode(self.encoding)

    def __str__(self):
        if hasattr(self.stdout, 'read'):
            output = self.stdout.read().rstrip()
        else:
            output = b''.join(list(self.stdout)).rstrip()
        return output.decode(self.encoding)

    def __gt__(self, filename):
        with open(filename, 'w') as fd:
            for line in self.stdout:
                fd.write(line.decode(self.encoding))
        return None

    def __rshift__(self, filename):
        with open(filename, 'a+') as fd:
            for line in self.stdout:
                fd.write(line.decode(self.encoding))
        return None

    def __or__(self, other):
        other.previous = self
        return other

    def __repr__(self):
        if self.args:
            return '<%s %s>' % (self.__class__.__name__, self.args)
        else:
            return '<%s>' % self.__class__.__name__


class PyPipe(Pipe):

    def __init__(self, func):
        self.args = []
        self.func = func
        self.stdin = None
        self.previous = None

    @property
    def _stdout(self):
        return self.func(self.stdin)


class Chut(object):
    __file__ = __file__
    __name__ = __name__

    def wraps(self, func):
        return type(func.__name__, (PyPipe,), {})(func)

    @contextmanager
    def pipe(self, cmd):
        try:
            yield cmd
        finally:
            if cmd.returncodes:
                raise OSError(cmd.stderr)

    def cd(self, directory):
        os.chdid(directory)

    def __getattr__(self, attr):
        return type(attr, (Pipe,), {})

ch = Chut()
