# -*- coding: utf-8 -*-
from chut import *


@console_script
def github_clone(args):
    """Usage: %prog [<user>]

    Clone all github repository for a user using ssh
    """
    user = args['<user>'] or 'gawel'
    page = wget('-O- https://github.com/%s?tab=repositories' % user)
    for line in page | grep('href="/%s/' % user) | grep('-v title='):
        repo = line.split('"')[1]
        name = repo.split('/', 1)[-1]
        if not test.d(name) and name not in ('followers', 'following'):
            try:
                git('clone', 'git@github.com:%s' % repo.strip('/')) > 1
            except OSError:
                pass

if __name__ == '__main__':
    github_clone()
