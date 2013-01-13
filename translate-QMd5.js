
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
                  return e.innerText.replace(/\n/,': ')
              else
                  return ''
          })
      })
      this.echo(results.join(''))
}).run()
