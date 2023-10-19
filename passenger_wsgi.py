import sys

import os

INTERP = os.path.expanduser("/opt/python/python-3.9.0/bin/python")
if sys.executable != INTERP:
   os.execl(INTERP, INTERP, *sys.argv)

sys.path.append(os.getcwd())

from server import application