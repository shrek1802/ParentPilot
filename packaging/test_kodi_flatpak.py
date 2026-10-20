#!/usr/bin/python3
"""Offline Kodi Flatpak trial tests; never install software or touch a real system."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import tempfile
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent/'parentpilot'))
import kodi_flatpak_test as trial

assert trial.APP=='tv.kodi.Kodi'
assert trial.APP_REF=='tv.kodi.Kodi//stable'
assert 'Exec=/usr/bin/flatpak run --system tv.kodi.Kodi' in trial.DESKTOP_ENTRY
assert 'Kodi (New Version Test)' in trial.DESKTOP_ENTRY
assert trial.flathub_origin('flathub\thttps://dl.flathub.org/repo/\n') in trial.ORIGINS
assert trial.flathub_origin('flathub\thttps://bad.example/repo/\n') not in trial.ORIGINS

with tempfile.TemporaryDirectory() as folder:
    dest=Path(folder)/'kodi-test.desktop'
    trial.write_launcher(dest)
    assert dest.read_text()==trial.DESKTOP_ENTRY
    trial.write_launcher(dest) # idempotent
    assert dest.stat().st_mode & 0o777 == 0o644
    dest.write_text('Someone else made this launcher.')
    try:
        trial.write_launcher(dest)
        raise AssertionError('Overwrote user launcher')
    except RuntimeError:
        pass
    dest.unlink()
    dest.symlink_to(Path(folder)/'linked')
    try:
        trial.write_launcher(dest)
        raise AssertionError('Followed a symlink')
    except RuntimeError:
        pass

commands=[]
launches=[]
def fake_runner(args, **kwargs):
    commands.append(args)
    assert kwargs['check'] is False
    assert kwargs['capture_output'] is True
    assert kwargs['timeout'] <= 2400
    if 'remotes' in args:
        return SimpleNamespace(returncode=0,stdout='flathub https://dl.flathub.org/repo/\n',stderr='')
    if 'info' in args:
        return SimpleNamespace(returncode=0,stdout='21.3\n',stderr='')
    return SimpleNamespace(returncode=0,stdout='ok',stderr='')
version=trial.install_test(runner=fake_runner,flatpak_exists=False,
                           launcher=lambda:launches.append('ready'))
assert version=='21.3'
assert launches==['ready']
assert commands==[
    ['/usr/bin/apt-get','install','-y','--no-install-recommends','flatpak'],
    ['/usr/bin/flatpak','--system','remote-add','--if-not-exists',
     'flathub','https://flathub.org/repo/flathub.flatpakrepo'],
    ['/usr/bin/flatpak','remotes','--system','--columns=name,url'],
    ['/usr/bin/flatpak','--system','install','-y','--noninteractive',
     'flathub','tv.kodi.Kodi//stable'],
    ['/usr/bin/flatpak','info','--system','--show-version','tv.kodi.Kodi'],
]
assert not any('kodi' in arg.lower() for arg in commands[0])
assert all('remove' not in cmd and 'purge' not in cmd for cmd in commands)
commands.clear()
trial.install_test(runner=fake_runner,flatpak_exists=True,
                   launcher=lambda:launches.append('existing'))
assert commands[0][0]=='/usr/bin/flatpak', 'Installed Flatpak must not re-run APT'
assert len(commands)==4
commands.clear()
def tampered(args,**kwargs):
    if 'remotes' in args:
        return SimpleNamespace(returncode=0,stdout='flathub https://untrusted.example/repo\n',stderr='')
    return SimpleNamespace(returncode=0,stdout='ok',stderr='')
try:
    trial.install_test(runner=tampered,flatpak_exists=True,
                       launcher=lambda:launches.append('unsafe'))
    raise AssertionError('Accepted an untrusted Flathub replacement remote')
except RuntimeError:
    pass
assert 'unsafe' not in launches

with patch.object(trial.os,'geteuid',return_value=0),\
     patch.object(trial.sys,'argv',['kodi_flatpak_test.py','--install-test']),\
     patch.object(trial,'validate_adult_origin',return_value='adult') as adult,\
     patch.object(trial,'parentpilot_configured',return_value=True),\
     patch.object(trial,'install_test',return_value='21.3') as work:
    trial.main()
    adult.assert_called_once()
    work.assert_called_once()
with patch.object(trial.os,'geteuid',return_value=1000):
    try:
        trial.main()
        raise AssertionError('Installed without administrator approval')
    except RuntimeError:
        pass
print('PASS: official Flathub-only side-by-side Kodi test, separate launcher, no classic Kodi changes')
