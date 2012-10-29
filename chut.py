# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import os
import sys
import logging
import subprocess
from copy import deepcopy
from contextlib import contextmanager

log = logging.getLogger('chut')


class Pipe(object):

    def __init__(self, args='', encoding='utf-8', **kwargs):
        self.args = args
        self.previous = None
        self.processes = []
        self.encoding = encoding
        self.kwargs = kwargs
        if 'sh' in kwargs:
            kwargs['shell'] = kwargs.pop('sh')
        if 'pipe' in kwargs:
            if not kwargs.pop('pipe'):
                self.run()
        elif not self._pipe:
            kwargs['shell'] = True
            self.run()

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
    def commands(self):
        cmds = [self]
        previous = self.previous
        while previous is not None:
            cmds.insert(0, previous)
            previous = previous.previous
        return cmds

    @property
    def stdout(self):
        self.processes = []
        stdin = sys.stdin
        for cmd in self.commands:
            if not isinstance(cmd, (Stdin, PyPipe)):
                encoding = cmd.encoding
                binary = cmd.__class__.__name__
                for dirname in ('/usr/bin', '/usr/sbin'):
                    filename = os.path.join(dirname, binary)
                    if os.path.isfile(filename):
                        binary = filename
                args = [binary] + cmd.args.split()
                if cmd.kwargs.get('shell', False):
                    args = ' '.join(args)
                kwargs = dict(
                    stdin=stdin, stderr=subprocess.PIPE,
                    stdout=subprocess.PIPE)
                kwargs.update(cmd.kwargs)
                log.debug('Running Popen(%r, **%r)', args, kwargs)
                try:
                    p = subprocess.Popen(args, **kwargs)
                except OSError:
                    if isinstance(args, list):
                        args = ' '.join(args)
                    log.debug('Error while running Popen(%r, **%r)',
                              args, kwargs)
                    raise OSError(args)
                self.processes.append(p)
                stdin = p.stdout
            elif isinstance(cmd, Stdin):
                continue
            else:
                cmd.encoding = encoding
                cmd.stdin = p.stdout
                stdin = cmd._stdout
        return stdin

    def run(self):
        self.stdout
        if self.returncodes:
            raise OSError(self.stderr)

    __call__ = run

    def __getitem__(self, item):
        if not isinstance(item, slice):
            raise KeyError('You can only use slices')
        cmds = self.commands
        cmds = [deepcopy(cmd) for cmd in cmds[item]]
        return self._order(cmds)[-1]

    def __getslice__(self, start, stop):
        cmds = self.commands
        cmds = [deepcopy(cmd) for cmd in cmds[start:stop]]
        return self._order(cmds)[-1]

    def __iter__(self):
        for line in self.stdout:
            yield line.decode(self.encoding)

    def __str__(self):
        stdout = self.stdout
        if hasattr(stdout, 'read'):
            output = stdout.read().rstrip()
        else:
            output = b''.join(list(stdout)).rstrip()
        if not isinstance(output, str):
            return output.decode(self.encoding)
        return output

    def __gt__(self, filename):
        return self._write(filename, 'wb+')

    def __rshift__(self, filename):
        return self._write(filename, 'ab+')

    def __or__(self, other):
        other = deepcopy(other)
        previous = other
        while previous.previous is not None:
            previous = previous.previous
        if isinstance(self, Stdin):
            previous.previous = self
        else:
            previous.previous = deepcopy(self)
        return other

    def __repr__(self):
        cmds = []
        for cmd in self.commands:
            s = ''
            if cmd.kwargs.get('shell'):
                s += 'sh '
            s += '%s ' % cmd.__class__.__name__
            if cmd.args:
                s += '%s ' % cmd.args
            cmds.append(s.strip())
        if len(cmds) == 1:
            return repr(str(cmds[0]))
        return repr(str(' | '.join(cmds)))

    def _order(self, cmds):
        if cmds:
            cmds[0].previous = None
            for i in range(len(cmds) - 1, 0, -1):
                cmds[i].previous = cmds[i - 1]
        return cmds

    def _write(self, filename, mode):
        with open(filename, mode) as fd:
            if not isinstance(self, PyPipe):
                self.kwargs['stdout'] = fd
                self.run()
            else:
                for line in self.stdout:
                    fd.write(line)
                if self.returncodes:
                    raise OSError(self.stderr)
        return None


class Stdin(Pipe):

    _pipe = True

    def __init__(self, value):
        super(Stdin, self).__init__()
        self.value = value

    def __or__(self, other):
        other = super(Stdin, self).__or__(other)
        if hasattr(self.value, 'read'):
            r = self.value
            r.seek(0)
        else:
            r, w = os.pipe()
            fd = os.fdopen(w, 'wb')
            fd.write(self.value)
            fd.close()
        other.kwargs['stdin'] = r
        return other


class PyPipe(Pipe):

    _pipe = True

    @property
    def _stdout(self):
        return self.func(self.stdin)


class Chut(object):
    __file__ = __file__
    __name__ = __name__
    not_piped = ['rm', 'mkdir', 'cp', 'touch', 'mv', 'scp', 'rsync']
    not_piped = sorted([str(c) for c in not_piped])
    _cmds = {}

    def wraps(self, func):
        return type(func.__name__, (PyPipe,), {'func': staticmethod(func)})()

    @contextmanager
    def pipe(self, cmd):
        try:
            yield cmd
        finally:
            if cmd.returncodes:
                stderr = cmd.stderr
                log.error('Error while running %r\n%s', cmd, stderr)
                raise OSError(stderr)

    def cd(self, directory):
        os.chdir(directory)

    def ssh(self, host, command, gzip=True, **kwargs):
        cmd = self.__getattr__('ssh')
        command = command.replace('"', r'\"')
        kwargs['shell'] = True
        if 'sh' in kwargs:
            del kwargs['sh']
        if gzip:
            return (cmd('%s "%s | gzip"' % (host, command), **kwargs) |
                    self.gunzip())
        else:
            return cmd('%s "%s"' % (host, command), **kwargs)

    def stdin(self, value):
        return Stdin(value)
        if hasattr(value, 'read'):
            if hasattr(value, 'seek'):
                value.seek(0)
            value = value.read()
        value = value.replace('\n', r'\n')
        return self.echo('"%s"' % value, shell=True)

    def __getattr__(self, attr):
        attr = str(attr)
        if attr not in self._cmds:
            if attr in self.not_piped:
                kw = dict(_pipe=False)
            else:
                kw = dict(_pipe=True)
            self._cmds[attr] = type(attr, (Pipe,), kw)
        return self._cmds[attr]

ch = Chut()
