# -*- coding: utf-8 -*-
import chut as sh
import os


@sh.console_script(fmt='msg')
def chutify(args):
    """
    Usage: %prog [options] [<location>]

    Generate binary scripts from all @console_script contained in <location>
    <location> can be a directory, a python file or a dotted name.

    If <location> is .git then generate a pre-commit hook which generate script
    from the current directory.

    <location> and --destination can be set in a .chut file:

        [chut]
        destination = bin/
        location = scripts

    Options:

    -l, --loop                    Generate scripts when the source change
    -s NAME, --section NAME       Use NAME section in .chut [default: chut]
    --devel                       Install develop scripts in bin/
    --upgrade                     Upgrade virtualenv dependencies
    -d DIR, --destination=DIR     Destination [default: dist/scripts]
    -i X, --interpreter=X         Python interpreter to use
    -n X, --new-version=X         Set new scripts version
    %options-30s
    """
    config = sh.ini('.chut')
    if sh.env.git_dir:  # pragma: no cover
        cfg = config['githook'] or config[args['--section']]
    else:
        cfg = config[args['--section']]

    interpreter = args['--interpreter'] or cfg.interpreter or 'python'
    if interpreter in ('2', '3'):  # pragma: no cover
        interpreter = 'python' + interpreter
    args['--interpreter'] = interpreter

    location = args.get('<location>') or cfg.location or os.getcwd()
    location = os.path.expanduser(location)

    if location.endswith('.git'):
        hooks = sh.path.join(location, 'hooks')
        hook = sh.path.join(hooks, 'pre-commit')
        args['destination'] = hooks
        generator = sh.Generator(**args)
        if not __file__.endswith('chutify'):
            filename = __file__.replace('.pyc', '.py')
            script = generator(filename)[0]
            sh.mv(script, hook)
        else:  # pragma: no cover
            # install git hook
            sh.cp(__file__, hook)
        executable = sh.chmod('+x', hook)
        if executable:
            print(executable.commands_line)
        return 0

    if cfg.destination and args['--destination'] == 'dist/scripts':
        args['--destination'] = cfg.destination

    if os.path.isfile('setup.py'):
        version = sh.grep('-E ^version setup.py')
        if version:
            version = str(version).split('=')[1].strip('\'" ')
            if 'dev' in version:
                version = version.split('dev')[0].strip('.')
            args['version'] = version

    generator = sh.Generator(**args)

    commands = cfg.run.as_list('\n')
    commands = [c.strip() for c in commands if c.strip()]

    def gen():
        scripts = generator(location)
        for cmd in commands:
            print('$ %s' % cmd)
            if ' ' in cmd:
                binary, args = cmd.split(' ', 1)
                sh[binary](args) > 2
            else:
                sh[cmd]() > 2
        return scripts

    if args['--loop']:  # pragma: no cover
        import time
        while True:
            try:
                gen()
                time.sleep(.1)
            except KeyboardInterrupt:
                return 0
    else:
        scripts = gen()
        if sh.env.git_dir:  # pragma: no cover
            sh.git('add -f', *scripts) > 1
    return 0
