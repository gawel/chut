# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import os
import sys
import types
import logging
import posixpath
import subprocess
from copy import deepcopy
from contextlib import contextmanager

log = logging.getLogger('chut')

SUDO = '/usr/bin/sudo'


def check_sudo():
    if not os.path.isfile(SUDO):
        raise OSError('sudo is not installed')
    whoami = subprocess.Popen([SUDO, 'whoami'],
                              stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT,
                              env=env)
    whoami.wait()
    whoami = whoami.stdout.read().strip()
    if whoami != 'root':
        raise OSError('Not able to run sudo')


class Environ(dict):

    def __getattr__(self, attr):
        return self.get(attr.upper(), None)

    def __setattr__(self, attr, value):
        if isinstance(value, (list, tuple)):
            value = ':'.join(value)
        self[attr.upper()] = value

    def __call__(self, **kwargs):
        environ = self.__class__(self.copy())
        for k, v in kwargs.items():
            setattr(environ, k, v)
        return environ


class Pipe(object):

    _chut = None
    _pipe = True
    _cmd_args = []

    def __init__(self, *args, **kwargs):
        self._stderr = None
        self.args = list(args)
        self.previous = None
        self.processes = []
        self.encoding = kwargs.get('encoding', 'utf8')
        self.kwargs = kwargs
        if 'sh' in kwargs:
            kwargs['shell'] = kwargs.pop('sh')
        if 'combine_stderr' in kwargs:
            kwargs.pop('combine_stderr')
            kwargs['stderr'] = subprocess.STDOUT
        if 'pipe' in kwargs:
            if not kwargs.pop('pipe'):
                self.__call__()
        elif not self._pipe:
            self.__call__()

    @property
    def returncodes(self):
        for p in self.processes:
            p.wait()
        codes = [p.poll() for p in self.processes]
        if set(codes) == set([0]):
            return []
        return codes

    @property
    def failed(self):
        output = self.__call__()
        return output.failed

    @property
    def succeeded(self):
        output = self.__call__()
        if output.succeeded:
            if output:
                return output
            else:
                return True
        return False

    @property
    def stderr(self):
        if self._stderr is None:
            stderr = [p.stderr.read() for p in self.processes]
            output = b'\n'.join(stderr).strip()
            self._stderr = output.decode(self.encoding)
        return self._stderr

    @property
    def commands(self):
        cmds = [self]
        previous = self.previous
        while previous is not None:
            cmds.insert(0, previous)
            previous = previous.previous
        return cmds

    def command_line(self, shell=False):
        args = []

        if self._cmd_args:
            args.extend(self._cmd_args)

        binary = self._binary
        if self._cmd_args[:1] == ['ssh']:
            cmd = '%s %s' % (binary, ' '.join(self.args))
            cmd = cmd.strip()
            if ('|' in cmd or '>' in cmd) and shell:
                cmd = repr(str(cmd))
            if 'sudo' in cmd and '-t' not in self._cmd_args:
                args.append('-t')
            args.append(cmd)
        else:
            args.append(binary)
            if isinstance(self.args, list):
                for a in self.args:
                    args.extend(a.split())
            else:
                args.extend(self.args.split(" "))

        args = [a for a in args if a]

        if shell:
            return ' '.join(args)
        return args

    @property
    def commands_line(self):
        cmds = []
        for cmd in self.commands:
            if isinstance(cmd, Stdin):
                s = 'stdin'
            elif isinstance(cmd, PyPipe):
                s = '%s()' % cmd.__class__.__name__
            else:
                s = cmd.command_line(shell=True)
            cmds.append(s.strip())
        return str(' | '.join(cmds))

    @property
    def stdout(self):
        p = None
        self.processes = []
        stdin = sys.stdin
        cmds = self.commands

        if [c for c in cmds if c._cmd_args[:1] == ['sudo']]:
            check_sudo()

        for cmd in cmds:
            if isinstance(cmd, Stdin):
                stdin = cmd.iter_stdout
            elif isinstance(cmd, PyPipe):
                cmd.stdin = p.stdout
                stdin = cmd.iter_stdout
            else:
                args = cmd.command_line(cmd.kwargs.get('shell', False))

                kwargs = dict(
                    stdin=stdin, stderr=subprocess.PIPE,
                    stdout=subprocess.PIPE
                    )
                kwargs.update(cmd.kwargs)

                log.debug('Running Popen(%r, **%r)', args, kwargs)

                if 'env' not in kwargs:
                    kwargs['env'] = env

                try:
                    p = subprocess.Popen(args, **kwargs)
                except OSError:
                    self._raise(args, kwargs)

                self.processes.append(p)
                stdin = p.stdout
        return stdin

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

    def __call__(self, **kwargs):
        for cmd in self.commands:
            if kwargs.get('shell'):
                cmd.kwargs['shell'] = True
            if kwargs.get('combine_stderr'):
                cmd.kwargs['stderr'] = subprocess.STDOUT
        stdout = self.stdout
        if stdout is not None:
            if hasattr(stdout, 'read'):
                output = stdout.read().rstrip()
            else:
                output = b''.join(list(stdout)).rstrip()
            if not isinstance(output, str):
                output = output.decode(self.encoding)
        else:
            output = ''
        return self._get_stdout(output)

    __str__ = __call__

    def __gt__(self, filename):
        return self._write(filename, 'wb+')

    def __rshift__(self, filename):
        return self._write(filename, 'ab+')

    def __or__(self, other):
        if isinstance(other.commands, property):
            other = other()
        if isinstance(self, Stdin):
            first = other.commands[0]
            first.previous = self
            return other
        cmds = deepcopy(self.commands) + deepcopy(other.commands)
        cmds = self._order(cmds)
        other = cmds[-1]
        return other

    def __bool__(self):
        return not self.failed
    __nonzero__ = __bool__

    def __repr__(self):
        return repr(self.commands_line)

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
                return self.__call__()
            else:
                for line in self.stdout:
                    fd.write(line)
                return self._get_stdout('')
        return None

    def _get_stdout(self, stdout):
        output = Stdout(stdout)
        output.stderr = self.stderr
        output.returncodes = self.returncodes
        output.failed = bool(output.returncodes)
        output.succeeded = not output.failed
        return output

    def _raise(self, args, kwargs):
        if isinstance(args, list):
            args = ' '.join(args)
        log.debug('Error while running Popen(%r, **%r)',
                  args, kwargs)
        raise OSError(args)


class Stdin(Pipe):

    def __init__(self, value):
        super(Stdin, self).__init__()
        self.value = value
        self._stdin = None

    @property
    def iter_stdout(self):
        if hasattr(self.value, 'seek'):
            self.value.seek(0)
        if hasattr(self.value, 'fileno'):
            r = self.value
        else:
            if hasattr(self.value, 'read'):
                value = self.value.read()
            else:
                value = self.value
            r, w = os.pipe()
            fd = os.fdopen(w, 'wb')
            fd.write(value)
            fd.close()
        return r

    def __deepcopy__(self, other):
        return self.__class__(self.value)


class Stdout(str):

    @property
    def stdout(self):
        return str(self)


class PyPipe(Pipe):

    @property
    def iter_stdout(self):
        return self.func(self.stdin)


class Base(object):
    not_piped = ['rm', 'mkdir', 'cp', 'touch', 'mv', 'scp', 'rsync']
    not_piped = sorted([str(c) for c in not_piped])

    def __init__(self, name, *cmd_args):
        self.__name__ = name
        self._cmds = {}
        self._cmd_args = []
        if cmd_args:
            self._cmd_args = [name] + list(cmd_args)

    def __getattr__(self, attr):
        attr = str(attr)
        if attr not in self._cmds:
            kw = dict(_chut=self,
                      _binary=attr,
                      _cmd_args=self._cmd_args,
                      _pipe=True)
            if attr in self.not_piped:
                kw['_pipe'] = False
            self._cmds[attr] = type(attr, (Pipe,), kw)
        return self._cmds[attr]

    def __repr__(self):
        if self.__host__:
            return '<%s %>' % (self.__name__, self.__host__)
        else:
            return '<%s>' % self.__name__


class Chut(Base):

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
        if self.__name__ not in ('sh', 'sudo'):
            raise ImportError('You can only run cd in local commands')
        os.chdir(directory)

    def stdin(self, value):
        return Stdin(value)

    def ssh(self, *args):
        return SSH('ssh', *args)

    @property
    def test(self):
        return Command('test')


class Command(Base):

    def __getattr__(self, attr):
        attr = str(attr)
        if attr not in self._cmds:
            cmd = self.__name__
            kw = dict(_chut=self,
                      _binary='',
                      _cmd_args=[cmd, '-' + attr],
                      _pipe=True)
            self._cmds[attr] = type(str(cmd), (Pipe,), kw)
        return self._cmds[attr]


class SSH(Base):

    def join(self, *args):
        return '%s%s' % (self, posixpath.join(*args))

    def __str__(self):
        return '%s:' % self._cmd_args[-1]

    def __call__(self, *args, **kwargs):
        cmds = []
        for a in args:
            if isinstance(a, Pipe):
                cmds.append(a.commands_line)
            else:
                cmds.append(a)
        return getattr(SSH('ssh', *self._cmd_args[1:]), '')(*cmds, **kwargs)


class ModuleWrapper(types.ModuleType):

    def __init__(self, mod, chut, name):
        self.__name__ = name
        for attr in ["__builtins__", "__doc__",
                     "__package__", "__file__"]:
            setattr(self, attr, getattr(mod, attr, None))
        self.__path__ = getattr(mod, '__path__', [])
        self.__test__ = getattr(mod, '__test__', {})
        self.mod = mod
        self.chut = chut

    def __getattr__(self, attr):
        if attr == '__all__':
            raise ImportError('You cant import things that does not exist')
        if hasattr(self.mod, attr):
            return getattr(self.mod, attr)
        else:
            return getattr(self.chut, attr)


env = Environ(os.environ.copy())
ch = Chut('sh')
sudo = Chut('sudo', '-s')

try:
    import fabric.operations
except ImportError:
    pass
else:
    def _run_command(command, *args, **kwargs):
        if hasattr(command, '_chut'):
            new_command = command.commands_line
            if isinstance(new_command, property):
                new_command = command().commands_line
        else:
            new_command = command
        return fab_run_command(new_command, *args, **kwargs)
    fab_run_command = fabric.operations._run_command
    fabric.operations._run_command = _run_command

if __name__ != '__main__':
    mod = sys.modules[__name__]
    sys.modules[__name__] = ModuleWrapper(mod, ch, __name__)
    sys.modules['chut.sudo'] = ModuleWrapper(mod, sudo, 'sudo')
