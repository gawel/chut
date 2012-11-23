# -*- coding: utf-8 -*-
import chut as sh
__doc__ = """
Generate standalone script from examples
"""


@sh.console_script
def chutify_examples(args):
    sh.env.path = ['/bin', '/usr/bin', 'bin']
    sh.rm('-Rf', 'dist/scripts', 'docs/_static/binaries')()
    sh.mkdir('-p docs/_static/binaries')()
    for mod in sh.ls('chut/examples'):
        mod = mod.strip()
        if mod.startswith('_') or not mod.endswith('.py'):
            continue
        print(sh.chutify('chut.examples.%s' % mod[:-3]))
    sh.mv('dist/scripts/*', 'docs/_static/binaries/', shell=True)()
    print('Generated scripts:')
    print(sh.ls('docs/_static/binaries'))

if __name__ == '__main__':
    chutify_examples()
