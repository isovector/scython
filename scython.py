#!/usr/bin/python2
import re
import sys

print r'''#!/usr/bin/python2
from sys import *
import string, subprocess, re, getopt, signal

args = string.join(argv[1:])

__scython_dry_run = False

options = { }
def get_options(*os):
    global argv, args, options

    shortOpts = ""
    longOpts = [ ]
    mapping = { }
    
    for opt in os:
        try:
            index = opt.index("|")
            if index != 1:
                exit('scython Error: Invalid short option "%s"' % opt[0:index])
            shortOpt = opt[0]
            shortOpts += shortOpt
            if opt[-1] == "=":
                shortOpts += ":"
            opt = opt[index + 1:]
            
            mapping[shortOpt] = opt
        except ValueError:
            pass
        
        longOpts.append(opt)
        
    try:
        opts, argv = getopt.gnu_getopt(argv, shortOpts, longOpts)
    except getopt.GetoptError as err:
        exit(str(err))
        
    for opt, val in opts:
        while opt[0] == "-":
            opt = opt[1:]
    
        if opt in mapping:
            opt = mapping[opt]
            if opt[-1] == "=":
                opt = opt[0:-1]

        if val == "":
            val = 1
            if opt in options:
                options[opt] += val
            else:
                options[opt] = 1
        else:
            options[opt] = val
            
    args = string.join(argv[1:])

def __scython_unpacker(format, haystack):
    formatTypes = {
        '%d': (int, r'(\d+)'),
        '%f': (float , r'([\d.]+)'),
        '%b': (bool, r'(true|false)'),
        '%s': (str, r'(.*)')
    }
    
    types = []
    search = re.escape(format)
    
    for match in re.findall(r'%[dfbs]', format):
        types.append(formatTypes[match][0])
        search = re.sub(r'\\%s' % match, formatTypes[match][1], search, 1)
    
    try:
        return [t(s) for t,s in zip(types, re.search(search, haystack).groups())]
        
    except AttributeError:
        exit('scython Error: Couldn\'t parse "%s"' % format)

def __scython_call(cmd):
    if __scython_dry_run:
        print cmd
        return ""

    try:
        return subprocess.check_output(cmd, shell=True)[:-1]
    except subprocess.CalledProcessError:
        return ""
'''



file = open(sys.argv[1])
trappingCtrlC = False
inHereDoc = False

for line in file:
    line = line.rstrip()
    
    if re.match(r'\s*``', line):
        inHereDoc = not inHereDoc
        continue
    
    if inHereDoc:
        hereDoc = re.match(r'(\s*)(.*)', line)
        line = r'%s__scython_call(%s.format(**locals()))' % (hereDoc.group(1), repr(hereDoc.group(2)))
        
    else:
        # insert appropriate signal handles
        if not re.match(r'\s', line) and trappingCtrlC:
            print "signal.signal(signal.SIGINT, trap_ctrl_c)"
            trappingCtrlC = False
            
        if re.search('trap_ctrl_c', line):
            trappingCtrlC = True
        
        tick = re.search(r'(.*)`(.*)`(.*)', line)
        if tick:
            line = r'%s__scython_call(%s.format(**locals()))%s' % (tick.group(1), repr(tick.group(2)), tick.group(3))
        
        # it would be really nice if this were an expression
        format = re.search(r'([^=]*)\s*=\s*(.+)\s*>>=\s*(.+)', line)
        if format:
            line = "%s = __scython_unpacker(%s, %s)" % (format.group(1), format.group(3), format.group(2))
    
    line = re.sub(r'\$\{(\w+)\}', r'{\1}', line)
    print line
    
file.close()