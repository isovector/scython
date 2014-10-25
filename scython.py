#!/usr/bin/python
import re, sys, os

from sys import *
from os.path import expanduser
import string, subprocess, re, getopt, signal, os, pipes


# preamble starts here

__scython_dry_run = False

def read_file(filename):
    with open(filename) as file:
        return file.read()

def write_file(filename, data, mode = "w"):
    with open(filename, mode) as file:
        file.write(data)

def path_exists(path):
    return os.path.exists(path)

def has_network():
    return __scython_call("ping -c1 google.com 2> /dev/null", True)

class switch(object):
    def __init__(self, value):
        self.value = value
        self.fall = False

    def __iter__(self):
        """Return the match method once, then stop"""
        yield self.match
        raise StopIteration

    def match(self, *args):
        """Indicate whether or not to enter a case suite"""
        if self.fall or not args:
            return True
        elif self.value in args: # changed for v1.5, see below
            self.fall = True
            return True
        else:
            return False

"""
def get_persistence(name):
    persistenceDir = expanduser("~") + "/.scython"
    `mkdir ${persistenceDir}`
    return "%s/%s.tmp" % (persistenceDir, name)
"""

options = { }
def __scython_get_options(os):
    global argv, argc, args, options

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

    args = string.join(argv)
    argc = len(argv)

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

# preamble ends

__host_code = "#!/usr/bin/python2\n"

__host_file = open(sys.argv[1])
__host_ctrlTrap = False
__host_hereDoc = False
__host_inPragma = False

def pragma_globs(globs):
    if "require sudo" in globs:
        if os.getuid() != 0:
            exit("%s must be run as root" % sys.argv[1])

    if "require network" in globs:
        if not has_network():
            exit("no network connection")

def pragma_options(data):
    bits = [ eval(x.strip()) for x in data.split(",") ]
    if len(bits) not in [1, 2]:
        raise Exception("bad option: " + data)
    return bits[0]


__host_pragma = BlockParser("pragma")
__host_pragma.addHook("options", pragma_options)
__host_pragma.addGlobal("require sudo")
__host_pragma.addGlobal("require network")

for line in __host_file:
    line = line.rstrip()

    if line == "":
        continue

    if line == "pragma:":
        __host_inPragma = True

    if __host_inPragma:
        __host_pragma.parse(line)
        if __host_pragma.finished:
            __host_inPragma = False
            pragma_globs(__host_pragma.getHook("pragma"))
            line = "__scython_get_options(%s)\n" % repr(__host_pragma.getHook("options")) + line
        else:
            continue

    if re.match(r'\s*``', line):
        __host_hereDoc = not __host_hereDoc
        continue

    if __host_hereDoc:
        hereDoc = re.match(r'(\s*)(.*)', line)
        line = r'%s__scython_call(%s.format(**locals()), False)' % (hereDoc.group(1), repr(hereDoc.group(2)))

    else:
        # insert appropriate signal handles
        if not re.match(r'\s', line) and __host_ctrlTrap:
            __host_code += "signal.signal(signal.SIGINT, trap_ctrl_c)\n"
            __host_ctrlTrap = False

        if re.search('trap_ctrl_c', line):
            __host_ctrlTrap = True

        tick = re.search(r'(.*)`(.*)`(\??)(.*)', line)
        if tick:
            line = r'%s__scython_call(%s.format(**locals()), %s)%s' % (tick.group(1), repr(tick.group(2)), len(tick.group(3)) == 1, tick.group(4))

        # it would be really nice if this were an expression
        format = re.search(r'([^=]*)\s*=\s*(.+)\s*>>=\s*(.+)', line)
        if format:
            line = "%s = __scython_unpacker(%s, %s)" % (format.group(1), format.group(3), format.group(2))

    line = re.sub(r'\$\{(\w+)\}', r'{\1}', line)
    __host_code += line + "\n"

__host_file.close()


# setup environment

script_name = argv[1]
argv = argv[2:]
argc = len(argv)
args = string.join(argv)
uid = os.getuid()
HOME = expanduser("~") + "/"


# go for it!
#try:
exec __host_code
"""
except Exception as e:
    class bcolors:
        HEADER = '\033[95m'
        OKBLUE = '\033[94m'
        OKGREEN = '\033[92m'
        WARNING = '\033[93m'
        FAIL = '\033[91m'
        ENDC = '\033[0m'

    import traceback
    type, _, _ = sys.exc_info()

    lineNum = int(re.match(r'[^0-9]*([0-9]+)', traceback.format_exc().splitlines()[-2]).group(1)) - 1
    print "%sFile \"%s\", (parsed) line %d, in <module>%s" % (bcolors.WARNING, script_name, lineNum, bcolors.ENDC)
    print "%s%s: %s%s\n" % (bcolors.WARNING, type.__name__, str(e), bcolors.ENDC)

    lines = __host_code.split("\n")
    for i in range(max(lineNum - 3, 0), min(lineNum + 3, len(lines) - 1)):
        if i == lineNum:
            print bcolors.FAIL + lines[i] + bcolors.ENDC
        else:
            print lines[i]
"""
