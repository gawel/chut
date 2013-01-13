# -*- coding: utf-8 -*-
import chut as sh
import os


@sh.console_script
def chutify(arguments):
    """
    Usage: %prog [-d DIRNAME] [<location>] [<MODULE>...]
           %prog [<location>] (-l | -h)

    Generate binary scripts from all @console_script contained in <location>
    <location> can be a directory, a python file or a dotted name.

    -h, --help                         Print this help
    -d DIRNAME, --destination=DIRNAME  Destination [default: dist/scripts]
    -l, --list-entry-points            List console script entry points
    """
    location = arguments.get('<location>') or os.getcwd()
    location = os.path.expanduser(location)
    if os.path.isfile(location):
        sh.generate(location, arguments)
    elif os.path.isdir(location):
        filenames = []
        filenames = sh.grep('-lRE --include=*.py @.*console_script',
                            location) | sh.grep('-v site-packages')
        filenames = [s.strip() for s in filenames]
        for filename in filenames:
            sh.generate(filename, arguments)
    return 0
