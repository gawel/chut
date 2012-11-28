from __future__ import unicode_literals
import os
import sys
import six
import types
import logging
import shutil
import functools
import posixpath
from subprocess import Popen
from subprocess import PIPE
from subprocess import STDOUT
from copy import deepcopy
from contextlib import contextmanager

log = logging.getLogger('chut')

aliases = dict(
    ifconfig='/sbin/ifconfig',
    sudo='/usr/bin/sudo',
    ssh='ssh',
  )


def console_script(func):
    @functools.wraps(func)
    def wrapper(arguments=None):
        doc = getattr(func, '__doc__', None)
        if doc is None:
            doc = 'Usage: %prog'
        name = func.__name__.replace('_', '-')
        doc = doc.replace('%prog', name).strip()
        doc = doc.replace('\n    ', '\n')
        # take care if a script is chutified
        if 'docopt' not in sys.modules:
            import docopt
        else:
            docopt = sys.modules['docopt'] # NOQA
        if isinstance(arguments, list):
            arguments = docopt.docopt(doc, args=arguments)
            return func(arguments)
        else:
            arguments = docopt.docopt(doc, help=True)
            sys.exit(func(docopt.docopt(doc)))
    wrapper.console_script = True
    return wrapper


def check_sudo():
    sudo = aliases.get('sudo')
    if not os.path.isfile(sudo):
        raise OSError('sudo is not installed')
    args = [sudo, '-s', 'whoami']
    kwargs = dict(stdout=PIPE, stderr=STDOUT)
    log.debug('Popen(%r, **%r)', args, kwargs)
    whoami = Popen(args, env=env, **kwargs)
    whoami.wait()
    whoami = whoami.stdout.read().strip()
    if whoami != 'root':
        raise OSError('Not able to run sudo')


class Environ(dict):
    """Manage os.environ"""

    def __getattr__(self, attr):
        return self.get(attr.upper(), None)

    def __setattr__(self, attr, value):
        if isinstance(value, (list, tuple)):
            value = os.pathsep.join(value)
        self[attr.upper()] = value

    def __call__(self, **kwargs):
        environ = self.__class__(self.copy())
        for k, v in kwargs.items():
            setattr(environ, k, v)
        return environ


class Pipe(object):
    """A pipe object. Represent a set of one or more commands."""

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
            kwargs['stderr'] = STDOUT
        if 'binary' in kwargs:
            self._binary = kwargs.pop('binary')
        if 'pipe' in kwargs:
            if not kwargs.pop('pipe'):
                self.__call__()
        elif not self._pipe:
            self.__call__()

    @property
    def returncodes(self):
        """A list of return codes of all processes launched by the pipe"""
        for p in self.processes:
            p.wait()
        codes = [p.poll() for p in self.processes]
        if set(codes) == set([0]):
            return []
        return codes

    @property
    def failed(self):
        """True if one or more process failed"""
        output = self.__call__()
        return output.failed

    @property
    def succeeded(self):
        """True if all processes succeeded"""
        output = self.__call__()
        if output.succeeded:
            return output or True
        return False

    @property
    def stderr(self):
        """combined stderr of all processes"""
        if self._stderr is None:
            stderr = [p.stderr.read() for p in self.processes if p.stderr]
            output = b'\n'.join(stderr).strip()
            if not isinstance(output, six.text_type):
                output = output.decode(self.encoding, 'ignore')
            self._stderr = output
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

        if 'sudo' in args:
            args[0:1] = [aliases.get('sudo')]

        binary = self._binary
        if self._cmd_args[:1] == ['ssh']:
            cmd = '%s %s' % (binary, ' '.join(self.args))
            cmd = cmd.strip()
            if ('|' in cmd or '>' in cmd) and shell:
                cmd = repr(str(cmd))
            args.append(cmd)
        else:
            args.extend(binary.split())
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
        """standard output of the pipe. A file descriptor or an iteraror"""
        p = None
        self.processes = []
        self._stderr = None
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
                    stdin=stdin, stderr=PIPE,
                    stdout=PIPE
                    )
                kwargs.update(cmd.kwargs)
                env_ = kwargs.pop('env', env)

                log.debug('Popen(%r, **%r)', args, kwargs)

                kwargs['env'] = env_

                try:
                    p = Popen(args, **kwargs)
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
                cmd.kwargs['stderr'] = STDOUT
        stdout = self.stdout
        if stdout is not None:
            if hasattr(stdout, 'read'):
                output = stdout.read().rstrip()
            else:
                output = b''.join(list(stdout)).rstrip()
            if not isinstance(output, six.text_type):
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

    def __deepcopy__(self, *args):
        return self.__class__(*self.args, **self.kwargs)

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
        if not six.PY3 and not isinstance(stdout, six.binary_type):
            stdout = stdout.encode(self.encoding)
        output = Stdout(stdout)
        output.stderr = self.stderr
        output.returncodes = self.returncodes
        output.failed = bool(output.returncodes)
        output.succeeded = not output.failed
        return output

    def _raise(self, args, kwargs):
        if isinstance(args, list):
            args = ' '.join(args)
        env_ = kwargs.pop('env')
        log.debug('Error while running Popen(%r, **%r)',
                  args, kwargs)
        kwargs['env'] = env_
        raise OSError(args)


class Stdin(Pipe):
    """Used to inject some data in the pipe"""

    stderr = ''
    returncodes = []

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
                if not isinstance(self.value, six.binary_type):
                    value = six.b(self.value)
                else:
                    value = self.value
            r, w = os.pipe()
            fd = os.fdopen(w, 'wb')
            fd.write(value)
            fd.close()
        return r

    def __deepcopy__(self, *args):
        return self.__class__(self.value)

    def _write(self, filename, mode):
        with open(filename, mode) as fd:
            if hasattr(self.value, 'seek'):
                self.value.seek(0)
            if hasattr(self.value, 'read'):
                shutil.copyfileobj(self.value, fd)
            else:
                fd.write(self.value)
        return self._get_stdout('')


class Stdout(str):
    """A string with extra attributes:

    - succeeded
    - failed
    - stdout
    - stderr
    """

    @property
    def stdout(self):
        return str(self)


class PyPipe(Pipe):

    @property
    def iter_stdout(self):
        return self.func(self.stdin)

    def __deepcopy__(self, *args):
        return ch.wraps(self.func)


class Base(object):
    not_piped = ['rm', 'mkdir', 'cp', 'touch', 'mv', 'scp', 'rsync']
    not_piped = sorted([str(c) for c in not_piped])

    def __init__(self, name, *cmd_args):
        self.__name__ = name
        self._cmds = {}
        self._cmd_args = []
        if cmd_args:
            self._cmd_args = [name] + list(cmd_args)

    def set_debug(self, enable=True):
        if enable:
            log.setLevel(logging.DEBUG)
            log.addHandler(logging.StreamHandler(sys.stdout))
        else:
            log.setLevel(logging.INFO)

    def __getattr__(self, attr):
        attr = str(attr)
        if attr not in self._cmds:
            kw = dict(_chut=self,
                      _binary=str(aliases.get(attr, attr)),
                      _cmd_args=self._cmd_args,
                      _pipe=True)
            if attr in self.not_piped:
                kw['_pipe'] = False
            self._cmds[attr] = type(attr, (Pipe,), kw)
        return self._cmds[attr]

    __getitem__ = __getattr__

    def __repr__(self):
        return '<%s>' % self.__name__


class Chut(Base):

    def wraps(self, func):
        return type(func.__name__, (PyPipe,), {'func': staticmethod(func)})()

    @contextmanager
    def pipes(self, cmd):
        try:
            yield cmd
        finally:
            if cmd.returncodes:
                stderr = cmd.stderr
                log.error('Error while running %r\n%s', cmd, stderr)
                raise OSError(stderr)

    def pipe(self, binary, *args, **kwargs):
        pipe = getattr(self, str(binary))
        return pipe(*args, **kwargs)

    def cd(self, directory):
        if self.__name__ not in ('sh', 'sudo'):
            raise ImportError('You can only run cd in local commands')
        os.chdir(directory)

    def stdin(self, value):
        return Stdin(value)

    def ssh(self, *args):
        return SSH('ssh', *args)


class Command(Base):
    """A command (like test)"""

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
    """A ssh server"""

    def join(self, *args):
        return '%s%s' % (self, posixpath.join(*args))

    @property
    def host(self):
        return self._cmd_args[-1]

    def __str__(self):
        return '%s:' % self.host

    def __call__(self, *args, **kwargs):
        cmds = []
        for a in args:
            if isinstance(a, Pipe):
                cmds.append(a.commands_line)
            else:
                cmds.append(a)
        srv = getattr(SSH(aliases.get('ssh'), *self._cmd_args[1:]), '')
        return srv(*cmds, **kwargs)


class ModuleWrapper(types.ModuleType):
    """wrap chut and add extra attributes from classes"""

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

    __getitem__ = __getattr__


env = Environ(os.environ.copy())
ch = Chut('sh')
sudo = Chut('sudo', '-s')
test = Command('test')

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


def wraps_module(mod):
    sys.modules['chut'] = ModuleWrapper(mod, ch, 'chut')
    sys.modules['chut.sudo'] = ModuleWrapper(mod, sudo, 'sudo')

if __name__ != '__main__':
    mod = sys.modules[__name__]
    wraps_module(mod)
