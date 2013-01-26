# -*- coding: utf-8 -*-
from chut import *  # noqa
import sys
import re

_episode = re.compile(r'S([0-9]+)E([0-9]+)')


def extract_numbers(f):
    season, episode = _episode.findall(f)[0]
    episode = int(season), int(episode)
    return episode


@console_script
def vlserie(args):
    """
    Usage: %prog [options] [<season> <episode>]

    Play the serie contained in the current folder. File names should be
    formated like SXXEXX. Also load subtitles if any.

    Store the latest play in ~/.vlserie. So you dont have to remember it
    yourself.

    Require vlc.

    Options:
    -h              Show this help
    --l,--latest    Play latest instead of next
    --loop          Loop over episodes
    """

    def play(filename, episode):
        cmdline = '-f %s' % e(filename)
        srts = find('-regex ".*%s\(x\|E\)%02i.*srt"' % episode, shell=True)
        for srt in sorted(srts):
            cmdline += ' --sub-file %s' % e(srt)
        cmd = vlc(cmdline, combine_stderr=True, shell=True)
        print(repr(cmd))
        serie.latest = filename
        config.write()
        try:
            cmd > 1
        except OSError:
            pass
        if not args['--loop']:
            sys.exit(0)

    config = ini('~/.vlserie')
    config.write()
    serie = config[path.abspath('.')]

    filenames = find('. -regex ".*S[0-9]+E[0-9]+.*\(avi\|wmv\)"', shell=True)
    filenames = [path.basename(f) for f in filenames]
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
