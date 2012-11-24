# -*- coding: utf-8 -*-
from chut import console_script, stdin, env, test, casperjs, which, mktemp, rm
import atexit
import six
import sys
import os

__doc__ = """
This script use chut and casperjs to build an interactive translator

Example usage::

    $ echo "hello" | translate -
    $ translate -l fr:en bonjour
    $ translate -i
"""

SCRIPT = six.b("""
system = require('system')
require('casper').create()
  .start('http://translate.google.com/#' + system.env['TR_PAIR'], function(){
      this.fill('form#gt-form', {text: system.env['TR_TEXT']}, false)})
  .waitForSelector('span.hps', function() {
      this.echo(this.fetchText('#result_box'))
      results = this.evaluate(function() {
          results = document.querySelectorAll('table.gt-baf-table tr')
          return Array.prototype.map.call(results, function(e) {
              if (!/colspan/.exec(e.innerHTML))
                  return e.innerText.replace(/\\n/,': ')
              else
                  return ''
          })
      })
      this.echo(results.join(''))
}).run()
""")


@console_script
def translate(args):
    """Usage: %prog [options] [-] [<text>...]

    -l LANGS, --langs=LANGS     Langs [default: en:fr]
    -i, --interactive           Translate line by line in interactive mode
    -h, --help                  Show this help
    """
    if not which('casperjs'):
        print('You must install casperjs first')
        return 1
    env.tr_pair = args['--langs'].replace(':', '|')
    script = str(mktemp('translate-XXXX.js'))
    atexit.register(rm(script))
    stdin(SCRIPT) > script

    def show_result():
        for line in [l.strip() for l in casperjs(script) if l.strip()]:
            if ':' in line:
                line = '- ' + line
            print(line)

    if args['--interactive'] or not (args['-'] or args['<text>']):
        import readline
        hist = os.path.join(os.path.expanduser('~'), '.translate_history')
        if test.f(hist):
            readline.read_history_file(hist)
        atexit.register(readline.write_history_file, hist)
        from six.moves import input
        while True:
            try:
                env.tr_text = input('Text: ')
            except KeyboardInterrupt:
                return
            else:
                show_result()
    elif args['-']:
        env.tr_text = sys.stdin.read()
    elif args['<text>']:
        env.tr_text = ' '.join(args['<text>'])
    show_result()

if __name__ == '__main__':
    translate()
