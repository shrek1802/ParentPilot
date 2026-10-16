#!/usr/bin/env python3
"""Local admin recovery tool. Run as sudo; never type the password in a command argument."""
import getpass
import os
import sys
from pathlib import Path
from control_server import CONFIG_DIR, CONFIG_FILE, STATE_FILE, atomic_write, clean_state, hash_password
import json


def main():
    if os.geteuid() != 0:
        raise SystemExit('Run with sudo from a separate adult administrator account.')
    if len(sys.argv) != 2 or sys.argv[1] not in ('password','reset-day'):
        raise SystemExit('Usage: sudo python3 /opt/max-family-control/admin.py password|reset-day')
    if sys.argv[1] == 'password':
        p1 = getpass.getpass('New parent PIN (exactly 6 digits): ')
        p2 = getpass.getpass('Repeat PIN: ')
        if not (len(p1) == 6 and p1.isascii() and p1.isdecimal()) or p1 != p2:
            raise SystemExit('PIN must be exactly 6 digits, and entries must match. No changes made.')
        config = json.loads(CONFIG_FILE.read_text())
        config['password'] = hash_password(p1)
        atomic_write(CONFIG_FILE, config)
        os.system('chown root:maxfamily /etc/max-family-control/config.json')
        os.chmod(CONFIG_FILE,0o640)
        print('Changed. Restart the Family Control service to apply: sudo systemctl restart max-family-control')
    else:
        confirm = input('Reset today to zero approved time? Type RESET: ')
        if confirm != 'RESET':
            raise SystemExit('Cancelled')
        atomic_write(STATE_FILE, clean_state())
        os.system('chown maxfamily:maxfamily /var/lib/max-family-control/state.json')
        print('Reset. Restart the service if currently running.')

if __name__ == '__main__': main()
