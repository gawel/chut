# -*- coding: utf-8 -*-
__doc__ = """Generate this page"""
from chut import *  # noqa

TEMPLATE = '''
%(binary)s
=========================================================

.. literalinclude:: ../chut/examples/%(filename)s
   :language: python

Get standalone `%(binary)s <_static/binaries/%(binary)s>`_

'''


@console_script
def example(args):
    fd = open('docs/examples.rst', 'w')
    fd.write((
        '==========================\n'
        'Examples\n'
        '==========================\n\n'))
    for filename in sorted(find('chut/examples -name *.py')):
        try:
            scripts = list(grep('-A1 -E @.*console_script', filename))
        except OSError:
            continue
        if not scripts:
            continue
        filename = path.basename(filename)
        scripts = [s[4:].split('(')[0] for s in scripts if s[0] != '@']
        binary = scripts[0].replace('_', '-')
        fd.write(TEMPLATE % dict(filename=filename, binary=binary))
    fd.close()
