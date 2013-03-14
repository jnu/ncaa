# -*- coding:utf8 -*-
'''
$ python terminal.py

Module for basic terminal output manipulation.

Should work on on *nix, on most xterm-based consoles.
Largely untested, though.

Implements 'save' and 'unsave' (ESC+[s and ESC+[u)
which most terminals do not honor.

Copyright (c) 2013 Joseph Nudell
Freely distributable under the MIT license.
'''

from sys import stdout, stdin, stderr
import os
import termios
import tty


ESC = '\033['


class config:
    '''Set dark=False if on a white screen.'''
    dark = True
    saved = None


class color:
    '''Wrap ANSI color escape sequences'''
    class fg:
        black, red, green, yellow, blue, magenta, cyan, white \
            = tuple(range(90, 98))
        reset = 99
    
    class bg:
        black, red, green, yellow, blue, magenta, cyan, white \
            = tuple(range(100, 108))
        reset = 109
    
    class lum:
        '''Adjust 'luminosity' of text. Options are bright, dim, and normal.
        Note bright is traditionally 1, which I've called 'bold' in the
        color.effect class. Here it's actually the same as 'nomral', since
        brightness is better conveyed through high-intensity colors.'''
        bright = 22
        dim = 2
        normal = 22
    
    class effect:
        '''Not all effects are always implemented'''
        bold = 1
        standout = 3
        underline = 4
        blink = 5
        invert = 7
        invisible = 8
        normal = 22
        
    reset = ESC+'0m'
    
    @staticmethod
    def make_color(fg, bg, effect, lum):
        '''Create style based on fg color, bg color, effect,
        and lum(inosity)'''
        fgc = getattr(color.fg, fg)
        bgc = getattr(color.bg, bg)
        if not config.dark: fgc -= 60
        if not config.dark: bgc -= 60
        return '%s%d;%d;%d;%dm' % (ESC, fgc, bgc,
                                     getattr(color.effect, effect),
                                     getattr(color.lum, lum))


def colorize(msg, fg='reset', bg='reset', lum='normal', effect='normal'):
    '''Wrap given msg in specified style.'''
    return "%s%s%s" % (color.make_color(fg.lower(),
                                        bg.lower(),
                                        effect.lower(),
                                        lum).lower(), msg, color.reset)



class cursor:
    '''Collection of functions for manipulating cursor position.'''
    
    class direction:
        up = 'A'
        down = 'B'
        right = 'C'
        left = 'D'
        
    @staticmethod
    def move(direction, n=1, stream=stdout):
        stream.write('%s%d%s' % (ESC, n,
                                 getattr(cursor.direction, direction)))
    
    @staticmethod
    def moveleft(n=1, stream=stdout):
        cursor.move('left', n, stream)
    
    @staticmethod
    def moveright(n=1, stream=stdout):
        cursor.move('right', n, stream)
    
    @staticmethod
    def moveup(n=1, stream=stdout):
        cursor.move('up', n, stream)
    
    @staticmethod
    def movedown(n=1, stream=stdout):
        cursor.move('down', n, stream)
    
    @staticmethod
    def place(x,y, stream=stdout):
        stream.write("%s%d;%dH" % (ESC, y, x))

    @staticmethod
    def save(stream=stdout):
        '''Save position. Terminals I use don't honor ESC+[s for save, so
        implement using cursor.pos() (which uses ESC+[6n)'''
        #print >>stream, "%ss"%ESC,
        config.saved = cursor.pos()
    
    @staticmethod
    def unsave(stream=stdout):
        '''Load position. Terms don't honor ESC+[u, so implement with
        cursor.pos().'''
        #print >>stream, "%su"%ESC,
        if type(config.saved) is list and len(config.saved)==2:
            cursor.place(config.saved[1], config.saved[0])

    @staticmethod
    def pos(stream=stdout):
        '''Get cursor position.'''
        
        # Save term settings
        fd = stdin.fileno()
        prev = termios.tcgetattr(fd)
        
        stream.write("\033[6n")
        
        resp = ""
        ch = ''
        
        # Immitate getch() until 'R' (end of tty response, e.g. \033[1;1R)
        try:
            tty.setraw(fd)
            while ch!='R':
                ch = stdin.read(1)
                resp += ch
        
        finally:
            # Reset term mode
            termios.tcsetattr(fd, termios.TCSADRAIN, prev)
        
        try:
            # First two chars in response are \033 and [, last is R
            return [int(c) for c in resp[2:-1].split(';')]
        except:
            # In case of failure
            return [-1, -1]
        

    


class screen:
    '''Collection of functions relating to screen. Clearing fns, size fns.'''
    
    @staticmethod
    def clear(stream=stdout):
        '''Clear screen. Not all terminals place cursor at top left, so do
        it manually.'''
        cursor.place(1,1,stream)
        stream.write("%s2J" % ESC)
    
    @staticmethod
    def clearline(part='all', stream=stdout):
        '''Can clear all of line, part of line before cursor, and part of line
        after cursor.'''
        parts = {
            'all': 2,
            'start': 1,
            'end' : 0
        }
        stream.write("%s%dK" % (ESC, parts[part]))
    
    @staticmethod
    def size():
        '''Get terminal size as (x,y) in columns and rows, respectively.'''
        size = os.popen('stty size', 'r').read().split()
        return (int(size[1]), int(size[0]),)
    
    @staticmethod
    def cols():
        '''Get number of columns in terminal'''
        return screen.size()[0]
    
    @staticmethod
    def rows():
        '''Get number of rows in terminal'''
        return screen.size()[1]
    
    @staticmethod
    def width():
        '''Alias of screen.cols()'''
        return screen.cols()
    
    @staticmethod
    def height():
        '''Alias of screen.rows()'''
        return screen.rows()

