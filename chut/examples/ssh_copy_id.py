import os
import chut as sh
from chut import test


@sh.console_script
def ssh_copy_id(args):
    """
    Usage: %prog <host>
           %prog <pubkey> <host>
    """
    stdin = None
    pubkey = args['<pubkey>']

    if not pubkey and sh.env.SSH_AUTH_SOCK:
        ret = str(sh.pipe('ssh-add', '-L', combine_stderr=True))
        if ret.succeeded:
            stdin = sh.stdin(ret.strip() + '\n')

    if stdin is None:
        if not pubkey:
            pubkey = os.path.expanduser('~/.ssh/id_rsa.pub')
        if not test.e(pubkey):
            print('Cant find a valid key')
            return 1
        stdin = sh.cat(pubkey)

    srv = sh.ssh(args['<host>'])
    if stdin | srv(("umask 077; test -d .ssh || mkdir .ssh;"
                    "cat >> .ssh/authorized_keys")):
        print('Key added to %s' % (args['<host>'],))
        print('Trying to cat %s~/.ssh/authorized_keys...' % srv)
        print(srv.cat('~/.ssh/authorized_keys') | sh.tail('-n1'))
        return 0
    print('Failed to add key')
    return 1

if __name__ == '__main__':
    ssh_copy_id()
