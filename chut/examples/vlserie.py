# -*- coding: utf-8 -*-
from chut import *  # noqa
import shutil
import sys
import re

__version__ = "0.17"

_episode = re.compile(
    r'[^0-9]+(?P<s>[0-9]+)\s*(x|e|episode)\s*(?P<e>[0-9]+)[^0-9]+')


def extract_numbers(f):
    m = _episode.search(f.lower())
    if m:
        m = m.groupdict()
        return int(m['s']), int(m['e'])


@console_script(fmt='brief')
def vlserie(args):
    """
    Usage: %prog [options] [<season> <episode>]

    Play the serie contained in the current folder. File names should be
    formated like SXXEXX. Also load subtitles if any.

    Store the latest play in ~/.vlserie. So you dont have to remember it
    yourself.

    Require vlc or mplayer.

    Options:

    -s TIME, --start=TIME   Start at (float)
    -l, --latest            Play latest instead of next
    -f, --freeplayer        Play in freeplayer
    --loop                  Loop over episodes
    %options
    """

    config = ini('~/.vlserie')
    config.write()

    player = config.player.binary or 'vlc'
    player_opts = config[player]
    if env.display:
        options = player_opts.xoptions
    else:
        options = player_opts.fboptions
    if args['--start']:
        options += ' --start-time ' + args['--start']
    debug('Using %s player', player)

    pwd = path.abspath('.')

    def play(filename, episode):
        filename = path.abspath(filename)
        dirname, filename = path.split(filename)
        cd(dirname)
        if args['--freeplayer']:
            cmdline = (
                "%s %r --play-and-exit --sout "
                "'#transcode{vcodec=mp2v,vb=4096,scale=1,audio-sync,soverlay}:"
                "duplicate{dst=std{access=udp,mux=ts,dst=212.27.38.253:1234}}'"
            ) % (options, filename)
        elif player in ('vlc', 'cvlc'):
            cmdline = (
                '%s -f --play-and-exit --qt-minimal-view %r'
            ) % (options, filename)
        elif player == 'mplayer':
            cmdline = '%s -fs %r' % (options, filename)
        else:
            error('Unknown player %r', player)
            sys.exit(1)
        srts = find(pwd, '-iregex ".*%s\(x\|E\)%02i.*srt"' % episode,
                    shell=True)
        for srt in sorted(srts):
            if '  ' in srt:
                new = srt.replace('  ', ' ')
                shutil.move(srt, new)
                srt = new
            if player in ('vlc', 'cvlc'):
                cmdline += ' --sub-file %r' % srt
            elif player == 'mplayer':
                cmdline += ' -sub %r' % srt
        subs = find(pwd, '-iregex ".*%s\(x\|E\)%02i.*sub"' % episode,
                    shell=True)
        for sub in sorted(subs):
            if player == 'mplayer':
                sub = sub.lstrip('./')
                cmdline += ' -vobsub %r' % sub[:-4]
        cmd = sh[player](cmdline, combine_stderr=True, shell=True)
        info(repr(cmd))
        serie = config[pwd]
        serie.latest = filename
        config.write()
        try:
            cmd > 1
        except OSError:
            pass
        if not args['--loop']:
            sys.exit(0)

    serie = config[pwd]

    filenames = find(
        ('. -iregex '
         '".*[0-9]+\s*\(e\|x\|episode\)\s*[0-9]+.*'
         '\(avi\|wmv\|mkv\|mp4\)"'),
        shell=True)
    filenames = [path.abspath(f) for f in filenames]
    filenames = sorted([(extract_numbers(f), f) for f in filenames])
    filenames = [(e, f) for e, f in filenames if f is not None]

    if args['<season>']:
        episode = int(args['<season>']), int(args['<episode>'])
        filenames = [(x, f) for x, f in filenames if x >= episode]
    elif serie.latest:
        episode = extract_numbers(serie.latest.lower())
        if args['--latest']:
            filenames = [(x, f) for x, f in filenames if x >= episode]
        else:
            filenames = [(x, f) for x, f in filenames if x > episode]

    for episode, filename in filenames:
        play(filename, episode)


@console_script(fmt='brief')
def freeplayer(args):
    """Usage: %prog [options] [<stream>]

    -s      Serve freeplayer page
    """
    if args["-s"]:
        with open('/tmp/settings.html', 'w') as fd:
            fd.write(settings)
        nc('-l -p 8080 -q 1 < /tmp/settings.html', shell=True) > 0
        info('freeplayer initialized')
        return
    stream = args['<stream>']
    if stream.startswith('https://'):
        stream.replace('https://', 'http://')
    cmdline = (
        "%r --play-and-exit --sout "
        "'#transcode{vcodec=mp2v,vb=4096,scale=1,audio-sync,soverlay}:"
        "duplicate{dst=std{access=udp,mux=ts,dst=212.27.38.253:1234}}'"
    ) % stream
    cmd = sh['vlc'](cmdline, combine_stderr=True, shell=True)
    info(repr(cmd))
    cmd > 1

settings = '''HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n
<html><body background="ts://127.0.0.1"></body></html>'''
