import chut as sh
import inspect
import base64
import sys
import six
import os


def encode_module(mod):
    if not hasattr(mod, '__file__'):
        mod = __import__(mod, globals(), locals(), [''])
    data = inspect.getsource(mod)
    data = base64.encodestring(six.b(data))
    return 'mods.append((%r, %r))\n' % (mod.__name__, data)


@sh.console_script
def chutify(arguments):
    """
    Usage: %prog <scripts> [<MODULE>...]
           %prog <scripts> (-l | -h)

    -h, --help               Print this help
    -l, --list-entry-points  List console script entry points
    """
    filename = arguments['<scripts>']
    if not os.path.isfile(filename):
        mod = __import__(filename, globals(), locals(), [''])
        filename = mod.__file__
        name = mod.__name__
    else:
        name = os.path.splitext(os.path.basename(filename))[0]
        dirname = os.path.dirname(filename)
        sys.path.insert(0, dirname)
        mod = __import__(name)

    scripts = []
    for k, v in mod.__dict__.items():
        if getattr(v, 'console_script', False) is True:
            scripts.append(k)

    if arguments['--list-entry-points']:
        for name in scripts:
            print(('%s = %s:%s' % (name, mod.__name__, name)))
        sys.exit(0)

    modules = [six, 'docopt', sh] + arguments['<MODULE>']
    modules = ''.join([encode_module(m) for m in modules])
    sh.mkdir('-p dist/scripts')
    for name in scripts:
        script = 'dist/scripts/%s' % name
        with open(script, 'w') as fd:
            fd.write((
                '#!/usr/bin/env python\n'
                'import base64, json, types, sys\n'
                'PY3 = sys.version_info[0] == 3\nmods = []\n'))

            fd.write(modules)
            fd.write('''
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
    sys.modules[name] = mod

import six
''')
            fd.write(inspect.getsource(mod).replace('__main__',
                                                    '__chutified__'))
            fd.write('''
if __name__ == '__main__':
    %s()
''' % name)
        print('writing %s' % script)
        executable = sh.chmod('+x', script)
        if executable:
            print(executable.commands_line)
