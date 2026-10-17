#!/usr/bin/python3
"""Offline validation; never changes real system users or services."""
import io
import importlib.util
import pathlib
import sys
import tempfile
import xml.etree.ElementTree as ET
from contextlib import redirect_stdout

R=pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(R/'parentpilot'))
p=R/'parentpilot/setup_root.py'
spec=importlib.util.spec_from_file_location('root_setup',p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
valid={'child_name':'Max','child_user':'maxchild','child_password':'complex#2026',
       'parent_pin':'724951','youtube':'kids','netflix':True,'autologin':True,'family_filter':True}
assert m.validate(valid)==('Max','maxchild','complex#2026','724951')
for changed in ({'child_user':'root'},{'child_user':'Xx'},{'child_user':'not ok'},
                {'parent_pin':'123456'},{'child_password':'tiny'},{'netflix':'yes'},
                {'youtube':'kids && rm -rf /'}):
    t={**valid,**changed}
    try:m.validate(t)
    except ValueError:pass
    else:raise AssertionError('Unsafe input was accepted: '+str(changed))
with tempfile.TemporaryDirectory() as d:
    home=pathlib.Path(d)
    for x in ['parentpilot-browser.desktop','parentpilot-youtube.desktop','parentpilot-netflix.desktop']:
        path=home/'.local/share/applications'/x
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text('[Desktop Entry]\nType=Application\nName=Test\nExec=true\n')
    m.write_child_panel(home,1000,netflix=True)
    x=ET.parse(home/'.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-panel.xml')
    assert x.getroot().attrib['name']=='xfce4-panel'
    assert all('value' not in elem.attrib for elem in x.findall(".//property[@type='array']")+x.findall(".//property[@type='empty']"))
    assert list((home/'.config/xfce4/panel').glob('launcher-*/**/*.desktop'))
import py_compile
for py in [R/'parentpilot/wizard.py',R/'parentpilot/setup_root.py',R.parent/'desktop/max_desktop.py',R.parent/'desktop/parentpilot_lock_media.py']:
    py_compile.compile(str(py),doraise=True)
print('PASS: installer inputs, child panel XML and Python syntax; no accounts or services modified')

# Mixed Debian family compatibility checks: accepted on XFCE/X11, rejected on
# Wayland, other desktop shells, or a missing login manager if autologin asked.
from platform_check import assess
all_bins=set(('xfce4-session','xfce4-panel','python3','openssl','setfacl',
              'avahi-daemon','systemctl','pkexec','lightdm','chromium'))
for operating_system in ({'ID':'linuxmint','PRETTY_NAME':'Mint XFCE'},
                         {'ID':'debian','PRETTY_NAME':'Debian 13'},
                         {'ID':'ubuntu','PRETTY_NAME':'Xubuntu 24.04'},
                         {'ID':'mx','ID_LIKE':'debian'}):
    assert assess(operating_system,binaries=all_bins,desktop='XFCE',session_type='x11')['ok']
assert not assess({'ID':'ubuntu'},binaries=all_bins,desktop='GNOME',session_type='wayland')['ok']
assert not assess({'ID':'debian'},binaries=all_bins-{'lightdm'},desktop='XFCE',session_type='x11',auto_login=True)['ok']
assert not assess({'ID':'fedora'},binaries=all_bins,desktop='XFCE',session_type='x11')['ok']
print('PASS: supported Debian-family XFCE/X11 preflight + unsupported-desktop safety checks')