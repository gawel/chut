# -*- coding: utf-8 -*-
from chut import *  # noqa
import shutil
import sys
import re

__version__ = "0.9"

_episode = re.compile(r's([0-9]+)\s*e\s*([0-9]+)')


def extract_numbers(f):
    season, episode = _episode.findall(f.lower())[0]
    episode = int(season), int(episode)
    return episode


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

    -l, --latest            Play latest instead of next
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
    debug('Using %s player', player)

    def play(filename, episode):
        filename = path.abspath(filename)
        dirname, filename = path.split(filename)
        cd(dirname)
        if player == 'vlc':
            cmdline = '%s -f --qt-minimal-view %r' % (options, filename)
        elif player == 'mplayer':
            cmdline = '%s -fs %r' % (options, filename)
        else:
            error('Unknown player %r', player)
            sys.exit(1)
        srts = find('-iregex ".*%s\(x\|E\)%02i.*srt"' % episode, shell=True)
        for srt in sorted(srts):
            srt = srt.lstrip('./')
            if '  ' in srt:
                new = srt.replace('  ', ' ')
                shutil.move(srt, new)
                srt = new
            if player == 'vlc':
                cmdline += ' --sub-file %r' % srt
            elif player == 'mplayer':
                cmdline += ' -sub %r' % srt
        subs = find('-iregex ".*%s\(x\|E\)%02i.*sub"' % episode, shell=True)
        for sub in sorted(subs):
            if player == 'mplayer':
                sub = sub.lstrip('./')
                cmdline += ' -vobsub %r' % sub[:-4]
        cmd = sh[player](cmdline, combine_stderr=True, shell=True)
        info(repr(cmd))
        serie = config[dirname]
        serie.latest = filename
        config.write()
        try:
            cmd > 1
        except OSError:
            pass
        if not args['--loop']:
            sys.exit(0)

    serie = config[path.abspath('.')]

    filenames = find(
        '. -iregex ".*s[0-9]+\s*e\s*[0-9]+.*\(avi\|wmv\|mkv\|mp4\)"',
        shell=True)
    filenames = [path.abspath(f) for f in filenames]
    filenames = sorted([(extract_numbers(f), f) for f in filenames])

    if args['<season>']:
        episode = int(args['<season>']), int(args['<episode>'])
        filenames = [(x, f) for x, f in filenames if x >= episode]
    elif serie.latest:
        episode = extract_numbers(serie.latest)
        if args['--latest']:
            filenames = [(x, f) for x, f in filenames if x >= episode]
        else:
            filenames = [(x, f) for x, f in filenames if x > episode]

    for episode, filename in filenames:
        play(filename, episode)
