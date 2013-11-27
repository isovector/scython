#!/usr/bin/python2
import re, sys, os

code = r'''#!/usr/bin/python2
from sys import *
from os.path import expanduser
import string, subprocess, re, getopt, signal, os, pipes

script_name = argv[1]
args = string.join(argv[2:])

__scython_dry_run = False

uid = os.getuid()

homedir = expanduser("~") + "/"

def read_file(filename):
    with open(filename) as file:
        return file.read()

def write_file(filename, data, mode = "w"):
    with open(filename, mode) as file:
        file.write(data)

def path_exists(path):
    return os.path.exists(path)

options = { }
def __scython_get_options(os):
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
            
    args = string.join(argv[2:])

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

def __scython_call(cmd, wantReturnCode):
    if __scython_dry_run:
        print cmd
        return ""

    try:
        output = subprocess.check_output(cmd, shell=True)[:-1]
        return output if not wantReturnCode else True
    except subprocess.CalledProcessError:
        return False
'''

class BlockParser:
    def __init__(self, blockName):
        self.name = blockName
        self.hook = None
        self.hooks = { }
        self.pragmas = { }
        self.preamble = None
        self.finished = False
        self.globs = [ ]
        self.pragmas[blockName] = [ ]
    
    def addGlobal(self, glob):
        self.globs.append(glob)
    
    def addHook(self, hook, parser):
        self.hooks[hook] = parser
        self.pragmas[hook] = [ ]
        
    def parse(self, line):
        parsed = re.search(r'^(\s*)([^:]*)(:?)\s*', line)
        if not parsed:
            raise Exception("not parsed")
            
        preamble = parsed.group(1)
        data = parsed.group(2)
        isHook = parsed.group(3) == ":"
        
        if preamble == "" and not (data == self.name):
            self.finished = True
            return
        
        if self.preamble == None:
            if not (isHook and data == self.name):
                raise Exception("unmatched name " + data)
            self.preamble = preamble
            return
        
        if self.hook and len(preamble) <= len(self.preamble):
            self.hook = None

        if isHook:
            if self.hook:
                raise Exception("new hook with old hook")
            else:
                self.hook = data
                self.preamble = preamble
                return
            
        if not self.hook:
            if data in self.globs:
                self.pragmas[self.name].append(data)
            else:
                raise Exception("bad glob")
            return
        
        self.pragmas[self.hook].append(self.hooks[self.hook](data))
        
    def getHook(self, hook):
        return self.pragmas[hook]

file = open(sys.argv[1])
trappingCtrlC = False
inHereDoc = False
inPragma = False

def pragma_globs(globs):
    if "require sudo" in globs:
        if os.getuid() != 0:
            exit("%s must be run as root" % sys.argv[1])

def pragma_options(data):
    bits = [ eval(x.strip()) for x in data.split(",") ]
    if len(bits) not in [1, 2]:
        raise Exception("bad option: " + data)
    return bits[0]


pragma = BlockParser("pragma")
pragma.addHook("options", pragma_options)
pragma.addGlobal("require sudo")

for line in file:
    line = line.rstrip()
    
    if line == "":
        continue
    
    if line == "pragma:":
        inPragma = True
    
    if inPragma:
        pragma.parse(line)
        if pragma.finished:
            inPragma = False
            pragma_globs(pragma.getHook("pragma"))
            line = "__scython_get_options(%s)\n" % repr(pragma.getHook("options")) + line
        else:
            continue
    
    if re.match(r'\s*``', line):
        inHereDoc = not inHereDoc
        continue
    
    if inHereDoc:
        hereDoc = re.match(r'(\s*)(.*)', line)
        line = r'%s__scython_call(%s.format(**locals()), False)' % (hereDoc.group(1), repr(hereDoc.group(2)))
        
    else:
        # insert appropriate signal handles
        if not re.match(r'\s', line) and trappingCtrlC:
            code += "signal.signal(signal.SIGINT, trap_ctrl_c)\n"
            trappingCtrlC = False
            
        if re.search('trap_ctrl_c', line):
            trappingCtrlC = True
        
        tick = re.search(r'(.*)`(.*)`(\??)(.*)', line)
        if tick:
            line = r'%s__scython_call(%s.format(**locals()), %s)%s' % (tick.group(1), repr(tick.group(2)), len(tick.group(3)) == 1, tick.group(4))
        
        # it would be really nice if this were an expression
        format = re.search(r'([^=]*)\s*=\s*(.+)\s*>>=\s*(.+)', line)
        if format:
            line = "%s = __scython_unpacker(%s, %s)" % (format.group(1), format.group(3), format.group(2))
    
    line = re.sub(r'\$\{(\w+)\}', r'{\1}', line)
    code += line + "\n"
    
file.close()

exec code