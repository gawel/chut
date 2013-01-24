# -*- coding: utf-8 -*-
import chut as sh
import os


@sh.console_script
def chutify(arguments):
    """
    Usage: %prog [-d DIR] [--loop DELAY] [<location>] [<MODULE>...]
           %prog [<location>] (-l | -h)

    Generate binary scripts from all @console_script contained in <location>
    <location> can be a directory, a python file or a dotted name.

    -h, --help                 Print this help
    -d DIR, --destination=DIR  Destination [default: dist/scripts]
    -l, --list-entry-points    List console script entry points
    --loop DELAY               Generate scripts over and over
    """
    config = sh.ini('.chut')
    if sh.env.git_dir:
        ini = sh.path.join(sh.env.git_dir, 'hooks', 'chut.ini')
        if os.path.isfile(ini):
            config.read(ini)
    cfg = config.chut

    location = arguments.get('<location>') or cfg.location or os.getcwd()
    location = os.path.expanduser(location)

    if location.endswith('.git'):
        hooks = sh.path.join(location, 'hooks')
        hook = sh.path.join(hooks, 'pre-commit')
        if not __file__.endswith('chutify'):
            script = sh.generate(__file__, {'--destination': hooks})[0]
            sh.mv(script, hook)
        else:
            # install git hook
            sh.cp(__file__, hook)
        executable = sh.chmod('+x', hook)
        if executable:
            print(executable.commands_line)
        return

    if cfg.destination and arguments['--destination'] == 'dist/scripts':
        arguments['--destination'] = cfg.destination

    commands = cfg.run.as_list('\n')
    commands = [c.strip() for c in commands if c.strip()]

    def gen():
        scripts = []
        if os.path.isfile(location):
            scripts.extend(sh.generate(location, arguments))
        elif os.path.isdir(location):
            filenames = []
            filenames = sh.grep('-lRE --include=*.py @.*console_script',
                                location) | sh.grep('-v site-packages')
            filenames = [s.strip() for s in filenames]
            for filename in filenames:
                scripts.extend(sh.generate(filename, arguments))
        for cmd in commands:
            print('$ %s' % cmd)
            binary, args = cmd.split(' ', 1)
            sh[binary](args) > 2
        return scripts

    if arguments['--loop']:
        import time
        while True:
            try:
                gen()
                time.sleep(float(arguments['--loop']))
                print('--')
            except KeyboardInterrupt:
                return 0
    else:
        scripts = gen()
        if sh.env.git_dir:
            sh.git('add -f', *scripts) > 1
    return 0
