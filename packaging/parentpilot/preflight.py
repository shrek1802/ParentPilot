#!/usr/bin/python3
"""Read-only desktop compatibility report. Never creates accounts or changes files.

ParentPilot's current lock window uses Tk/X11 and XFCE; Debian-based does
NOT imply any desktop session or display protocol. Stop, don't silently install
an insecure overlay into Wayland or a different desktop.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import sys

REQUIRED = {
    'Python Tkinter': 'python3',
    'XFCE desktop': 'xfce4-session',
    'XFCE bottom panel': 'xfce4-panel',
    'Parent authentication': 'pkexec',
    'System services': 'systemctl',
    'Account tools': 'adduser',
    'Password tools': 'chpasswd',
    'File permissions': 'setfacl',
    'SSL certificates': 'openssl',
    'Network discovery': 'avahi-daemon',
}

def parse_os_release(raw: str) -> dict:
    result = {}
    for line in raw.splitlines():
        if '=' not in line or line.lstrip().startswith('#'):
            continue
        k, v = line.split('=', 1)
        result[k] = v.strip().strip('"').strip("'")
    return result


def debian_family(data: dict) -> bool:
    members = set((data.get('ID', '') + ' ' + data.get('ID_LIKE', '')).lower().split())
    return bool(members.intersection({'debian', 'ubuntu', 'linuxmint'}))


def report(os_release=None, which=shutil.which, environ=None, exists=None) -> dict:
    env = os.environ if environ is None else environ
    if os_release is None:
        try:
            os_release = parse_os_release(Path('/etc/os-release').read_text(encoding='utf8'))
        except OSError:
            os_release = {}
    if exists is None:
        exists = lambda p: Path(p).exists()
    errors, notices = [], []
    if sys.version_info < (3, 9):
        errors.append('This release requires Python 3.9 or newer (older Debian/Ubuntu versions are not supported).')
    system = os_release.get('PRETTY_NAME') or os_release.get('ID') or 'Unknown Linux'
    if sys.platform != 'linux' or not debian_family(os_release):
        errors.append('This preview requires a Debian/Ubuntu-based Linux system.')
    for label, binary in REQUIRED.items():
        if not which(binary):
            errors.append(f'{label} missing ({binary}). Install the required package first.')
    browser = which('chromium') or which('chromium-browser')
    if not browser:
        errors.append('Chromium browser missing (chromium or chromium-browser).')
    session = env.get('XDG_SESSION_TYPE', '').lower()
    desktop = env.get('XDG_CURRENT_DESKTOP', '')
    if session == 'wayland':
        errors.append('This lock-screen preview needs an X11 desktop session, not Wayland.')
    elif session != 'x11':
        notices.append('We could not confirm an X11 login session. Test on XFCE/X11 before creating a child account.')
    if desktop and 'XFCE' not in desktop.upper():
        errors.append(f'This preview requires an XFCE desktop session; currently: {desktop}.')
    if not exists('/run/systemd/system'):
        notices.append('A running systemd system manager was not detected; services must work before setup.')
    if exists('/etc/max-family-control/config.json') or exists('/opt/max-family-control/control_server.py'):
        errors.append('Existing ParentPilot/Max Family Control installation detected. This fresh installer will not overwrite it.')
    if not which('lightdm'):
        notices.append('LightDM is not installed. ParentPilot can work with a manual child login, but automatic child login will be unavailable.')
    if exists('/etc/chromium/policies/managed/90-parentpilot-family.json'):
        notices.append('A ParentPilot Chromium policy already exists; the family-filter option cannot overwrite it.')
    notices.append('The fullscreen lock has only been tested on XFCE/X11; it is not a tamper-proof security boundary.')
    return {'compatible':not errors,'os':system,'session':session or 'unknown',
            'desktop':desktop or 'unknown','browser':browser or '',
            'lightdm':bool(which('lightdm')),'errors':errors,'notices':notices}


if __name__ == '__main__':
    if '--json' in sys.argv:
        print(json.dumps(report(), indent=2))
    else:
        state = report()
        print(state['os'], '—', 'Ready to set up' if state['compatible'] else 'Cannot install yet')
        for item in state['errors']:
            print('STOP:', item)
        for item in state['notices']:
            print('NOTE:', item)
    sys.exit(0)
