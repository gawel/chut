# -*- coding: utf-8 -*-
from chut import *  # noqa

__version__ = "0.17"


@console_script(fmt='msg')
def ssh_mount(args):
    """
    Usage: %prog [options] [<server>] [<mountpoint>]

    Use sshfs/fusermount to mount/umount your remote servers

    By default ~ is mounted but you can set the mountpoints in ~/.ssh/sshfs:

    [mountpoints]
    myserver = ./path

    Options:
    -u, --umount        Umount
    %options
    """
    env.lc_all = 'C'
    server = args['<server>']
    if not server:
        if not args['--umount']:
            sh.mount() | grep('--color=never fuse.sshfs') > 1
        else:
            for line in sh.mount() | grep('--color=never fuse.sshfs'):
                dirname = line.split(' ')[2]
                info('umount %s', dirname)
                sh.fusermount('-u', dirname) > 0
        return 0
    dirname = path.expanduser('~/mnt/%s' % server)
    if sh.mount() | grep(dirname):
        info('umount %s', dirname)
        sh.fusermount('-u', dirname) > 0
    if args['--umount']:
        return 0
    if not test.d(dirname):
        mkdir('-p', dirname)
    cfg = ini('~/.ssh/sshfs')
    mountpoint = '%s:%s' % (
        server,
        args['<mountpoint>'] or cfg['mountpoints'][server] or '.'
    )
    info('mount %s to %s', mountpoint, dirname)
    sh.sshfs(mountpoint, dirname) > 1
