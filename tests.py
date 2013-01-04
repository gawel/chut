# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import six
import unittest
import chut as sh


class Chut(unittest.TestCase):

    def test_slices(self):
        pipe = sh.cat('tmp') | sh.grep('tmp') | sh.wc('-l')
        self.assertEqual(pipe[0:1]._binary, 'cat')
        self.assertEqual(pipe.__getitem__(slice(0, 1))._binary, 'cat')
        self.assertEqual(pipe.__getslice__(0, 1)._binary, 'cat')
        self.assertEqual(pipe[1:]._binary, 'wc')
        self.assertEqual(pipe.__getitem__(slice(1, 3))._binary, 'wc')
        self.assertEqual(pipe.__getslice__(1, 3)._binary, 'wc')

    def test_redirect_binary(self):
        with sh.pipes(sh.cat(__file__)) as cmd:
            cmd > 'tmp'
        ls = str(sh.ls('-l tmp'))

        with sh.pipes(sh.cat(__file__)) as cmd:
            cmd >> 'tmp'
        self.assertFalse(ls == str(sh.ls('-l tmp')))
        sh.rm('tmp')

    def test_redirect_python(self):

        @sh.wraps
        def grep(stdin):
            for line in stdin:
                if b'__' in line:
                    yield line

        pipe = sh.cat(__file__) | grep
        with sh.pipes(pipe) as cmd:
            cmd > 'tmp'
        ls = str(sh.ls('-l tmp'))
        with sh.pipes(pipe) as cmd:
            cmd >> 'tmp'
        self.assertFalse(ls == str(sh.ls('-l tmp')), ls)

    def test_stdin(self):
        content = open(__file__).read().strip()
        if not isinstance(content, six.binary_type):
            bcontent = content.encode('utf-8')
        else:
            bcontent = content
        self.assertEqual(content,
                         str(sh.stdin(bcontent) | sh.cat('-')))
        self.assertEqual(content,
                         str(sh.stdin(open(__file__, 'rb')) | sh.cat('-')))

    def test_redirect_stdin(self):
        sh.stdin(b'blah') > 'tmp'
        self.assertEqual(str(sh.cat('tmp')), 'blah')

        sh.stdin(b'blah') >> 'tmp'
        self.assertEqual(str(sh.cat('tmp')), 'blahblah')

    def test_stdin2(self):
        head = str(sh.stdin(open(__file__, 'rb'))
                   | sh.cat('-')
                   | sh.head('-n1'))
        self.assertTrue(len(head) > 1, head)

    def test_raise(self):
        self.assertRaises(OSError, str, sh.zero_command())

    def test_sudo(self):
        sh.aliases['sudo'] = sh.path.join(sh.pwd(), 'sudo')
        old_path = sh.env.path
        sh.env.path = []
        self.assertRaises(OSError, sh.check_sudo)
        sh.env.path = old_path

        sh.stdin(six.b('#!/bin/bash\necho root')) > 'sudo'
        self.assertEqual(sh.chmod('+x sudo').succeeded, True)
        self.assertEqual(sh.check_sudo(), None)

    def test_cd(self):
        pwd = sh.pwd()
        sh.cd('..')
        self.assertNotEqual(pwd, sh.env.pwd)
        self.assertEqual(sh.pwd(), sh.env.pwd)
        sh.cd(pwd)

    def test_console_script(self):
        def f(args):
            return 1
        f = sh.console_script(f)
        self.assertRaises(SystemExit, f)
        self.assertEqual(f([]), 1)

    def test_map(self):
        self.assertRaises(OSError, list,
                          sh.rm.map(['/chut'], stop_on_failure=True))

    def tearDown(self):
        sh.rm('-f tmp')
        sh.rm('-f sudo')
