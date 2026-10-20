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
    # Simulate Preview 8-13's mistaken hidden programs: newer versions must
    # restore regular educational Linux apps but still hide other browsers.
    from parentpilot import child_panel as cp
    apps=home/'.local/share/applications'
    for name in ('xfce4-terminal.desktop', 'mintinstall.desktop', 'org.xfce.appfinder.desktop'):
        (apps/name).write_text(cp.OLD_HIDDEN_ENTRY)
    (apps/'my-art-project.desktop').write_text(
        '[Desktop Entry]\nType=Application\nName=My Drawing\n'
        'Exec=true\nCategories=Graphics;\n')
    (apps/'firefox.desktop').write_text(cp.OLD_HIDDEN_ENTRY)
    # Simulate last preview's allowlisted child menu and its duplicate XDG
    # Files/Logout items; upgrade must replace it with the normal XFCE menu.
    old_menu = home/'.config/menus/parentpilot.menu'
    old_menu.parent.mkdir(parents=True, exist_ok=True)
    old_root = ET.Element('Menu')
    ET.SubElement(old_root, 'Name').text = 'ParentPilot'
    incl = ET.SubElement(old_root, 'Include')
    for name in ['parentpilot-browser.desktop', 'parentpilot-files.desktop',
                 'parentpilot-youtube.desktop', 'parentpilot-logout.desktop']:
        ET.SubElement(incl, 'Filename').text = name
    ET.ElementTree(old_root).write(old_menu, encoding='utf-8')
    (apps/'parentpilot-files.desktop').write_text(
        '[Desktop Entry]\nType=Application\nName=Files\n'
        'Exec=thunar\nIcon=' + str(cp.ICONS[11]) +
        '\nTerminal=false\nCategories=Utility;\n')
    (apps/'parentpilot-logout.desktop').write_text(
        '[Desktop Entry]\nType=Application\nName=Log out\n'
        'Exec=xfce4-session-logout\nIcon=system-log-out\n'
        'Terminal=false\nCategories=System;\n')
    m.write_child_panel(home,1000,netflix=True)
    x=ET.parse(home/'.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-panel.xml')
    assert x.getroot().attrib['name']=='xfce4-panel'
    assert all('value' not in elem.attrib for elem in x.findall(".//property[@type='array']")+x.findall(".//property[@type='empty']"))
    assert list((home/'.config/xfce4/panel').glob('launcher-*/**/*.desktop'))

    # This is a regular learning computer, not a whitelisted-only kiosk.
    # Keep default XFCE menus, normal installed apps and VLC media player.
    from parentpilot.child_panel import ICONS
    expected = {
        10: 'parentpilot-browser.desktop',
        11: 'thunar.desktop',
        12: 'parentpilot-youtube.desktop',
        13: 'parentpilot-netflix.desktop',
        14: 'parentpilot-vlc.desktop',
    }
    for number, name in expected.items():
        active = home/'.config/xfce4/panel'/f'launcher-{number}'/name
        assert active.is_file(), (number, name)
        raw = active.read_text()
        assert raw.startswith('[Desktop Entry]\n'), (number, repr(raw[:100]))
        assert '\nExec=' in raw and '\nIcon=' in raw
        assert r'\n' not in raw
        if number == 14:
            assert 'Exec=vlc %U\n' in raw
            assert 'Icon=vlc\n' in raw
        elif number in (10, 11, 12, 13):
            assert 'Icon=' + str(ICONS[number]) in raw
    for name in ('browser.svg', 'files.svg', 'youtube.svg', 'netflix.svg'):
        image = ET.parse(R/'parentpilot'/name).getroot()
        assert image.tag.endswith('svg'), name

    # All non-browser programs are accessible again in the normal app menu.
    for name in ('xfce4-terminal.desktop', 'mintinstall.desktop',
                 'org.xfce.appfinder.desktop'):
        assert not (apps/name).exists(), name
    assert (apps/'my-art-project.desktop').is_file(), 'User app must survive'
    assert (apps/'firefox.desktop').read_text() == cp.OLD_HIDDEN_ENTRY
    for name in ('google-chrome.desktop', 'brave-browser.desktop'):
        assert 'Hidden=true' in (apps/name).read_text(), name
    assert (apps/'parentpilot-vlc.desktop').is_file()

    app_menu = x.find(".//property[@name='plugin-1']")
    assert app_menu.get('value') == 'whiskermenu', 'The original Linux Mint menu is Whisker, not basic applicationsmenu'
    assert app_menu.find("./property[@name='custom-menu-file']") is None
    profile = home/'.config/xfce4/panel/whiskermenu-1.rc'
    assert profile.is_file()
    assert 'parentpilot-browser.desktop' in profile.read_text()
    assert 'show-button-title=false' in profile.read_text()
    # A Mint artwork profile, where available, is preferred over a custom one.
    with tempfile.TemporaryDirectory() as other:
        original = pathlib.Path(other)/'mint-original.rc'
        original.write_text('button-icon=linuxmint-logo-ring-symbolic\n'
                            'show-button-title=false\n'
                            'favorites=firefox.desktop,thunar.desktop,vlc.desktop\n'
                            'menu-width=600\n')
        new_home = pathlib.Path(other)/'child'
        new_path = cp.ensure_mint_whisker_settings(new_home, templates=(original,))
        config = new_path.read_text()
        assert 'menu-width=600' in config  # Unmodified native Mint sizing
        assert 'firefox.desktop' not in config
        assert 'parentpilot-browser.desktop' in config
        # Never clobber a child-customised Whisker profile during updates.
        new_path.write_text('button-icon=my-own-icon\nshow-button-title=true\n')
        assert cp.ensure_mint_whisker_settings(new_home, templates=(original,)) == new_path
        assert new_path.read_text() == 'button-icon=my-own-icon\nshow-button-title=true\n'
    assert not (home/'.config/menus/parentpilot.menu').exists()
    assert not (apps/'parentpilot-files.desktop').exists()
    assert not (apps/'parentpilot-logout.desktop').exists()
    assert x.find(".//property[@name='panel-1']/property[@name='size']").get('value') == '44'
    assert x.find(".//property[@name='panel-1']/property[@name='icon-size']").get('value') == '32'
    assert x.find(".//property[@name='plugin-17']").get('value') == 'tasklist'
    assert x.find(".//property[@name='plugin-21']/property[@name='icon-size']").get('value') == '20'
    assert x.find(".//property[@name='plugin-22']/property[@name='digital-format']").get('value') == '%H:%M'

    # Netflix is optional and the child's existing YouTube choice is kept.
    with tempfile.TemporaryDirectory() as second:
        h2 = pathlib.Path(second)
        p=h2/'.local/share/applications'
        p.mkdir(parents=True)
        for name in ('parentpilot-browser.desktop','parentpilot-youtube.desktop'):
            (p/name).write_text('[Desktop Entry]\nType=Application\nName=Test\nExec=true\n')
        cp.write_child_panel(h2, 1000, youtube=True, netflix=False)
        assert not (p/'parentpilot-netflix.desktop').exists()
        assert (h2/'.config/xfce4/panel/launcher-14/parentpilot-vlc.desktop').is_file()
        panel = ET.parse(h2/'.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-panel.xml')
        ids2 = [int(q.get('value')) for q in panel.findall(".//property[@name='plugin-ids']/value")]
        assert 13 not in ids2 and 14 in ids2

    # App launchers are centred, and systray/clock remain on the right.
    positions=[p.attrib.get('name') for p in x.findall(".//property[@name='plugin-ids']/value")]
    plugins=x.find(".//property[@name='plugin-ids']")
    assert plugins is not None
    ids=[int(v.attrib['value']) for v in plugins.findall('value')]
    assert ids[:3] == [1, 17, 18]
    assert ids.index(18) < ids.index(10) < ids.index(14) < ids.index(19) < ids.index(21)
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
                 'launcher-13/parentpilot-netflix.desktop',
                 'launcher-14/parentpilot-vlc.desktop']:
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
    assert any('/plugins/plugin-1' == c[4] and c[-1] == 'whiskermenu' for c in commands)
    assert any('/plugins/plugin-17' in c and 'tasklist' in c for c in commands)
    assert any('/plugins/plugin-14/items' in c for c in commands)
    assert any('/plugins/plugin-21/icon-size' in c and c[-1] == '20' for c in commands)
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
        assert len(calls) == len(commands) + 1
        assert calls[-1] == ['xfce4-panel', '--restart'], 'Whisker plugin must be reloaded once'
        assert cp.apply_session_panel(home=home, runner=run_fake)
        assert len(calls) == len(commands) + 1, 'Already-applied layouts must not flap at login'

    with tempfile.TemporaryDirectory() as unrelated:
        assert cp.xfconf_commands_for_panel(pathlib.Path(unrelated)) == []

import py_compile
for py in [R/'parentpilot/wizard.py',R/'parentpilot/preflight.py',R/'parentpilot/setup_root.py',R.parent/'desktop/max_desktop.py',R.parent/'desktop/parentpilot_lock_media.py',R.parent/'desktop/screen_view.py']:
    py_compile.compile(str(py),doraise=True)
print('PASS: six-character child password, compact panel layout/repair, and Python syntax; no system users modified')
