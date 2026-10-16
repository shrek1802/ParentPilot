#!/usr/bin/env python3
"""Max Family Control desktop watchdog. Restarts the interface if it crashes or is closed.
Not a secure kiosk; both processes run as max, which means a technical user can kill them.
"""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

CHILD = Path('/opt/max-family-control/max_desktop.py')
stop = False
running = None

def exit_gracefully(_signum, _frame):
    global stop
    stop = True
    if running is not None and running.poll() is None:
        running.terminate()

signal.signal(signal.SIGTERM, exit_gracefully)
signal.signal(signal.SIGINT, exit_gracefully)

while not stop:
    if not CHILD.is_file():
        print('Max Family Control UI missing; watchdog stopping', file=sys.stderr)
        break
    running = subprocess.Popen(['/usr/bin/python3','-B',str(CHILD)], close_fds=True)
    while not stop and running.poll() is None:
        time.sleep(.25)
    if stop: break
    # Limit crash churn, but still recover quickly if the UI is closed.
    time.sleep(2)
