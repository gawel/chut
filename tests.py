# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import unittest
from chut import ch


class Chut(unittest.TestCase):

    def test_redirect_binary(self):
        with ch.pipe(ch.cat(__file__)) as cmd:
            cmd > 'tmp'
        ls = str(ch.ls('-l tmp'))

        with ch.pipe(ch.cat(__file__)) as cmd:
            cmd >> 'tmp'
        self.assertFalse(ls == str(ch.ls('-l tmp')))
        ch.rm('tmp')

    def test_redirect_python(self):

        @ch.wraps
        def grep(stdin):
            for line in stdin:
                if b'__' in line:
                    yield line

        pipe = ch.cat(__file__) | grep
        with ch.pipe(pipe) as cmd:
            cmd > 'tmp'
        ls = str(ch.ls('-l tmp'))
        with ch.pipe(pipe) as cmd:
            cmd >> 'tmp'
        self.assertFalse(ls == str(ch.ls('-l tmp')), ls)
        ch.rm('tmp')

    def test_stdin(self):
        content = open(__file__).read().strip()
        try:
            bcontent = content.encode('utf-8')
        except:
            bcontent = content
        self.assertEqual(content,
                         str(ch.stdin(bcontent) | ch.cat('-')))
        self.assertEqual(content,
                         str(ch.stdin(open(__file__, 'rb')) | ch.cat('-')))

    def test_stdin2(self):
        head = str(ch.stdin(open(__file__, 'rb'))
                   | ch.cat('-')
                   | ch.head('-n1'))
        self.assertTrue(len(head) > 1, head)

    def test_raise(self):
        self.assertRaises(OSError, str, ch.zero_command())
