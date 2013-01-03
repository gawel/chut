import chut as sh
import inspect
import base64
import sys
import six
import os

SCRIPT_HEADER = '''
#!/usr/bin/env python
import base64, json, types, sys
PY3 = sys.version_info[0] == 3
mods = []
'''.lstrip()

LOAD_MODULES = '''
for name, code in mods:
    if PY3:
        if isinstance(code, str):
            code = code.encode('utf-8')
    else:
        name = bytes(name)
    code = base64.decodestring(code)
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

import six
'''.lstrip()


def encode_module(mod):
    if not hasattr(mod, '__file__'):
        mod = __import__(mod, globals(), locals(), [''])
    data = inspect.getsource(mod)
    data = base64.encodestring(six.b(data))
    return 'mods.append((%r, %r))\n' % (str(mod.__name__), data)


def generate(arguments, filename):
    if not os.path.isfile(filename):
        mod = __import__(filename, globals(), locals(), [''])
        filename = mod.__file__
        name = mod.__name__
    else:
        dirname = os.path.dirname(filename)
        sys.path.insert(0, dirname)
        name = inspect.getmodulename(filename)
        mod = __import__(name)

    filenames = []
    for k, v in mod.__dict__.items():
        if getattr(v, 'console_script', False) is True:
            filenames.append(k)

    if arguments['--list-entry-points']:
        for name in filenames:
            print(('%s = %s:%s' % (name.replace('_', '-'),
                                   mod.__name__, name)))
        sys.exit(0)

    dest = os.path.expanduser(arguments['--destination'])
    sh.mkdir('-p', dest)

    modules = [six, 'docopt', 'ConfigObject', sh] + arguments['<MODULE>']
    modules = ''.join([encode_module(m) for m in modules])
    for name in filenames:
        script = os.path.join(dest, name.replace('_', '-'))
        with open(script, 'w') as fd:
            fd.write(SCRIPT_HEADER + modules + LOAD_MODULES)
            fd.write(inspect.getsource(mod).replace('__main__',
                                                    '__chutified__'))
            fd.write("if __name__ == '__main__':\n    %s()\n" % name)
        executable = sh.chmod('+x', script)
        if executable:
            print(executable.commands_line)
        else:
            print('failed to generate %s' % script)


@sh.console_script
def chutify(arguments):
    """
    Usage: %prog [-d DIRNAME] <location> [<MODULE>...]
           %prog <location> (-l | -h)

    Generate binary scripts from all @console_script contained in <location>
    <location> can be a directory, a python file or a dotted name.

    -h, --help                         Print this help
    -d DIRNAME, --destination=DIRNAME  Destination [default: dist/scripts]
    -l, --list-entry-points            List console script entry points
    """
    location = arguments['<location>']
    location = os.path.expanduser(location)
    if os.path.isfile(location):
        generate(arguments, location)
    elif os.path.isdir(location):
        filenames = []
        filenames = sh.grep('-lRE --include=*.py @.*console_script',
                            location) | sh.grep('-v site-packages')
        filenames = [s.strip() for s in filenames]
        for filename in filenames:
            generate(arguments, filename)
    else:
        generate(arguments, location)
