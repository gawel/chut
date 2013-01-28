from __future__ import unicode_literals, print_function
import os
import sys
import six
import stat
import zlib
import time
import types
import base64
import shutil
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

__all__ = [
    'console_script', 'requires', 'sh', 'env', 'ini', 'stdin', 'test',
    'ls', 'cat', 'grep', 'find', 'cut', 'tr', 'head', 'tail', 'sed', 'awk',
    'nc', 'ping', 'nmap', 'hostname', 'host', 'scp', 'rsync', 'wget', 'curl',
    'cd', 'which', 'mktemp', 'echo', 'wc',
    'tar', 'gzip', 'gunzip', 'zip', 'unzip',
    'vlc', 'ffmpeg', 'convert',
    'virtualenv', 'pip',
    'git', 'hg', 'svn',
    'ssh', 'sudo',
    'path', 'pwd',  # path is posixpath, pwd return os.getcwd()
    'escape', 'e',  # e is escape()
]

__not_piped__ = ['chmod', 'cp', 'mkdir', 'mv', 'rm', 'rmdir', 'touch']

__all__ += __not_piped__

log = logging.getLogger('chut')

aliases = dict(
    ifconfig='/sbin/ifconfig',
    sudo='/usr/bin/sudo',
    ssh='ssh',
  )


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
    if whoami != six.b('root'):
        raise OSError('Not able to run sudo.')


def escape(value):
    chars = "|!`'[]() "
    esc = '\\'
    if isinstance(value, six.binary_type):
        chars = chars.encode('ascii')
        esc = esc.encode('ascii')
    for c in chars:
        value = value.replace(c, esc + c)
    return value


def ini(filename, **defaults):
    """Load a .ini file in a ConfigObject. Dont raise if the file does not
    exist"""
    filename = os.path.expanduser(filename)
    defaults.update(home=os.path.expanduser('~'))
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
            for c in '\'"*<>|':
                if c in cmd:
                    cmd = repr(str(cmd))
                    break
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
                            if p.poll() is None:
                                p.kill()
                        cmd._raise(output=output)
            time.sleep(.1)
        if out_index < len(results):
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
        for line in self.stdout:
            yield self._decode(line).rstrip('\n')

    def __call__(self, **kwargs):
        if self._done and self._stdout is not None:
            return self._stdout
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
            output = self._decode(output)
        else:
            output = ''
        output = self._get_stdout(output)
        if self._done:
            self._stdout = output
        return output

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

    def _write_to(self, fd):
        if not isinstance(self, PyPipe):
            self.kwargs['stdout'] = fd
            return self.__call__()
        else:
            for line in self.stdout:
                fd.write(line)
            return self._get_stdout('')

    def _write(self, filename, mode):
        if isinstance(filename, int):
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
        if six.PY3 and not isinstance(output, six.text_type):
            output = output.decode(self.encoding)
        return output

    def _get_stdout(self, stdout):
        if not six.PY3 and not isinstance(stdout, six.binary_type):
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

    path = posixpath

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
        if self.__name__ not in ('sh', 'sudo'):
            raise ImportError('You can only run cd in local commands')
        directory = os.path.realpath(directory)
        os.chdir(directory)
        env.pwd = directory

    def pwd(self):
        """return os.path.abspath(os.getcwd())"""
        if self.__name__ not in ('sh', 'sudo'):
            raise ImportError('You can only use pwd in local commands')
        return os.path.abspath(os.getcwd())

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
        p = posixpath.join(*args)
        host = str(self)
        quote = '"'
        if isinstance(p, six.binary_type):
            host = host.encode('ascii')
            quote = quote.encode('ascii')
        return host + quote + escape(p) + quote

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
            if self.__name__ == 'chut':
                return [str(c) for c in __all__]
            else:
                raise ImportError('You cant import things that does not exist')
        if hasattr(self.mod, attr):
            return getattr(self.mod, attr)
        else:
            return getattr(self.chut, attr)

    __getitem__ = __getattr__


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
    elif env.virtual_env:
        venv = env.chut_virtualenv = env.virtual_env
    else:
        venv = os.path.expanduser(kwargs.get('venv', '~/.chut/venv'))
    if not env.pip_download_cache:
        env.pip_download_cache = os.path.expanduser('~/.chut/cache')
        sh.mkdir('-p', env.pip_download_cache)
    bin_dir = os.path.join(venv, 'bin')
    if bin_dir not in env.path:
        env.path = [bin_dir] + env.path
    requirements = list(requirements)
    if 'chut' not in requirements:
        requirements.insert(0, 'chut')
    if not test.d(venv):
        import urllib
        url = 'https://raw.github.com/pypa/virtualenv/master/virtualenv.py'
        urllib.urlretrieve(url, '/tmp/_virtualenv.py')
        sh[sys.executable]('-S /tmp/_virtualenv.py', venv) > 1
        sh.rm('/tmp/_virtualenv*', shell=True)
        print('Installing %s...' % ', '.join(requirements))
        sh.pip('install -qM', *requirements) > 1
    elif env.chut_virtualenv:
        upgrade = '--upgrade' in sys.argv
        if (env.chut_upgrade or upgrade):
            installed = ''
        else:
            installed = str(sh.pip('freeze')).lower()
        requirements = [r for r in requirements if r.lower() not in installed]
        if requirements:
            print('Updating %s...' % ', '.join(requirements))
            sh.pip('install -qM --upgrade', *requirements) > 1
    executable = os.path.join(bin_dir, 'python')
    if not env.chut_virtualenv:
        env.chut_virtualenv = venv
        os.execve(executable, [executable] + sys.argv, env)


class console_script(object):
    """A decorator to take care of sys.argv via docopt"""

    def __init__(self, *args, **opts):
        self._console_script = True
        self.docopts = opts
        self.func = self.doc = None
        self.wraps(args)

    def version(self):
        version = getattr(sys.modules['__main__'], 'version', 'unknown')
        print('%s %s' % (self.func.__name__, version))

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
            doc = doc.replace('\n    ', '\n')
            self.doc = doc
        return self

    def main(self, arguments=None):
        import docopt
        ret = isinstance(arguments, list)
        if ret:
            self.docopts['argv'] = arguments
        arguments = docopt.docopt(self.doc, **self.docopts)
        if arguments.get('--version') is True:
            res = self.version()
        else:
            try:
                res = self.func(arguments)
            except KeyboardInterrupt:
                sys.exit(1)
        return res if ret else sys.exit(res)

    def __call__(self, *args, **kwargs):
        return self.main(*args, **kwargs) if self.func else self.wraps(args)


class Generator(object):
    """generate a script from a @console_script. args may contain some
    docopts like arguments"""

    _modules = {}

    def __init__(self, **args):
        self.devel = args.get('--devel') or args.get('devel')
        if self.devel:
            dest = 'bin'
        else:
            dest = args.get('--destination') or args.get('destination')
            dest = os.path.expanduser(dest or 'dist/scripts')
        sh.mkdir('-p', dest)
        self.dest = dest
        args.update(version=repr(str(args.get('--version') or 'unknown')),
                    interpreter=args.get('--interpreter', 'python'))
        self.args = args
        self.mods = self.encode_modules(*args.get('modules', []))

    def encode_module(self, mod):
        if not hasattr(mod, '__file__'):
            mod = __import__(mod)
        name = str(mod.__name__)
        if name not in self._modules:
            data = inspect.getsource(mod)
            data = base64.encodestring(zlib.compress(six.b(data)))
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
                'six', 'docopt', 'ConfigObject', sys.modules[__name__]
            ] + list(modules)
            modules = ''.join([self.encode_module(m) for m in modules])
        else:
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
        while not os.path.isfile(filename):
            time.sleep(.1)
        mtime = os.stat(filename)[stat.ST_MTIME]
        for func_name in sorted(set(console_scripts)):
            name = func_name[4:].split('(')[0]
            script = os.path.join(self.dest, name.replace('_', '-'))
            if os.path.isfile(script) and loop:
                smtime = os.stat(script)[stat.ST_MTIME]
                if mtime <= smtime:
                    continue
            with open(script, 'w') as fd:
                fd.write(SCRIPT_HEADER % self.args + self.mods + LOAD_MODULES)
                if self.devel:
                    fd.write('sys.path.insert(0, "%s")\n' % dirname)
                    fd.write('import %s\n' % mod_name)
                    fd.write('if __name__ == "__main__":\n')
                    fd.write('    %s.%s()\n' % (mod_name, name))
                else:
                    with open(filename) as mod:
                        fd.write(mod.read().replace('__main__',
                                                    '__chutified__'))
                    fd.write("\nif __name__ == '__main__':\n    %s()\n" % name)
            executable = sh.chmod('+x', script)
            if executable:
                print(executable.commands_line)
                scripts.append(script)
            else:
                print('failed to generate %s' % script)
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

if __name__ != '__main__':
    mod = sys.modules[__name__]
    wraps_module(mod)
