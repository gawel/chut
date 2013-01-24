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
    cfg = sh.ini('.chut').chut
    location = arguments.get('<location>') or cfg.location or os.getcwd()
    location = os.path.expanduser(location)
    if cfg.destination and arguments['--destination'] == 'dist/scripts':
        arguments['--destination'] = cfg.destination

    commands = cfg.run.as_list('\n')
    commands = [c.strip() for c in commands if c.strip()]

    def gen():
        if os.path.isfile(location):
            sh.generate(location, arguments)
        elif os.path.isdir(location):
            filenames = []
            filenames = sh.grep('-lRE --include=*.py @.*console_script',
                                location) | sh.grep('-v site-packages')
            filenames = [s.strip() for s in filenames]
            for filename in filenames:
                sh.generate(filename, arguments)
        for cmd in commands:
            print('$ %s' % cmd)
            binary, args = cmd.split(' ', 1)
            sh[binary](args) > 2

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
        gen()
    return 0
