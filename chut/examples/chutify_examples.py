# -*- coding: utf-8 -*-
from chut import *  # NOQA
__doc__ = """
Generate standalone script from examples
"""


@console_script
def chutify_examples(args):
    env.path = ['/bin', '/usr/bin', 'bin']
    rm('-Rf', 'dist/scripts', 'docs/_static/binaries')
    sh.chutify('chut/examples') > 2
    ls('dist/scripts') > 1
    mkdir('-p docs/_static/binaries') > 2
    mv('dist/scripts/*', 'docs/_static/binaries/', shell=True)
    print('Generated scripts:')
    ls('docs/_static/binaries') > 1

if __name__ == '__main__':
    chutify_examples()
