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

    # Existing Preview 8-11 launchers may have generic theme icons or badly
    # escaped desktop entries. Preview 12 must repair the REAL launcher
    # files, not only regenerate xfce4-panel.xml.
    from parentpilot.child_panel import ICONS
    expected = {
        10: 'parentpilot-browser.desktop',
        11: 'thunar.desktop',
        12: 'parentpilot-youtube.desktop',
        13: 'parentpilot-netflix.desktop',
    }
    for number, name in expected.items():
        active = home/'.config/xfce4/panel'/f'launcher-{number}'/name
        assert active.is_file(), (number, name)
        raw = active.read_text()
        lines = raw.splitlines()
        assert lines[0] == '[Desktop Entry]', (number, repr(raw[:120]))
        assert 'Type=Application' in lines
        assert 'Icon=' + str(ICONS[number]) in lines
        assert not any('\\n' in line for line in lines), 'Malformed literal newline escape'
        assert 'Exec=' in raw
        if number in (10, 12, 13):
            original = home/'.local/share/applications'/name
            assert original.read_text() == raw, 'Panel should match repaired child app entry'
            assert 'Exec=true' in raw, 'Preserve child launcher command on repair'
    icons = ['browser.svg', 'files.svg', 'youtube.svg', 'netflix.svg']
    for name in icons:
        image = ET.parse(R/'parentpilot'/name).getroot()
        assert image.tag.endswith('svg'), name

    from parentpilot import child_panel as cp
    # The child menu must list only explicitly allowed family apps, not
    # the default XFCE System, Settings, Office, or Run Program categories.
    menu = home / '.config/menus/parentpilot.menu'
    xml = ET.parse(menu).getroot()
    included = [n.text for n in xml.findall('./Include/Filename')]
    assert included == [
        'parentpilot-browser.desktop', 'parentpilot-files.desktop',
        'parentpilot-youtube.desktop', 'parentpilot-netflix.desktop',
        'parentpilot-logout.desktop',
    ], included
    assert xml.findtext('AppDir') == str(home/'.local/share/applications')
    assert xml.find('./Include/All') is None
    assert xml.find('./DefaultMergeDirs') is None
    for filename in included:
        entry = home/'.local/share/applications'/filename
        raw = entry.read_text()
        assert raw.startswith('[Desktop Entry]\n'), (filename, repr(raw))
        assert '\nExec=' in raw and '\nIcon=' in raw, (filename, repr(raw))
        assert r'\n' not in raw
    assert (home/'.local/share/applications/parentpilot-files.desktop').read_text().find('Exec=thunar') != -1
    assert 'xfce4-session-logout' in (home/'.local/share/applications/parentpilot-logout.desktop').read_text()
    app_menu = x.find(".//property[@name='plugin-1']")
    assert app_menu.find("./property[@name='custom-menu']").get('value') == 'true'
    assert app_menu.find("./property[@name='custom-menu-file']").get('value') == str(menu)
    assert x.find(".//property[@name='panel-1']/property[@name='icon-size']").get('value') == '28'
    assert x.find(".//property[@name='plugin-21']/property[@name='icon-size']").get('value') == '18'
    assert x.find(".//property[@name='plugin-22']/property[@name='digital-format']").get('value') == '%H:%M'

    # Optional Netflix must remain optional; YouTube Kids or supervised
    # preference is retained by the .desktop file already in the child home.
    with tempfile.TemporaryDirectory() as second:
        h2 = pathlib.Path(second)
        cp.write_child_menu(h2, youtube=True, netflix=False)
        names = [v.text for v in ET.parse(h2/'.config/menus/parentpilot.menu').getroot().findall('./Include/Filename')]
        assert 'parentpilot-netflix.desktop' not in names
        assert 'parentpilot-youtube.desktop' in names

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
    # Actual launcher entries must have REAL newline characters, not literal
    # backslash-n sequences; otherwise XFCE shows generic/corrupt icons.
    for item in ['launcher-10/parentpilot-browser.desktop',
                 'launcher-11/thunar.desktop',
                 'launcher-12/parentpilot-youtube.desktop',
                 'launcher-13/parentpilot-netflix.desktop']:
        data = (home/'.config/xfce4/panel'/item).read_text()
        assert data.startswith('[Desktop Entry]\n'), (item, repr(data[:80]))
        assert '\nIcon=' in data, (item, repr(data))
        assert r'\n' not in data, (item, repr(data))
    thunar = (home/'.config/xfce4/panel/launcher-11/thunar.desktop').read_text()
    assert 'Exec=thunar\n' in thunar
    assert 'files.svg' in thunar
    browser = (home/'.local/share/applications/parentpilot-browser.desktop').read_text()
    assert 'Exec=true' in browser and 'browser.svg' in browser
    assert (home/'.config/autostart/parentpilot-panel-refresh.desktop').is_file()

    # Live corrections happen only in the child's own XFCE session, through
    # xfconf. They must not affect adult/user-modified panels.
    commands=cp.xfconf_commands_for_panel(home)
    assert len(commands) >= 8
    assert any('/panels/panel-1/plugin-ids' in c for c in commands)
    assert any('/plugins/plugin-1/custom-menu-file' in c for c in commands)
    assert any('/plugins/plugin-21/icon-size' in c and c[-1] == '18' for c in commands)
    assert any('/plugins/plugin-22/digital-format' in c and c[-1] == '%H:%M' for c in commands)
    assert all(c[0] == 'xfconf-query' and c[2] == 'xfce4-panel' for c in commands)
    with patch.object(cp.os, 'geteuid', return_value=1000), \
         patch.object(cp.os, 'getuid', return_value=1000), \
         patch.object(cp.pwd, 'getpwuid', return_value=SimpleNamespace(pw_dir=str(home), pw_gid=1000)), \
         patch.object(cp.shutil, 'which', return_value='/usr/bin/xfconf-query'), \
         patch.dict(cp.os.environ, {'DISPLAY':':10',
                                   'DBUS_SESSION_BUS_ADDRESS':'unix:path=/tmp/test-bus'}):
        calls=[]
        def run_fake(cmd, **kwargs):
            calls.append(cmd)
            return SimpleNamespace(returncode=0)
        assert cp.apply_session_panel(home=home, runner=run_fake)
        assert len(calls) == len(commands)
        assert cp.apply_session_panel(home=home, runner=run_fake)
        assert len(calls) == len(commands), 'Already-applied layouts must not flap at login'

    with tempfile.TemporaryDirectory() as unrelated:
        assert cp.xfconf_commands_for_panel(pathlib.Path(unrelated)) == []

import py_compile
for py in [R/'parentpilot/wizard.py',R/'parentpilot/preflight.py',R/'parentpilot/setup_root.py',R.parent/'desktop/max_desktop.py',R.parent/'desktop/parentpilot_lock_media.py',R.parent/'desktop/screen_view.py']:
    py_compile.compile(str(py),doraise=True)
print('PASS: six-character child password, compact panel layout/repair, and Python syntax; no system users modified')
