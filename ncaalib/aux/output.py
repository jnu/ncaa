# -*-coding:utf8-*-
'''
$ python ncaa2013/output.py

Utility functions for consistent (terminal) output formatting.

Copyright (c) 2013 Joseph Nudell
Freely distributable under the MIT license.
'''

from sys import stdout, stderr, stdin
try:
    import terminal
except ImportError:
    print >>stderr, "Error: unable to import terminal module."


def raw_input(prompt, stream=stderr, color='reset', bg='reset'):
    # override default raw_input, prompt goes to stderr
    stream.flush()
    terminal.screen.clearline('all', stream=stream)
    stream.write('\r%s'%terminal.colorize(prompt, color, bg))
    return stdin.readline().strip()


def print_error(message, stream=stderr):
    terminal.screen.clearline(stream=stream)
    print >>stream, terminal.colorize(message, 'red', 'white')

def print_warning(message, stream=stderr):
    terminal.screen.clearline(stream=stream)
    print >>stream, terminal.colorize(message, 'red')

def print_comment(message, stream=stderr):
    terminal.screen.clearline(stream=stream)
    print >>stream, terminal.colorize(message, 'yellow')

def print_header(message, stream=stderr):
    terminal.screen.clearline(stream=stream)
    print >>stream, terminal.colorize(message, 'white', 'blue', effect='bold')

def print_good(message, stream=stderr):
    terminal.screen.clearline(stream=stream)
    print >>stream, terminal.colorize(message, 'green')

def print_info(message, stream=stderr):
    terminal.screen.clearline(stream=stream)
    print >>stream, terminal.colorize(message, 'cyan')

def print_success(message, stream=stderr):
    terminal.screen.clearline(stream=stream)
    print >>stream, terminal.colorize(message, 'white', 'green')

def clear(stream=stdout):
    terminal.screen.clear(stream)

def clear_below(n, start=None, stream=stderr, return_=True):
    if start is not None:
        terminal.cursor.place(1, start, stream=stream)
    for i in range(n):
        terminal.screen.clearline('all', stream)
        print >>stream, ""
    if return_:
        terminal.cursor.moveup(n, stream=stream)
    stream.flush()

class ProgressBar(object):
    def __init__(self, width=40, block="█", track="░",
                       max=100, color='white', line='start', stream=stdout):
        self.width = width
        self.block = block
        self.track = track
        self.max = float(max)
        self.current = -1
        self.color = color
        try:
            if line.lower()=='end':
                self.line = terminal.screen.height()
            elif line.lower()=='start':
                self.line = 1
        except AttributeError:
            try:
                self.line = int(line)
            except:
                self.line = 1
        self.stream = stream
        self.update()

    def update(self, message="", current=None):
        # Calculate position, make bar
        if current is None:
            self.current += 1
        else:
            self.current = current
        rat = self.current / self.max
        nchars = int(round(self.width * rat))
        bar = "%s%s" % (nchars*self.block, (self.width-nchars)*self.track)
        bar = terminal.colorize(bar, self.color)
        
        # Save current cursor position
        terminal.cursor.save(self.stream)
        terminal.cursor.place(1, self.line, self.stream)
        terminal.screen.clearline(part='all', stream=self.stream)
        print >>self.stream, " %d%% [ %s ] %s" % (int(100*rat), bar, message)
        terminal.cursor.unsave(self.stream)

    def destroy(self):
        terminal.cursor.save(self.stream)
        terminal.cursor.place(1, self.line, self.stream)
        terminal.screen.clearline(part='all', stream=self.stream)
        terminal.cursor.unsave(self.stream)