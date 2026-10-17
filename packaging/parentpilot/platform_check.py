#!/usr/bin/python3
"""ParentPilot v0.5 platform preflight (no privileged commands, no changes).

A package being installable by dpkg does not imply that its X11/XFCE overlay
works on every Debian-based graphical environment. Explicitly reject unknown
sessions rather than leaving parents with a false sense of enforcement.
"""
from __future__ import annotations
import os
from pathlib import Path
import shutil

DISTROS = {
    'linuxmint': 'Linux Mint',
    'debian': 'Debian',
    'ubuntu': 'Ubuntu / Xubuntu',
    'pop': 'Pop!_OS',
    'mx': 'MX Linux',
    'kali': 'Kali Linux',
}


def parse_os_release(value: str) -> dict:
    out = {}
    for line in value.splitlines():
        if '=' not in line or line.lstrip().startswith('#'):
            continue
        key, item = line.split('=', 1)
        out[key] = item.strip().strip('"').strip("'")
    return out


def assess(os_release: dict, *, binaries: set[str], session_type: str = '',
           desktop: str = '', auto_login: bool = False, systemd: bool = True) -> dict:
    distro_id = os_release.get('ID', '').lower()
    family = (os_release.get('ID_LIKE') or '').lower().split()
    debian_based = distro_id in DISTROS or 'debian' in family or 'ubuntu' in family
    distro_name = os_release.get('PRETTY_NAME') or DISTROS.get(distro_id, distro_id or 'Unknown Linux')
    blockers: list[str] = []
    warnings: list[str] = []
    if not debian_based:
        blockers.append('This build requires a Debian/Ubuntu-based Linux system with APT.')
    if not systemd:
        blockers.append('The ParentPilot background service requires systemd. This system does not appear to use it.')
    needed = {'xfce4-session': 'XFCE desktop', 'xfce4-panel': 'XFCE panel',
              'python3': 'Python', 'openssl': 'HTTPS tools', 'setfacl': 'Linux access controls',
              'avahi-daemon': 'phone discovery', 'systemctl': 'system services',
              'pkexec': 'administrator approval', 'lightdm': 'graphical login manager'}
    if not auto_login:
        needed.pop('lightdm')
    for command, label in needed.items():
        if command not in binaries:
            if command == 'pkexec':
                blockers.append('Administrator approval tool (pkexec) is missing. Install polkit.')
            elif command == 'lightdm':
                blockers.append('Automatic child login requires LightDM. Disable automatic login or install LightDM.')
            else:
                blockers.append(f'{label} is missing ({command}).')
    if not {'chromium', 'chromium-browser'} & binaries:
        blockers.append('Chromium is not installed. Install Chromium in your Software Manager.')
    # Wayland compositors do not respect the X11-only overlay/window stacking.
    if session_type.lower() == 'wayland':
        blockers.append('This login uses Wayland. ParentPilot v0.5 supports XFCE on X11 only.')
    if desktop and 'xfce' not in desktop.lower():
        blockers.append('You are using ' + desktop + '. ParentPilot needs an XFCE desktop session.')
    if not session_type:
        warnings.append('The display session could not be detected. Confirm XFCE on X11 before completing setup.')
    if not desktop:
        warnings.append('Your desktop name could not be detected. A parent should confirm XFCE before installing.')
    if distro_id not in ('linuxmint', 'debian', 'ubuntu'):
        warnings.append('This Debian-family variant is not yet device-tested. Use a spare computer first.')
    if auto_login:
        warnings.append('Automatic login removes the Linux password prompt; the separate ParentPilot PIN still controls time.')
    return {'ok': not blockers, 'distro': distro_name, 'blockers': blockers, 'warnings': warnings,
            'display': f'{desktop or "Unknown desktop"} / {session_type.upper() or "Unknown display"}'}


def inspect_host(*, auto_login: bool = False, env: dict | None = None,
                 os_release_file: Path = Path('/etc/os-release')) -> dict:
    env = os.environ if env is None else env
    try:
        os_release = parse_os_release(os_release_file.read_text(encoding='utf-8'))
    except OSError:
        os_release = {}
    commands = ('xfce4-session', 'xfce4-panel', 'python3', 'openssl', 'setfacl',
                'avahi-daemon', 'systemctl', 'pkexec', 'lightdm', 'chromium', 'chromium-browser')
    binaries = {command for command in commands if shutil.which(command)}
    # In GUI setup the environment normally includes these, unlike a pkexec subprocess.
    return assess(os_release, binaries=binaries,
                  session_type=env.get('XDG_SESSION_TYPE', ''),
                  desktop=env.get('XDG_CURRENT_DESKTOP', ''),
                  auto_login=auto_login,
                  systemd=Path('/run/systemd/system').is_dir())