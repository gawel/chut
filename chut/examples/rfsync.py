# -*- coding: utf-8 -*-
from chut import *  # NOQA
import sys


@console_script(fmt='msg')
def rfsync(args):
    """
    Usage: %prog [-p] <host>:<path> [-- <find_options>...]
           %prog [-] [<destination>] [-- <rsync_options>...]
           %prog -h

    Find some files on a remote server and sync them on a local directory using
    rsync

    Examples:

        $ rfsync gawel@example.com:~/ -- -name "*.avi" | rfsync
        $ rfsync gawel@example.com:~/ -- -size +100M | rfsync ~/Movies -- -q

    """
    remote = args.get('<host>:<path>')
    if remote not in (None, '-') and ':' in remote:
        host, p = remote.split(':')
        srv = ssh(host)
        options = []
        for a in args.get('<find_options>', []) or []:
            if '*' in a:
                a = '"%s"' % a
            options.append(a)
        options = ' '.join(options)
        done = set()
        for line in srv.find(p, options, shell=True):
            line = line.strip()
            if args['-p']:
                line = path.dirname(line)
            if line not in done:
                done.add(line)
                print(srv.join(line))
    else:
        destination = args['<host>:<path>'] or args['<destination>'] or '.'
        destination = path.expanduser(path.expandvars(destination))
        options = ' '.join(args.get('<rsync_options>', [])) or '-aP'
        targets = sys.stdin.readlines()
        targets = [t.strip('\n/') for t in targets]
        targets = [t.strip('/ ') for t in targets if t.strip('/ ')]
        targets = sorted(set(targets))
        if not targets:
            return 1
        if '-q' not in options:
            info('$ rsync %s \\\n\t%s \\\n\t%s',
                 options,
                 ' \\\n\t'.join(targets),
                 destination)
        rsync(options, ' '.join(targets), destination, shell=True) > 1
