from __future__ import unicode_literals, print_function
import os
import re
import sys
import stat
import zlib
import time
import types
import base64
import shutil
import pathlib
import inspect
import logging
import functools
import posixpath
from subprocess import Popen
from subprocess import PIPE
from subprocess import STDOUT
from copy import deepcopy
from ConfigObject import ConfigObject
from contextlib import contextmanager

try:
    from fabric import api as fabric
except ImportError:
    HAS_FABRIC = False
else:  # pragma: no cover
    if 'nosetests' in sys.argv[0]:
        HAS_FABRIC = False
    else:
        HAS_FABRIC = True

__all__ = [
    'logopts', 'info', 'debug', 'error', 'exc',  # logging
    'console_script', 'requires', 'sh', 'pipe', 'env', 'ini', 'stdin', 'test',
    'ls', 'cat', 'grep', 'find', 'cut', 'tr', 'head', 'tail', 'sed', 'awk',
    'nc', 'ping', 'nmap', 'hostname', 'host', 'rsync', 'wget', 'curl',
    'cd', 'which', 'mktemp', 'echo', 'wc',
    'tar', 'gzip', 'gunzip', 'zip', 'unzip',
    'vlc', 'ffmpeg', 'convert',
    'virtualenv', 'pip',
    'git', 'hg', 'svn',
    'ssh', 'sudo',
    'path', 'pwd',  # path is posixpath, pwd return os.getcwd()
    'escape', 'e',  # e is escape()
]

__not_piped__ = ['chmod', 'cp', 'scp', 'mkdir', 'mv', 'rm', 'rmdir', 'touch']

__all__ += __not_piped__

log = logging.getLogger('chut')

aliases = dict(
    ifconfig='/sbin/ifconfig',
    sudo='/usr/bin/sudo',
    ssh='ssh',
)


class Log(object):

    initialized = False
    loggers = {}

    def __call__(self, args={'--quiet': False, '--verbose': False},
                 fmt=None, name=None, stream=sys.stderr):

        if not name:
            name = posixpath.basename(sys.argv[0])

        if name in self.loggers:
            return self.loggers[name]

        log = logging.getLogger(name)

        if not log.handlers:
            if fmt == 'brief':
                fmt = '[%(levelname)-4s] %(message)s'
            elif fmt == 'msg':
                fmt = '%(message)s'
            else:
                fmt = '%(asctime)s %(levelname)-6s %(name)s %(message)s'
            logging.basicConfig(stream=stream, format=fmt)

        if not log.level:  # pragma: no cover
            if args.get('--quiet'):
                level = logging.ERROR
            elif args.get('--debug'):
                level = logging.DEBUG
            else:
                level = logging.INFO

            log.setLevel(level)
        self.loggers[name] = log
        return log

    def log(self, name):
        def wrapper(*args, **kwargs):
            log = self()
            return getattr(log, str(name))(*args, **kwargs)
        wrapper.__name__ = str(name)
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
    if whoami != b'root':
        raise OSError('Not able to run sudo.')


def escape(value):
    chars = "|!`'[]() "
    esc = '\\'
    if isinstance(value, bytes):
        chars = chars.encode('ascii')
        esc = esc.encode('ascii')
    for c in chars:
        value = value.replace(c, esc + c)
    return value


def ini(filename, **defaults):
    """Load a .ini file in a ConfigObject. Dont raise if the file does not
    exist"""
    filename = sh.path(filename)
    defaults.update(home=sh.path('~'))
    return ConfigObject(filename=filename, defaults=defaults)


class Environ(dict):
    """Manage os.environ"""

    def __getattr__(self, attr):
        value = self.get(attr.upper(), None)
        if attr.lower() in ('path',):
            return value.split(os.pathsep)
        return value

    def __setattr__(self, attr, value):
        if isinstance(value, (list, tuple)):
            value = os.pathsep.join(value)
        self[attr.upper()] = value

    def __delattr__(self, attr):
        attr = attr.upper()
        if attr in self:
            del self[attr]

    def copy(self, **kwargs):
        environ = self.__class__(self)
        environ(**kwargs)
        return environ

    def __call__(self, **kwargs):
        return ChangeEnviron(self, **kwargs)


class ChangeEnviron:
    """Change the environment and keep a track of the previous one in
    order to restore it. This is meant to be used in a with statement."""

    def __init__(self, env, **kwargs):
        self._prevenv = Environ(env)
        self._env = env
        for k, v in kwargs.items():
            if v is None:
                delattr(self._env, k)
            else:
                setattr(self._env, k, v)

    def __enter__(self):
        return self._env

    def __exit__(self, type, value, traceback):
        # restore the previous values...
        self._env.update(self._prevenv)
        # and suppress the added keys
        for k in set(self._env.keys()) - set(self._prevenv):
            del self._env[k]


class Path(object):

    def __getattr__(self, attr):
        return getattr(posixpath, attr)

    def lib(self, *args):
        return self(*args, obj=True)

    @classmethod
    def __call__(cls, *args, **kwargs):
        if args:
            value = posixpath.expandvars(
                posixpath.expanduser(
                    posixpath.join(*args)))
        else:
            value = str()
        if value and 'obj' in kwargs or 'object' in kwargs:
            value = pathlib.Path(value)
        return value


class Pipe(object):
    """A pipe object. Represent a set of one or more commands."""

    _chut = None
    _pipe = True
    _cmd_args = []
    _sys_stdout = sys.stdout
    _sys_stderr = sys.stderr

    def __init__(self, *args, **kwargs):
        self._done = False
        self._stdout = None
        self._stderr = None
        self.args = list(args)
        self.previous = None
        self.processes = []
        encoding = kwargs.get('encoding')
        if not encoding:
            encoding = getattr(sys.stdout, 'encoding', None) or 'utf8'
        self.encoding = encoding
        self.kwargs = kwargs
        if 'sh' in kwargs:
            kwargs['shell'] = kwargs.pop('sh')
        if kwargs.get('stderr') == 1:
            kwargs['stderr'] = STDOUT
        if 'combine_stderr' in kwargs:
            kwargs.pop('combine_stderr')
            kwargs['stderr'] = STDOUT
        if 'pipe' in kwargs:
            if not kwargs.pop('pipe'):
                self._call_pipe()
        elif not self._pipe:
            self._call_pipe()

    def _call_pipe(self):
        self._done = True
        ret = self.__call__()
        if ret.failed:
            print(ret.stderr, file=sys.stderr)

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
            if not isinstance(output, str):
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
            if shell and any(i in cmd for i in '\'"*<>|& '):
                cmd = repr(str(cmd))
            args.append(cmd)
        else:
            import shlex
            args.extend(binary.split())
            for a in self.args:
                if isinstance(a, (list, tuple)):
                    args.extend(a)
                elif shell:
                    args.append(a)
                else:
                    args.extend(shlex.split(str(a)))

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
            elif cmd.kwargs.get("shell"):
                s = cmd.command_line(shell=True)
            else:
                args = []
                for arg in cmd.command_line():
                    if any(i in arg for i in '\'"*<>|& '):
                        args.append(repr(str(arg)))
                    else:
                        args.append(arg)
                s = " ".join(args)
            cmds.append(s.strip())
        return str(' | '.join(cmds))

    def bg(self):
        """Run processes in background. Return the last piped Popen object"""
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
                p = cmd
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
                    self._raise()

                self.processes.append(p)
                stdin = p.stdout
        return p

    def execv(self):
        cmd = self.command_line()
        binary = sh.which(cmd.pop(0))
        if binary:
            binary = str(binary)
            os.execve(binary, [binary] + cmd, env)
        else:
            raise OSError(binary)

    @property
    def stdout(self):
        """standard output of the pipe. A file descriptor or an iteraror"""
        p = self.bg()
        if isinstance(p, PyPipe):
            return p.iter_stdout
        else:
            return p.stdout

    @classmethod
    def map(cls, args,
            pool_size=None, stop_on_failure=False, **kwargs):
        """Run a batch of the same command and manage a pool of processes for
        you"""
        kw = dict(
            stdin=sys.stdin, stderr=PIPE,
            stdout=PIPE
        )
        kw.update(kwargs)
        if pool_size is None:
            import multiprocessing
            pool_size = multiprocessing.cpu_count()
        results = [None] * len(args)
        processes = []
        index = 0
        out_index = 0
        while args or processes:
            if args and len(processes) < pool_size:
                a = args.pop(0)
                if not isinstance(a, list):
                    a = [a]
                cmd = cls(*a)
                a = cmd.command_line(cmd.kwargs.get('shell', False))
                processes.append((index, cmd, Popen(a, **kw)))
                index += 1
            for i, cmd, p in processes:
                result = p.poll()
                if result is not None:
                    output = Stdout(p.stdout.read())
                    output.stderr = p.stderr.read()
                    output.returncodes = [result]
                    output.failed = bool(result)
                    output.succeeded = not output.failed
                    results[i] = output
                    processes.remove((i, cmd, p))
                    if out_index == i:
                        out_index += 1
                        yield results[i]
                    if result > 0 and stop_on_failure:
                        args = None
                        for index, cmd, p in processes:
                            if p.poll() is None:  # pragma: no cover
                                p.kill()
                        cmd._raise(output=output)
            time.sleep(.1)
        if out_index < len(results):  # pragma: no cover
            yield results[out_index]
            out_index += 1

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
        eol = '\n'
        for line in self.stdout:
            yield self._decode(line).rstrip(eol)
        if self.failed:
            self._raise(output=self._get_stdout(''))

    def __call__(self, **kwargs):
        if self._done and self._stdout is not None:
            return self._stdout
        for cmd in self.commands:
            if kwargs.get('shell'):
                cmd.kwargs['shell'] = True
            if kwargs.get('combine_stderr'):
                cmd.kwargs['stderr'] = STDOUT
            if kwargs.get('stderr'):
                cmd.kwargs['stderr'] = STDOUT
        stdout = self.stdout
        if stdout is not None:
            if hasattr(stdout, 'read'):
                output = stdout.read().rstrip()
            else:  # pragma: no cover
                output = b''.join(list(stdout)).rstrip()
            output = self._decode(output)
        else:
            output = ''
        output = self._get_stdout(output)
        if self._done:
            self._stdout = output
        return output

    def __str__(self):
        output = self.__call__()
        if self.failed:
            self._raise(output=output)
        return output

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

    def _write_to(self, fd):
        if not isinstance(self, PyPipe):
            self.kwargs['stdout'] = fd
            return self.__call__()
        else:
            for line in self.stdout:
                fd.write(line)
            return self._get_stdout('')

    def _write(self, filename, mode):
        if filename in (0,):
            with open('/dev/null', 'ab') as fd:
                output = self._write_to(fd)
        elif filename in (1, 2):
            if filename == 2:
                fd = self._sys_stderr
            else:
                fd = self._sys_stdout
            output = self._write_to(fd)
        else:
            with open(filename, mode) as fd:
                output = self._write_to(fd)
        if output.failed:
            self._raise(output=output)
        return output

    def _decode(self, output):
        if not isinstance(output, str):
            output = output.decode(self.encoding)
        return output

    def _get_stdout(self, stdout):
        if not isinstance(stdout, str):
            stdout = stdout.encode(self.encoding)
        output = Stdout(stdout)
        output.stderr = self.stderr
        output.returncodes = self.returncodes
        output.failed = bool(output.returncodes)
        output.succeeded = not output.failed
        return output

    def _raise(self, output=None):
        if not log.handlers:
            logging.basicConfig(stream=sys.stderr)
        if output is not None:
            if output.stderr:
                log.error(output.stderr)
            raise OSError(self.commands_line, output.stderr)
        raise OSError(self.commands_line)


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
                if not isinstance(self.value, bytes):
                    value = self.value.encode('ascii')
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
        return self


class PyPipe(Pipe):

    @property
    def iter_stdout(self):
        return self.func(self.stdin)

    def __deepcopy__(self, *args):
        return sh.wraps(self.func)


class Base(object):
    not_piped = [str(c) for c in __not_piped__]

    def __init__(self, name, *cmd_args):
        self.__name__ = name
        self._cmds = {}
        self._cmd_args = []
        if cmd_args:
            self._cmd_args = [name] + list(cmd_args)

    def set_debug(self, enable=True):
        if enable:
            log.setLevel(logging.DEBUG)
            if not log.handlers:
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

    path = Path()

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
        """Change the current directory"""
        return ChangeDir(directory)

    def pwd(self):
        """return os.path.abspath(os.getcwd())"""
        return os.path.abspath(os.getcwd())

    def stdin(self, value):
        return Stdin(value)

    def ssh(self, *args):
        return SSH('ssh', *args)


class ChangeDir:
    """Change to a new directory and keep a track of the previous directory in
    order to restore it. This is meant to be used in a with statement."""

    def __init__(self, dir):
        self._dir = os.path.realpath(dir)
        self._prevdir = env.pwd
        os.chdir(self._dir)
        env.pwd = self._dir

    def __enter__(self):
        return self._dir

    def __exit__(self, type, value, traceback):
        os.chdir(self._prevdir)
        env.pwd = self._prevdir


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
        p = posixpath.join(*args)
        host = str(self)
        quote = '"'
        if isinstance(p, bytes):
            host = host.encode('ascii')
            quote = quote.encode('ascii')
        return host + quote + escape(p) + quote

    def cd(self, *args):
        raise NotImplementedError('cd does not work with ssh')

    def pwd(self):
        raise NotImplementedError('pwd does not work with ssh')

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
        if attr == '__wrapped__':
            raise AttributeError()
        if attr == '__all__':
            if self.__name__ == 'chut':
                return [str(c) for c in __all__]
            else:  # pragma: no cover
                raise ImportError('You cant import things that does not exist')
        if getattr(self.mod, attr, None) is not None:
            return getattr(self.mod, attr)
        else:
            return getattr(self.chut, attr)

    __getitem__ = __getattr__


logopts = Log()
info = logopts.log('info')
debug = logopts.log('debug')
error = logopts.log('error')
warn = logopts.log('warn')
exc = logopts.log('exception')

env = Environ(os.environ.copy())
sh = Chut('sh')
sudo = Chut('sudo', '-s')
test = Command('test')
e = escape


def wraps_module(mod):
    sys.modules['chut'] = ModuleWrapper(mod, sh, 'chut')
    sys.modules['chut.sudo'] = ModuleWrapper(mod, sudo, 'sudo')

#####################
# Script generation #
#####################


def requires(*requirements, **kwargs):
    """Add extra dependencies in a virtualenv"""
    if '/.tox/' in sys.executable:
        venv = os.path.dirname(os.path.dirname(sys.executable))
    elif env.virtual_env:  # pragma: no cover
        venv = env.chut_virtualenv = env.virtual_env
    else:  # pragma: no cover
        venv = os.path.expanduser(kwargs.get('venv', '~/.chut/venv'))
    if not env.pip_download_cache:  # pragma: no cover
        env.pip_download_cache = os.path.expanduser('~/.chut/cache')
        sh.mkdir('-p', env.pip_download_cache)
    bin_dir = os.path.join(venv, 'bin')
    if bin_dir not in env.path:  # pragma: no cover
        env.path = [bin_dir] + env.path
    requirements = list(requirements)
    if 'chut' not in requirements:
        requirements.insert(0, 'chut')
    if not test.d(venv):  # pragma: no cover
        import urllib
        url = 'https://raw.github.com/pypa/virtualenv/master/virtualenv.py'
        urllib.urlretrieve(url, '/tmp/_virtualenv.py')
        sh[sys.executable]('-S /tmp/_virtualenv.py', venv) > 1
        sh.rm('/tmp/_virtualenv*', shell=True)
        info('Installing %s...' % ', '.join(requirements))
        sh.pip('install -qM', *requirements) > 1
    elif env.chut_virtualenv:
        upgrade = '--upgrade' in sys.argv
        if (env.chut_upgrade or upgrade):  # pragma: no cover
            installed = ''
        else:
            installed = str(sh.pip('freeze')).lower()
        requirements = [r for r in requirements if r.lower() not in installed]
        if requirements:  # pragma: no cover
            info('Updating %s...' % ', '.join(requirements))
            sh.pip('install -qM --upgrade', *requirements) > 1
    executable = os.path.join(bin_dir, 'python')
    if not env.chut_virtualenv:  # pragma: no cover
        env.chut_virtualenv = venv
        os.execve(executable, [executable] + sys.argv, env)


class console_script(object):
    """A decorator to take care of sys.argv via docopt"""

    options = (
        ('-q, --quiet', 'Quiet (No output)'),
        ('--debug', 'Debug mode (More output / pdb on failure)'),
        ('-v, --version', 'Show version'),
        ('-h, --help', 'Show this help'),
    )

    def __init__(self, *args, **opts):
        self._console_script = True
        self.logopts = opts.pop('logopts', {})
        for k in ('fmt', 'stream'):
            if k in opts:
                self.logopts[k] = opts.pop(k)
        self.docopts = opts
        self.func = self.doc = None
        self.wraps(args)

    def version(self):  # pragma: no cover
        version = getattr(sys.modules['__main__'], '__version__', 'unknown')
        py_version = sys.version.split(' ', 1)[0]
        args = (self.func.__name__, version, py_version)
        print('%s %s runing on python %s' % args)

    def wraps(self, args):
        if args:
            self.func = args[0]
            functools.wraps(self.func)(self)
            if 'help' not in self.docopts:
                self.docopts['help'] = True
            if 'doc' not in self.docopts:
                doc = getattr(self.func, '__doc__', None)
            else:
                doc = self.docopts.pop('doc')
            if doc is None:
                doc = 'Usage: %prog'
            name = self.func.__name__.replace('_', '-')
            doc = doc.replace('%prog', name).strip()
            if '%options' in doc:
                def options(match):
                    ll = match.groups()[-1]
                    if ll is not None:
                        fmt = '{0:<%s}{1}\n' % ll.strip('-s')
                    else:
                        fmt = '{0:<20}{1}\n'
                    opts = ''
                    for opt in self.options:
                        opts += fmt.format(*opt)
                    return opts
                doc = re.sub('(%options)(-[0-9]+s)*', options, doc)
            doc = doc.replace('\n    ', '\n')
            self.doc = doc

            if 'name' not in self.logopts:
                self.logopts['name'] = name
        return self

    def main(self, arguments=None):
        import docopt
        ret = isinstance(arguments, list)
        if ret:
            self.docopts['argv'] = arguments
        arguments = docopt.docopt(self.doc, **self.docopts)
        if arguments.get('--version') is True:  # pragma: no cover
            res = self.version()
        else:
            logopts(arguments, **self.logopts)
            try:
                res = self.func(arguments)
            except KeyboardInterrupt:  # pragma: no cover
                sys.exit(1)
            except Exception:  # pragma: no cover
                if arguments.get('--debug'):
                    info(('> Entering python debuger. '
                          'Use h for help, q to quit.'))
                    import pdb
                    pdb.post_mortem()
                    return 1
                else:
                    raise
        return res if ret else sys.exit(res)

    def __call__(self, *args, **kwargs):
        return self.main(*args, **kwargs) if self.func else self.wraps(args)


Chut.console_script = console_script


class Generator(object):
    """generate a script from a @console_script. args may contain some
    docopts like arguments"""

    _modules = {}

    def __init__(self, **args):
        self.version = args.get('--new-version') or args.get('version')
        self.devel = args.get('--devel') or args.get('devel')
        if self.devel:
            dest = 'bin'
        else:
            dest = args.get('--destination') or args.get('destination')
            dest = os.path.expanduser(dest or 'dist/scripts')
        sh.mkdir('-p', dest)
        self.dest = dest
        args.update(version=repr(str(args.get('--version') or 'unknown')),
                    interpreter=args.get('--interpreter', 'python3'))
        self.args = args
        self.mods = self.encode_modules(*args.get('modules', []))

    def encode_module(self, mod):
        if not hasattr(mod, '__file__'):
            mod = __import__(mod)
        name = str(mod.__name__)
        if name not in self._modules:
            data = inspect.getsource(mod)
            data = base64.encodestring(zlib.compress(data.encode('utf8')))
            code = '_chut_modules.append((%r, %r))\n' % (name, data)
            self._modules[name] = code
        return self._modules[name]

    def encode_modules(self, *modules):
        try:
            # check if the script is already chutified
            _chut_modules = sys.modules['__main__']._chut_modules
        except AttributeError:
            # get source from files
            modules = [
                'six', 'pathlib', 'docopt', 'ConfigObject',
                sys.modules[__name__]
            ] + list(modules)
            modules = ''.join([self.encode_module(m) for m in modules])
        else:  # pragma: no cover
            # get source from _chut_modules
            modules = ''
            for name, data in _chut_modules:
                modules += '_chut_modules.append((%r, %r))\n' % (name, data)
        return modules

    def generate(self, filename, args=None, **kwargs):
        if args is None:
            args = {}
        args.update(kwargs)
        dirname = os.path.dirname(filename)
        mod_name = inspect.getmodulename(filename)
        os.environ.update(env)

        console_scripts = list(sh.grep('-A4 -E @.*console_script', filename))
        console_scripts = [s for s in console_scripts if s.startswith('def ')]

        scripts = []
        loop = '--loop' in sys.argv or '-l' in sys.argv
        while not os.path.isfile(filename):  # pragma: no cover
            time.sleep(.1)
        mtime = os.stat(filename)[stat.ST_MTIME]
        if console_scripts and self.version:
            version = sh.grep('-E ^__version__', filename)
            if version:
                version = str(version).split('=')[1].strip('\'" ')
                if version != self.version:
                    info('bump %s version from %s to %s',
                         posixpath.basename(filename), version, self.version)
                    sh.sed((
                        '-i \'s/^__version__ =.*/__version__ = "%s"/\''
                    ) % self.version, filename, shell=True) > 1
        for func_name in sorted(set(console_scripts)):
            name = func_name[4:].split('(')[0]
            script = os.path.join(self.dest, name.replace('_', '-'))
            if os.path.isfile(script) and loop:  # pragma: no cover
                smtime = os.stat(script)[stat.ST_MTIME]
                if mtime <= smtime:
                    continue
            with open(script, 'w') as fd:
                fd.write(SCRIPT_HEADER % self.args + self.mods + LOAD_MODULES)
                if self.devel:
                    fd.write('sys.path.insert(0, "%s")\n' % dirname)
                    fd.write('import %s\n' % mod_name)
                    fd.write('__version__ = getattr(%s, ' % mod_name)
                    fd.write('"__version__", "unknown") + "-dev"\n')
                    fd.write('if __name__ == "__main__":\n')
                    fd.write('    %s.%s()\n' % (mod_name, name))
                else:
                    with open(filename) as mod:
                        fd.write(mod.read().replace('__main__',
                                                    '__chutified__'))
                        fd.write((
                            "\nif __name__ == '__main__':\n    %s()\n"
                        ) % name)
            executable = sh.chmod('+x', script)
            if executable:
                info(executable.commands_line)
                scripts.append(script)
            else:  # pragma: no cover
                error('failed to generate %s' % script)
        return scripts

    def __call__(self, location):
        scripts = []
        if os.path.isfile(location):
            scripts.extend(self.generate(location))
        elif os.path.isdir(location):
            filenames = sh.grep('-lRE --include=*.py @.*console_script',
                                location) | sh.grep('-v site-packages')
            for filename in sorted(filenames):
                scripts.extend(self.generate(filename))
        return scripts


SCRIPT_HEADER = '''
#!/usr/bin/env %(interpreter)s
# This script is generated with chut. Do NOT edit this file.
# All your changes will be lost at the next generation.

version = %(version)s

import base64, json, types, zlib, sys, os
os.environ['CHUTIFIED'] = '1'
PY3 = sys.version_info[0] == 3
_chut_modules = []
'''.lstrip()

LOAD_MODULES = '''
for name, code in _chut_modules:
    if PY3:
        if isinstance(code, str):
            code = code.encode('utf-8')
        code = zlib.decompress(base64.decodebytes(code))
    else:
        name = bytes(name)
        code = zlib.decompress(base64.decodestring(code))
    mod = types.ModuleType(name)
    globs = dict()
    if PY3:
        if isinstance(code, bytes):
            code = code.decode('utf-8')
        exec(code, globs)
    else:
        exec('exec code in globs')
    mod.__dict__.update(globs)
    if name == 'chut':
        mod.wraps_module(mod)
    else:
        sys.modules[name] = mod
from chut import env
'''.lstrip()

##########
# Fabric #
##########


class Fab(object):

    dirname = '.chutifab'
    scripts = []

    def _run(self, meth, script, *args, **kwargs):  # pragma: no cover
        if script not in self.scripts:
            scripts = sorted(sh.ls('.chutifab'))
            fabric.abort((
                'No such script {0}. Available scripts are:\n\n- {1}'
            ).format(script, '\n- '.join(scripts)))
        if HAS_FABRIC:
            meth = getattr(fabric, meth)
            with fabric.settings(fabric.hide('stdout', 'running')):
                res = meth(('test -d ~/{0} || mkdir ~/{0} && chmod 700 ~/{0}; '
                            'echo $HOME/{0}').format(self.dirname))
                remote = posixpath.join(res, script)
                fabric.put('.chutifab/' + script, remote, mode=0o700,
                           use_sudo=bool(meth.__name__ == 'sudo'))
            cmd = '{0} {1}'.format(remote, ' '.join(args))
            res = meth(cmd, **kwargs)
            return res

    def chutifab(self, *args):
        """Generate chut scripts contained in location"""
        ll = logging.getLogger(posixpath.basename(sys.argv[0]))
        level = ll.level
        ll.setLevel(logging.WARN)
        if not args:
            args = ['.']
        for location in args:
            Generator(destination='.chutifab')(location)
        ll.setLevel(level)
        self.scripts = sorted(sh.ls('.chutifab'))
        return self.scripts

    def run(self, script, *args, **kwargs):
        """Upload a script and run it. ``*args`` are used as command line
        arguments. ``**kwargs`` are passed to `fabric`'s `run`"""
        return self._run('run', script, *args, **kwargs)

    def sudo(self, script, *args, **kwargs):
        """Upload a script and run it using sudo. ``*args`` are used as command
        line arguments. ``**kwargs`` are passed to `fabric`'s `sudo`"""
        return self._run('sudo', script, *args, **kwargs)


fab = Fab()

if __name__ != '__main__':
    mod = sys.modules[__name__]
    wraps_module(mod)
