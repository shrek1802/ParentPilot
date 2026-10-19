#!/usr/bin/python3
"""Offline validation; never changes real system users or services."""
import io
import importlib.util
import pathlib
import tempfile
import xml.etree.ElementTree as ET
from contextlib import redirect_stdout

R=pathlib.Path(__file__).resolve().parent
p=R/'parentpilot/setup_root.py'
spec=importlib.util.spec_from_file_location('root_setup',p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
valid={'child_name':'Max','child_user':'maxchild','child_password':'complex#2026',
       'parent_pin':'724951','youtube':'kids','netflix':True,'autologin':True,'family_filter':True,'screen_view':False}
assert m.validate(valid)==('Max','maxchild','complex#2026','724951')
# Requested child Linux login password minimum is six; parent PIN stays six digits.
assert m.validate({**valid, 'child_password': 'Ab12!x'})[2] == 'Ab12!x'
for changed in ({'child_user':'root'},{'child_user':'Xx'},{'child_user':'not ok'},
                {'parent_pin':'123456'},{'child_password':'tiny'},{'child_password':'12345'},{'netflix':'yes'},
                {'youtube':'kids && rm -rf /'},{'screen_view':'yes'}):
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
    # App launchers are centred, and systray/clock remain on the right.
    positions=[p.attrib.get('name') for p in x.findall(".//property[@name='plugin-ids']/value")]
    plugins=x.find(".//property[@name='plugin-ids']")
    assert plugins is not None
    ids=[int(v.attrib['value']) for v in plugins.findall('value')]
    assert ids.index(18) < ids.index(10) < ids.index(19) < ids.index(21)
    assert ids[-1] == 22
    for key in ('plugin-18','plugin-19'):
        spacer=x.find(f".//property[@name='{key}']/property[@name='expand']")
        assert spacer is not None and spacer.attrib['value'] == 'true'
    # Detect our original panel and repair its layout without provisioning users.
    from parentpilot import child_panel as cp
    assert cp.existing_parentpilot_panel(home)
    old_panel=home/'.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-panel.xml'
    old_xml=old_panel.read_text()
    assert 'plugin-19' in old_xml
    from unittest.mock import patch
    from types import SimpleNamespace
    with patch.object(cp.os, 'geteuid', return_value=1000), \
         patch.object(cp.os, 'getuid', return_value=1000), \
         patch.object(cp.pwd, 'getpwuid', return_value=SimpleNamespace(pw_dir=str(home),pw_gid=1000)):
        cp.repair_child_panel()
    assert old_panel.is_file()
    assert cp.existing_parentpilot_panel(home)

import py_compile
for py in [R/'parentpilot/wizard.py',R/'parentpilot/preflight.py',R/'parentpilot/setup_root.py',R.parent/'desktop/max_desktop.py',R.parent/'desktop/parentpilot_lock_media.py',R.parent/'desktop/screen_view.py']:
    py_compile.compile(str(py),doraise=True)
print('PASS: six-character child password, compact panel layout/repair, and Python syntax; no system users modified')
