#!/usr/bin/env python3
"""ParentPilot child-session watchdog: only one supervisor per child account.

An advisory flock stops duplicate desktop autostarts or lingering supervisors
from spawning competing fullscreen lock screens. No account or PIN changes.
"""
import errno
import fcntl
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

CHILD = Path('/opt/max-family-control/max_desktop.py')
LOCK_PATH = Path.home() / '.local' / 'state' / 'parentpilot' / 'desktop-supervisor.lock'
stop = False
running = None


def acquire_singleton():
    LOCK_PATH.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(str(LOCK_PATH), os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        os.close(fd)
        if exc.errno in (errno.EACCES, errno.EAGAIN):
            return None
        raise
    os.ftruncate(fd, 0)
    os.write(fd, str(os.getpid()).encode('ascii') + b'\n')
    return fd


def exit_gracefully(_signum, _frame):
    global stop
    stop = True
    if running is not None and running.poll() is None:
        running.terminate()


def supervise():
    global running
    lock_fd = acquire_singleton()
    if lock_fd is None:
        print('ParentPilot desktop already supervised; duplicate startup ignored.', flush=True)
        return 0
    try:
        signal.signal(signal.SIGTERM, exit_gracefully)
        signal.signal(signal.SIGINT, exit_gracefully)
        while not stop:
            if not CHILD.is_file():
                print('ParentPilot desktop missing; watchdog stopping.', file=sys.stderr)
                return 1
            running = subprocess.Popen(['/usr/bin/python3', '-B', str(CHILD)], close_fds=True)
            while not stop and running.poll() is None:
                time.sleep(.25)
            if stop:
                break
            time.sleep(2)
        if running is not None and running.poll() is None:
            running.terminate()
            try:
                running.wait(timeout=3)
            except subprocess.TimeoutExpired:
                running.kill()
                running.wait(timeout=3)
        return 0
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


if __name__ == '__main__':
    sys.exit(supervise())
