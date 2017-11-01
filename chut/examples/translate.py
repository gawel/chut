# -*- coding: utf-8 -*-
from chut import *  # NOQA
import atexit
import six
import sys
import os

__version__ = "0.17"

__doc__ = """
Usage: %prog [options] [-] [<text>...]

This script use chut and casperjs to build an interactive translator

Examples:

    $ echo "hello" | translate -
    $ translate -l fr:en bonjour
    $ translate -i

Options:

    -l LANGS, --langs=LANGS     Langs [default: en:fr]
    -i, --interactive           Translate line by line in interactive mode
    -h, --help                  Show this help
    %options
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


@console_script(doc=__doc__)
def translate(args):
    if not which('casperjs'):
        print('You must install casperjs first')
        return 1
    env.tr_pair = args['--langs'].replace(':', '|')
    script = str(mktemp('--tmpdir translate-XXXX.js'))
    atexit.register(rm(script))
    stdin(SCRIPT) > script

    def show_result():
        try:
            for line in sh.casperjs(script):
                if line:
                    if ':' in line:
                        line = '- ' + line
                    print(line)
        except:
            pass

    if args['--interactive'] or not (args['-'] or args['<text>']):
        import readline
        hist = os.path.join(os.path.expanduser('~'), '.translate_history')
        if test.f(hist):
            readline.read_history_file(hist)
        atexit.register(readline.write_history_file, hist)
        while True:
            try:
                tr_text = six.moves.input('%s: ' % env.tr_pair)
                tr_text = tr_text.strip()
            except KeyboardInterrupt:
                return
            else:
                if tr_text == 'q':
                    return
                elif tr_text == 's':
                    env.tr_pair = '|'.join(reversed(env.tr_pair.split('|')))
                elif tr_text.startswith(('lang ', 'l ')):
                    tr_pair = tr_text.split(' ', 1)[1]
                    env.tr_pair = tr_pair.replace(':', '|').strip()
                elif tr_text:
                    env.tr_text = tr_text
                    show_result()
    elif args['-']:
        env.tr_text = sys.stdin.read()
    elif args['<text>']:
        env.tr_text = ' '.join(args['<text>'])
    show_result()

if __name__ == '__main__':
    translate()
