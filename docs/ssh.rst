SSH
===

The ssh command take a host first and is gziped by default::

    >>> import chut as sh
    >>> from chut import gzip
    >>> from chut import ssh
    >>> srv1 = ssh('gawel@srv')
    >>> srv1.ls('~')
    'ssh gawel@srv ls ~'

For example you can backup your mysql database locally::

    >>> srv1.mysqldump('db | gzip') | gzip
    "ssh gawel@srv 'mysqldump db | gzip' | gzip"

Or on another server::

    >>> srv2 = ssh('gawel@srv2')
    >>> srv1(sh.mysqldump('db') | gzip | srv2('gunzip > ~/backup.db'))
    'ssh gawel@srv "mysqldump db | gzip | ssh gawel@srv2 \'gunzip > ~/backup.db\'"'

You can use your ssh instance to get some remote file::

    >>> sh.rsync(srv1.join('~/p0rn'), '.', pipe=True)
    'rsync gawel@srv:"~/p0rn" .'


