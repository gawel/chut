# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals
from chut.recipe import Recipe
from chut.scripts import chutify
from io import StringIO
import chut as sh
import unittest
import os


os.environ['TESTING'] = '1'


class Chut(unittest.TestCase):

    __file__ = __file__.replace('.pyc', '.py')

    def test_output(self):
        self.assertEqual(sh.rm('/chut').succeeded, False)
        self.assertEqual(sh.rm('/chut').failed, True)
        self.assertTrue(len(sh.rm('/chut').stderr) >= 0)

    def test_repr(self):
        self.assertEqual(repr(sh.stdin(b'') | sh.cat('-')),
                         repr(str('stdin | cat -')))

        @sh.wraps
        def w():
            pass

        self.assertEqual(repr(sh.cat('-') | w),
                         repr(str('cat - | w()')))

        self.assertEqual(str('<sh>'), repr(sh.sh))

    def test_environ(self):
        env = sh.env.copy(tmp='tmp')
        print(env.tmp)
        self.assertEqual(env.tmp, 'tmp')
        self.assertEqual(sh.env.tmp, None)
        del env.tmp
        self.assertEqual(env.tmp, None)
        with sh.env(tmp="tmp"):
            self.assertEqual(sh.env.tmp, 'tmp')
            with sh.env(tmp=None):
                self.assertEqual(sh.env.tmp, None)
            self.assertEqual(sh.env.tmp, 'tmp')
        self.assertEqual(sh.env.tmp, None)

    def test_debug(self):
        sh.set_debug(False)
        level = sh.log.level
        sh.set_debug(True)
        self.assertNotEqual(level, sh.log.level)
        sh.set_debug(False)
        self.assertEqual(level, sh.log.level)

    def test_stdout(self):
        s = sh.Stdout('lkl')
        self.assertEqual(s.stdout, s)

    def test_iter_stdin(self):
        self.assertTrue(isinstance(sh.stdin(b'blah').iter_stdout, int))
        self.assertTrue(isinstance(sh.stdin('blah').iter_stdout, int))
        self.assertTrue(isinstance(sh.stdin(StringIO('')).iter_stdout,
                        StringIO))
        with open(__file__, 'rb') as fd:
            self.assertEqual(sh.stdin(fd).iter_stdout, fd)

    def test_slices(self):
        pipe = sh.cat('tmp') | sh.grep('tmp') | sh.wc('-l')
        self.assertEqual(pipe[0:1]._binary, 'cat')
        self.assertEqual(pipe.__getitem__(slice(0, 1))._binary, 'cat')
        self.assertEqual(pipe.__getslice__(0, 1)._binary, 'cat')
        self.assertEqual(pipe[1:]._binary, 'wc')
        self.assertEqual(pipe.__getitem__(slice(1, 3))._binary, 'wc')
        self.assertEqual(pipe.__getslice__(1, 3)._binary, 'wc')

        self.assertRaises(KeyError, pipe.__getitem__, 1)

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
        if not isinstance(content, bytes):
            bcontent = content.encode('utf-8')
        else:
            bcontent = content
        self.assertEqual(content,
                         str(sh.stdin(bcontent) | sh.cat('-')))
        self.assertEqual(content,
                         str(sh.stdin(open(__file__, 'rb')) | sh.cat('-')))

    def test_redirect_to_std(self):
        ls = sh.ls()
        with open('/tmp/stdout', 'wb+') as fd:
            ls._sys_stdout = fd
            ls._sys_stderr = fd
            ls._write(1, 'x')
            ls._write(2, 'x')
            ls.args = ['/none']
            sh.log.handlers = []
            self.assertRaises(OSError, ls._write, 1, 'x')

    def test_stdin_to_std(self):
        with open(__file__, 'rb') as stdin:
            sh.stdin(stdin) > '/tmp/stdout'

    def test_redirect_stdin(self):
        sh.stdin(b'blah') > 'tmp'
        self.assertEqual(str(sh.cat('tmp')), 'blah')

        sh.stdin(b'blah') >> 'tmp'
        self.assertEqual(str(sh.cat('tmp')), 'blahblah')

    def test_stdin2(self):
        head = str(
            sh.stdin(open(self.__file__, 'rb')
                     ) | sh.cat('-') | sh.head('-n1'))
        self.assertTrue(len(head) > 1, head)
        self.assertTrue(len(head) > 2, head)

    def test_raise(self):
        self.assertRaises(OSError, str, sh.zero_command())

    def test_sudo(self):
        sh.aliases['sudo'] = sh.path.join(sh.pwd(), 'sudo')
        old_path = sh.env.path
        sh.env.path = []
        self.assertRaises(OSError, sh.check_sudo)
        sh.env.path = old_path

        sh.stdin(b'#!/bin/bash\necho root') > 'sudo'
        self.assertEqual(sh.chmod('+x sudo').succeeded, True)
        self.assertEqual(sh.check_sudo(), None)

        self.assertTrue(len(list(sh.sudo.ls('.'))) > 0)

        sh.stdin(b'#!/bin/bash\necho gawel') > 'sudo'
        self.assertRaises(OSError, sh.check_sudo)

    def test_ssh(self):
        self.assertRaises(NotImplementedError, sh.ssh('x').cd, '/tmp')
        self.assertRaises(NotImplementedError, sh.ssh('x').pwd)

    def test_version(self):
        @sh.console_script
        def w(args):
            """Usage: %prog [--version]"""
            pass
        self.assertRaises(SystemExit, w.main, {'--version': True})

    def test_cd(self):
        pwd = sh.pwd()
        sh.cd('..')
        self.assertNotEqual(pwd, sh.env.pwd)
        self.assertEqual(sh.pwd(), sh.env.pwd)
        sh.cd(pwd)
        # test with with
        with sh.cd('..') as newd:
            self.assertNotEqual(pwd, sh.env.pwd)
            self.assertEqual(sh.pwd(), sh.env.pwd)
            self.assertEqual(newd, sh.env.pwd)
        self.assertEqual(sh.pwd(), pwd)

    def test_console_script(self):
        def f(args):
            return 1
        f = sh.console_script(f)
        self.assertRaises(SystemExit, f)
        self.assertEqual(f([]), 1)

    def test_generate(self):
        os.environ['CHUTIFIED_FILES'] = ''
        generator = sh.Generator()
        self.assertEqual(generator('chut/scripts.py'),
                         ['dist/scripts/chutify'])

    def test_chutify(self):
        self.assertEqual(chutify(['chut/scripts.py']), 0)
        self.assertEqual(chutify(['.']), 0)
        self.assertEqual(chutify(['-s', 'tests']), 0)
        self.assertEqual(chutify(['.git']), 0)

    def test_recipe(self):
        r = Recipe({'buildout': {'directory': os.getcwd()}},
                   'chut', {'destination': 'dist/scripts',
                            'run': 'ls\nls .\n '})
        self.assertEqual(r.install(), ())
        r = Recipe({'buildout': {'directory': os.getcwd()}},
                   'chut', {'destination': 'dist/scripts'})
        self.assertEqual(r.update(), ())
        r = Recipe({'buildout': {'directory': os.getcwd()}},
                   'chut', {'devel': 'true', 'run': 'ls'})
        self.assertEqual(r.update(), ())

    def test_map(self):
        self.assertRaises(OSError, list,
                          sh.rm.map(['/chut'], stop_on_failure=True))

    def test_call_opts(self):
        self.assertEqual(str(sh.ls('.')), str(sh.ls('.', shell=True)))
        self.assertEqual(str(sh.ls('.')), str(sh.ls('.')(shell=True)))
        self.assertEqual(str(sh.ls('.')), str(sh.ls('.', stderr=1)))
        self.assertEqual(str(sh.ls('.')), str(sh.ls('.')(stderr=1)))
        self.assertEqual(str(sh.ls('.')), str(sh.ls('.', combine_stderr=True)))
        self.assertEqual(str(sh.ls('.')), str(sh.ls('.')(combine_stderr=True)))

    def test_fab(self):
        fab = sh.fab
        fab.chutifab()
        fab.chutifab('.')
        fab.run('safe-upgrade', '-h')
        fab.sudo('safe-upgrade', '-h')

    def tearDown(self):
        sh.rm('-f tmp')
        sh.rm('-f sudo')
