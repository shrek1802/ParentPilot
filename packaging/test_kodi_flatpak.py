#!/usr/bin/python3
"""Offline side-by-side Kodi Flatpak tests; no real installation or user changes."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import tempfile
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / 'parentpilot'))
import kodi_flatpak_test as trial

assert trial.APP == 'tv.kodi.Kodi'
assert trial.APP_REF == 'tv.kodi.Kodi//stable'
assert 'Exec=/usr/bin/flatpak run --system tv.kodi.Kodi' in trial.DESKTOP_ENTRY
assert 'Kodi (New Version Test)' in trial.DESKTOP_ENTRY
assert trial.flathub_origin('flathub\thttps://dl.flathub.org/repo/\n') in trial.ORIGINS
assert trial.flathub_origin('flathub\thttps://bad.example/repo/\n') not in trial.ORIGINS
assert trial.parse_installed_version('          Version: 21.3\n') == '21.3'
assert trial.parse_installed_version('Version: 22.0rc1\n') == '22.0rc1'
assert trial.parse_installed_version('Version not supplied') == 'version not reported'

with tempfile.TemporaryDirectory() as folder:
    dest = Path(folder) / 'kodi-test.desktop'
    trial.write_launcher(dest)
    assert dest.read_text() == trial.DESKTOP_ENTRY
    trial.write_launcher(dest)  # idempotent
    assert dest.stat().st_mode & 0o777 == 0o644
    dest.write_text('Someone else made this launcher.')
    try:
        trial.write_launcher(dest)
        raise AssertionError('Overwrote user launcher')
    except RuntimeError:
        pass
    dest.unlink()
    dest.symlink_to(Path(folder) / 'linked')
    try:
        trial.write_launcher(dest)
        raise AssertionError('Followed a symlink')
    except RuntimeError:
        pass


def done(status=0, stdout='ok', stderr=''):
    return SimpleNamespace(returncode=status, stdout=stdout, stderr=stderr)

installed = [False]
commands = []
launches = []


def runner(args, **kwargs):
    commands.append(args)
    assert kwargs['check'] is False
    assert kwargs['capture_output'] is True
    assert kwargs['timeout'] <= 2400
    assert '--show-version' not in args, 'Flatpak does not have this option'
    if '--show-ref' in args:
        return done(0, 'app/tv.kodi.Kodi/x86_64/stable\n') if installed[0] else done(1, '', 'not installed')
    if '--show-origin' in args:
        return done(0, 'flathub\n')
    if 'remotes' in args:
        return done(0, 'flathub https://dl.flathub.org/repo/\n')
    if args[:3] == [trial.FLATPAK, '--system', 'install']:
        installed[0] = True
        return done()
    if 'info' in args:
        return done(0, 'Kodi\n         ID: tv.kodi.Kodi\n    Version: 21.3\n')
    return done()

version = trial.install_test(runner=runner, flatpak_exists=False,
                             launcher=lambda: launches.append('ready'))
assert version == '21.3'
assert launches == ['ready']
assert commands == [
    ['/usr/bin/apt-get', 'install', '-y', '--no-install-recommends', 'flatpak'],
    ['/usr/bin/flatpak', 'info', '--system', '--show-ref', 'tv.kodi.Kodi'],
    ['/usr/bin/flatpak', '--system', 'remote-add', '--if-not-exists',
     'flathub', 'https://flathub.org/repo/flathub.flatpakrepo'],
    ['/usr/bin/flatpak', 'remotes', '--system', '--columns=name,url'],
    ['/usr/bin/flatpak', '--system', 'install', '-y', '--noninteractive',
     'flathub', 'tv.kodi.Kodi//stable'],
    ['/usr/bin/flatpak', 'info', '--system', '--show-ref', 'tv.kodi.Kodi'],
    ['/usr/bin/flatpak', 'info', '--system', '--show-origin', 'tv.kodi.Kodi'],
    ['/usr/bin/flatpak', 'info', '--system', 'tv.kodi.Kodi'],
]
assert all('remove' not in cmd and 'purge' not in cmd for cmd in commands)

# Previous Preview 26 may already have installed Kodi, but failed at the
# unsupported version check. No network, remote, re-download or APT occurs.
commands.clear()
version = trial.install_test(runner=runner, flatpak_exists=True,
                             launcher=lambda: launches.append('existing'))
assert version == '21.3'
assert launches == ['ready', 'existing']
assert commands == [
    ['/usr/bin/flatpak', 'info', '--system', '--show-ref', 'tv.kodi.Kodi'],
    ['/usr/bin/flatpak', 'info', '--system', '--show-origin', 'tv.kodi.Kodi'],
    ['/usr/bin/flatpak', 'info', '--system', 'tv.kodi.Kodi'],
]

# Version text may be missing with some old Flatpak versions; verification
# succeeds based on installed app reference and origin, without a false error.
def no_version(args, **kwargs):
    if '--show-ref' in args:
        return done(0, 'app/tv.kodi.Kodi/x86_64/stable\n')
    if '--show-origin' in args:
        return done(0, 'flathub\n')
    return done(0, 'Kodi\n   ID: tv.kodi.Kodi\n')
assert trial.install_test(runner=no_version, flatpak_exists=True,
                          launcher=lambda: launches.append('no version')) == 'version not reported'
assert launches[-1] == 'no version'

# Refuse an installed package from a different remote.
def unrelated_origin(args, **kwargs):
    if '--show-ref' in args:
        return done(0, 'app/tv.kodi.Kodi/x86_64/stable\n')
    if '--show-origin' in args:
        return done(0, 'unverified\n')
    return done()
try:
    trial.install_test(runner=unrelated_origin, flatpak_exists=True,
                       launcher=lambda: launches.append('unsafe origin'))
    raise AssertionError('Accepted an unofficial Kodi installation')
except RuntimeError:
    pass
assert 'unsafe origin' not in launches

# Refuse a Flathub remote pointed at an unrelated server.
def tampered(args, **kwargs):
    if '--show-ref' in args:
        return done(1, '', 'not installed')
    if 'remotes' in args:
        return done(0, 'flathub https://untrusted.example/repo\n')
    return done()
try:
    trial.install_test(runner=tampered, flatpak_exists=True,
                       launcher=lambda: launches.append('unsafe remote'))
    raise AssertionError('Accepted a tampered Flathub remote')
except RuntimeError:
    pass
assert 'unsafe remote' not in launches

with patch.object(trial.os, 'geteuid', return_value=0), \
     patch.object(trial.sys, 'argv', ['kodi_flatpak_test.py', '--install-test']), \
     patch.object(trial, 'validate_adult_origin', return_value='adult') as adult, \
     patch.object(trial, 'parentpilot_configured', return_value=True), \
     patch.object(trial, 'install_test', return_value='21.3') as work:
    trial.main()
    adult.assert_called_once()
    work.assert_called_once()

with patch.object(trial.os, 'geteuid', return_value=1000):
    try:
        trial.main()
        raise AssertionError('Installed without administrator approval')
    except RuntimeError:
        pass

print('PASS: old Flatpak compatibility, detect previous install without downloads, official origin and separate launcher')
