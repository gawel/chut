# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import six
import unittest
from chut import sh


class Chut(unittest.TestCase):

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

    def tearDown(self):
        sh.rm('-f tmp')
