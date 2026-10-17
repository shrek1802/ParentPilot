#!/usr/bin/env python3
"""Offline distro/runtime matrix. Never provisions a user or invokes system services."""
import importlib.util
from pathlib import Path

here=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('preflight',here/'parentpilot/preflight.py')
pre=importlib.util.module_from_spec(spec);spec.loader.exec_module(pre)
programs=set(pre.REQUIRED.values())|{'chromium','lightdm'}
which=lambda name: '/usr/bin/'+name if name in programs else None
exists=lambda path: path == '/run/systemd/system'
x11={'XDG_SESSION_TYPE':'x11','XDG_CURRENT_DESKTOP':'XFCE'}
versions=(
  {'PRETTY_NAME':'Debian GNU/Linux 12','ID':'debian'},
  {'PRETTY_NAME':'Debian GNU/Linux 13','ID':'debian'},
  {'PRETTY_NAME':'Ubuntu 24.04','ID':'ubuntu','ID_LIKE':'debian'},
  {'PRETTY_NAME':'Linux Mint 22','ID':'linuxmint','ID_LIKE':'ubuntu debian'},
  {'PRETTY_NAME':'MX Linux','ID':'mx','ID_LIKE':'debian'},
)
for version in versions:
    result=pre.report(os_release=version,which=which,environ=x11,exists=exists)
    assert result['compatible'],(version,result)
    assert result['lightdm']
for env,problem in (({'XDG_SESSION_TYPE':'wayland','XDG_CURRENT_DESKTOP':'XFCE'}, 'Wayland'),
                    ({'XDG_SESSION_TYPE':'x11','XDG_CURRENT_DESKTOP':'GNOME'}, 'XFCE')):
    result=pre.report(os_release=versions[0],which=which,environ=env,exists=exists)
    assert not result['compatible'] and any(problem in issue for issue in result['errors'])
assert not pre.report(os_release={'ID':'fedora'},which=which,environ=x11,exists=exists)['compatible']
assert not pre.report(os_release=versions[0],which=lambda n:None,environ=x11,exists=exists)['compatible']
assert not pre.report(os_release=versions[0],which=which,environ=x11,
                      exists=lambda p: p=='/etc/max-family-control/config.json')['compatible']
assert pre.debian_family(pre.parse_os_release('ID=linuxmint\nID_LIKE="ubuntu debian"\n'))
print('PASS: Debian-family/XFCE/X11 checks and safe refusal for Wayland, GNOME, existing installs, missing tools')
