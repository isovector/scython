#!/usr/bin/python2
import re
import sys

print r'''#!/usr/bin/python2
import signal
from sys import *
import string
import subprocess
import re

args = string.join(argv[1:])

__scython_dry_run = False

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
        return subprocess.check_output(cmd, shell=True)
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