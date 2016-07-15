#!/usr/bin/env python
# encoding: utf-8

"""
ti is a simple and extensible time tracker for the command line. Visit the
project page (http://ti.sharats.me) for more details.

Usage:
  ti (o|on) <name> [<time>...]
  ti (f|fin) [<time>...]
  ti (s|status)
  ti (t|tag) <tag>...
  ti (n|note) <note-text>...
  ti (l|log) [today]
  ti (e|edit)
  ti (i|interrupt)
  ti --no-color
  ti -h | --help

Options:
  -h --help         Show this help.
  <start-time>...   A time specification (Go to http://ti.sharats.me for more on
                    this).
  <tag>...          Tags can be made of any characters, but its probably a good
                    idea to avoid whitespace.
  <note-text>...    Some arbitrary text to be added as `notes` to the currently
                    working project.
"""

from __future__ import print_function
from __future__ import unicode_literals

import json, yaml
from datetime import datetime, timedelta, date
from collections import defaultdict
from collections import OrderedDict as OD
import re
import os, subprocess, tempfile
from os import path
import sys
import math

from colorama import *

use_color = True
use_gui_notification = False
hour_space = 5
minute_space = 2
second_space = 2

class JsonStore(object):

    def __init__(self, filename):
        self.filename = filename

    def load(self):

        if path.exists(self.filename):
            with open(self.filename) as f:
                data = json.load(f, object_pairs_hook=OD)

        else:
            data = OD([('work', list()), ('interrupt_stack', list())])

        return data

    def dump(self, data):
        with open(self.filename, 'w') as f:
            json.dump(data, f, separators=(',', ': '), indent=2)

store = JsonStore(os.getenv('SHEET_FILE', None) or
                    os.path.expanduser('~/.ti-sheet'))
_now_local = datetime.now()
_now_utc = datetime.utcnow()
_delta = _now_local - _now_utc
_delta_hours = math.ceil(_delta.seconds/100)*100//3600
_delta_hours += _delta.days*24
LOCAL_UTC_HOURS_DIFF = _delta_hours
LOCAL_UTC_DELTA = timedelta(hours=LOCAL_UTC_HOURS_DIFF)

def clean_text(text):
    text_clean = text
    replacement_text = {
        Fore.RED: "\n",
        Fore.YELLOW: "\n",
        Fore.GREEN: "\n",
        Fore.BLUE: "\n",
        Fore.RESET: "\n",
    }
    for key, value in replacement_text.items():
        text_clean = text_clean.replace(key, value)
    text_clean = text_clean.replace("\n.", "\n")
    return text_clean

def gui_notification(title, text):
    text_clean = clean_text(text)
    if Fore.RED in text:
        icon = 'stop.svg'
    elif Fore.GREEN in text:
        icon = 'start.svg'
    elif Fore.YELLOW in text:
        icon = 'warning.svg'
    elif "cannot stop a task" in text:
        icon = 'warning.svg'
    else:
        icon = 'information.svg'

    dirname = os.path.dirname(os.path.realpath(__file__))
    icon = os.path.join(dirname, icon)
    if sys.platform in ("linux", "linux2"):
        try:
            subprocess.check_call(["notify-send", title, "%s"%text_clean.strip(), "-t", "3000", '-i', icon])
        except FileNotFoundError:
            pass

def print_ti(*args, **kwargs):
    text = " ".join(args)
    # Action status can be used by external programs as
    # it doesn't print anything on the GUI. We check for
    # it's two possible outputs
    if use_gui_notification:
        gui_notification("ti project manager", text)
    else:
        pass
    print(*args, **kwargs)

def red(str):
    if use_color:
        return Fore.RED + str + Fore.RESET
    else:
        return str

def green(str):
    if use_color:
        return Fore.GREEN + str + Fore.RESET
    else: 
        return str

def yellow(str):
    if use_color: 
        return Fore.YELLOW + str + Fore.RESET
    else:
        return str

def blue(str):
    if use_color: 
        return Fore.BLUE + str + Fore.RESET
    else:
        return str


def action_on(name, time):
    data = store.load()
    work = data['work']

    if work and 'end' not in work[-1]:
        print_ti('Already working on ' + yellow(work[-1]['name']) +
                '. Stop it or use a different sheet.', file=sys.stderr)
        raise SystemExit(1)

    if name == "":
        # empty task name, use previous task name
        name = work[-1]['name']
        message = "No task name specified, so using name of the previous task. "
    else:
        message = ""
    entry = OD([('name', name), ('start', time)])

    work.append(entry)
    store.dump(data)

    print_ti(message + 'Started working on ' + green(name) + '.')


def action_fin(time, back_from_interrupt=True):
    ensure_working()

    data = store.load()

    current = data['work'][-1]
    current['end'] = time
    store.dump(data)
    print_ti('Stopped working on ' + red(current['name']) + '.')

    if back_from_interrupt and len(data['interrupt_stack']) > 0:
        name = data['interrupt_stack'].pop()['name']
        store.dump(data)
        action_on(name, time)
        if len(data['interrupt_stack']) > 0:
            print_ti('You are now %d deep in interrupts.' % len(data['interrupt_stack']))
        else:
            print_ti('Congrats, you\'re out of interrupts!')


def action_interrupt(name, time):
    ensure_working()

    action_fin(time, back_from_interrupt=False)

    data = store.load()
    if 'interrupt_stack' not in data:
        data['interrupt_stack'] = []
    interrupt_stack = data['interrupt_stack']
    work = data['work']

    interrupted = data['work'][-1]
    interrupt_stack.append(interrupted)
    store.dump(data)

    action_on(name + '<i>', time)
    print_ti('You are now %d deep in interrupts.' % len(interrupt_stack))


def action_note(content):
    ensure_working()

    data = store.load()
    current = data['work'][-1]

    if 'notes' not in current:
        current['notes'] = [content]
    else:
        current['notes'].append(content)

    store.dump(data)

    print_ti('Yep, noted to ' + yellow(current['name']) + '.')


def action_tag(tags):
    ensure_working()

    data = store.load()
    current = data['work'][-1]

    current['tags'] = set(current.get('tags') or [])
    current['tags'].update(tags)
    current['tags'] = list(current['tags'])

    store.dump(data)

    tag_count = str(len(tags))
    print_ti('Okay, tagged current work with ' + tag_count + ' tag' +
            ('s' if tag_count > 1 else '') + '.')


def action_status():
    if not is_working():
        print_ti(red("Not working on any task."))
        return

    data = store.load()
    current = data['work'][-1]

    start_time = parse_isotime(current['start'])
    diff = timegap(start_time, datetime.utcnow())

    print_ti('Working on {0} for {1}.'
            .format(green(current['name']), diff))

def action_log(period):
    data = store.load()
    work = data['work'] + data['interrupt_stack']
    log = defaultdict(lambda: {'delta': timedelta()})
    current = None

    if period in ['t', 'today']:
        # print_ti("Today's log")
        today = date.today()
        start_cutoff = datetime(today.year, today.month, today.day) - LOCAL_UTC_DELTA
        end_cutoff = datetime(today.year, today.month, today.day) + timedelta(days=1) - LOCAL_UTC_DELTA
    elif period in ['y', 'yesterday']:
        # print_ti("Yesterday's log")
        today = date.today()
        start_cutoff = datetime(today.year, today.month, today.day) - timedelta(days=1) - LOCAL_UTC_DELTA
        end_cutoff = datetime(today.year, today.month, today.day) - LOCAL_UTC_DELTA
    else:
        start_cutoff = None
        end_cutoff = None
    for item in work:
        start_time = parse_isotime(item['start'])
        if 'end' in item:
            end_time = parse_isotime(item['end'])
        else: # The item currently being worked on
            end_time = datetime.utcnow()
            current = item['name']

        if start_cutoff is not None and end_time < start_cutoff:
            continue
        if end_cutoff is not None and start_time > end_cutoff:
            continue

        if start_cutoff is not None:
            start_time = max(start_cutoff, start_time)

        if end_cutoff is not None:
            end_time = min(end_cutoff, end_time)

        log[item['name']]['delta'] += end_time - start_time

    name_col_len = 0

    for name, item in log.items():
        name_col_len = max(name_col_len, len(name))

        hours = item['delta'].days * 24
        secs = item['delta'].seconds
        tmsg = []

        if secs > 3600:
            hours_from_secs = int(secs / 3600)
            hours += hours_from_secs
            secs -= hours_from_secs * 3600

        if hours != 0:
            tmsg.append(blue(str(hours).rjust(hour_space)) + ' hour' + ('s  ' if hours > 1 else '   '))

        if secs > 60:
            mins = int(secs / 60)
            secs -= mins * 60
            tmsg.append(blue(str(mins).rjust(minute_space)) + ' minute' + ('s' if mins > 1 else ' '))

        if secs:
            tmsg.append(blue(str(secs).rjust(second_space)) + ' second' + ('s' if secs > 1 else ' '))

        log[name]['tmsg'] = ', '.join(tmsg)[::-1].replace(', ', ' &'[::-1], 1)[::-1]

    for name, item in sorted(list(log.items()), key=(lambda x: x[1]['delta']), reverse=True):
	colored_name = name.replace('<i>',green('<i>'),1)
        print_ti(colored_name.ljust(name_col_len), ' ∙∙ ', item['tmsg'],
                end=' ← working\n' if current == name else '\n')


def action_edit():
    if 'EDITOR' not in os.environ:
        print_ti("Please set the 'EDITOR' environment variable", file=sys.stderr)
        raise SystemExit(1)

    data = store.load()
    try:
        yml = yaml.safe_dump(data, default_flow_style=False, allow_unicode=True)
	yml = yml.decode('utf-8')
    except:
        print_ti("Oops, that Decoding got an error!", file=sys.stderr)
        raise SystemExit(1)

    cmd = os.getenv('EDITOR')
    fd, temp_path = tempfile.mkstemp(prefix='ti.')
    with open(temp_path, "r+") as f:
        f.write(yml.replace('\n- ', '\n\n- '))
        f.seek(0)
        subprocess.check_call(cmd + ' ' + temp_path, shell=True)
        yml = f.read()
        f.truncate()
        f.close

    os.close(fd)
    os.remove(temp_path)

    try:
        data = yaml.load(yml)
    except:
        print_ti("Oops, that YAML didn't appear to be valid!", file=sys.stderr)
        raise SystemExit(1)

    store.dump(data)


def is_working():
    data = store.load()
    return data.get('work') and 'end' not in data['work'][-1]


def ensure_working():
    if is_working(): return
    print_ti("You aren't working on any task. See `ti -h` for help.")
    raise SystemExit(1)


def to_datetime(timestr):
    return parse_engtime(timestr).isoformat() + 'Z'


def parse_engtime(timestr):

    now = datetime.utcnow()
    if not timestr or timestr.strip() == 'now':
        return now

    match = re.match(r'(\d+|a) \s* (s|secs?|seconds?) \s+ ago $', timestr, re.X)
    if match is not None:
        n = match.group(1)
        seconds = 1 if n == 'a' else int(n)
        return now - timedelta(seconds=seconds)

    match = re.match(r'(\d+|a) \s* (mins?|minutes?) \s+ ago $', timestr, re.X)
    if match is not None:
        n = match.group(1)
        minutes = 1 if n == 'a' else int(n)
        return now - timedelta(minutes=minutes)

    match = re.match(r'(\d+|a|an) \s* (hrs?|hours?) \s+ ago $', timestr, re.X)
    if match is not None:
        n = match.group(1)
        hours = 1 if n in ['a', 'an'] else int(n)
        return now - timedelta(hours=hours)

    raise ValueError("Don't understand the time '" + timestr + "'")


def parse_isotime(isotime):
    return datetime.strptime(isotime, '%Y-%m-%dT%H:%M:%S.%fZ')


def timegap(start_time, end_time):
    diff = end_time - start_time

    mins = diff.seconds / 60

    if mins == 0:
        return 'less than a minute'
    elif mins == 1:
        return 'a minute'
    elif mins < 44:
        return '{} minutes'.format(mins)
    elif mins < 89:
        return 'about an hour'
    elif mins < 1439:
        return 'about {} hours'.format(mins / 60)
    elif mins < 2519:
        return 'about a day'
    elif mins < 43199:
        return 'about {} days'.format(mins / 1440)
    elif mins < 86399:
        return 'about a month'
    elif mins < 525599:
        return 'about {} months'.format(mins / 43200)
    else:
        return 'more than a year'


def helpful_exit(msg=__doc__):
    print_ti(msg, file=sys.stderr)
    raise SystemExit


def parse_args(argv=sys.argv):
    global use_color
    global use_gui_notification

    if sys.version_info[0] < 3:
        argv = [arg.decode('utf-8') for arg in argv]

    if '--no-color' in argv:
        use_color = False
        argv.remove('--no-color')

    if '--no-gui-notification' in argv:
        use_gui_notification = False
        argv.remove('--no-gui-notification')

    # prog = argv[0]
    if len(argv) == 1:
        helpful_exit('You must specify a command.')

    head = argv[1]
    tail = argv[2:]
      
    if head in ['-h', '--help', 'h', 'help']:
        helpful_exit()

    elif head in ['e', 'edit']:
        fn = action_edit
        args = {}

    elif head in ['o', 'on']:
    	if not tail:
       	    helpful_exit('Need the name of whatever you are working on.')

        fn = action_on
        args = {
            'name': " ".join(tail).strip(),
            'time': to_datetime(' '.join(tail[1:])),
        }

    elif head in ['f', 'fin']:
        fn = action_fin
        args = {'time': to_datetime(' '.join(tail))}

    elif head in ['s', 'status']:
        fn = action_status
        args = {}

    elif head in ['l', 'log']:
        fn = action_log
        args = {'period': tail[0] if tail else None}

    elif head in ['t', 'tag']:
        if not tail:
            helpful_exit('Please provide at least one tag to add.')

        fn = action_tag
        args = {'tags': tail}

    elif head in ['n', 'note']:
        if not tail:
            helpful_exit('Please provide some text to be noted.')

        fn = action_note
        args = {'content': ' '.join(tail)}

    elif head in ['i', 'interrupt']:
        if not tail:
            helpful_exit('Need the name of whatever you are working on.')

        fn = action_interrupt
        args = {
            'name': tail[0],
            'time': to_datetime(' '.join(tail[1:])),
        }

    else:
        helpful_exit("I don't understand '" + head + "'")

    return fn, args


def main():
    fn, args = parse_args()
    fn(**args)

if __name__ == '__main__':
    main()
