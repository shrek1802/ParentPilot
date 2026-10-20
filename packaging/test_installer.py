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
assert 'install_timer(user,name,pin,data[\'autologin\'],True)' in p.read_text(), (
    'Fresh setup must enable on-demand parent pictures irrespective of old flag')
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
    assert x.find(".//property[@name='panel-1']/property[@name='size']").get('value') == '40'
    assert x.find(".//property[@name='panel-1']/property[@name='icon-size']").get('value') == '22'
    assert x.find(".//property[@name='plugin-17']").get('value') == 'tasklist'
    assert x.find(".//property[@name='plugin-21']/property[@name='icon-size']").get('value') == '20'
    assert x.find(".//property[@name='plugin-22']/property[@name='digital-format']").get('value') == '%H:%M'
    # Power Manager is a native XFCE plugin, not an unverified script or a
    # modified adult desktop. It remains beside the status tray and clock.
    assert x.find(".//property[@name='plugin-23']").get('value') == 'power-manager-plugin'

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
    assert ids[-3:] == [21, 23, 22], 'Status tray, battery and clock must be on the right'
    for key in ('plugin-18','plugin-19'):
        spacer=x.find(f".//property[@name='{key}']/property[@name='expand']")
        assert spacer is not None and spacer.attrib['value'] == 'true'
    # Upgrade must leave a family's extra pinned Kodi launcher exactly where
    # they put it, including its plugin ID and custom launcher file.
    from parentpilot import child_panel as cp
    assert cp.existing_parentpilot_panel(home)
    panel_path=home/'.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-panel.xml'
    original=ET.parse(panel_path)
    saved_root=original.getroot()
    plugin_list=saved_root.find(".//property[@name='panel-1']/property[@name='plugin-ids']")
    items=plugin_list.findall('value')
    # Insert extra user-created launcher before the existing right separator.
    insertion=next(j for j,p in enumerate(items) if p.get('value') == '19')
    plugin_list.insert(insertion, ET.Element('value',{'type':'int','value':'50'}))
    plugins_node=saved_root.find(".//property[@name='plugins']")
    custom=ET.SubElement(plugins_node,'property',{'name':'plugin-50','type':'string','value':'launcher'})
    ET.SubElement(custom,'property',{'name':'items','type':'array'})
    pinned=home/'.config/xfce4/panel/launcher-50'
    pinned.mkdir(parents=True)
    (pinned/'kodi.desktop').write_text('[Desktop Entry]\nType=Application\nName=Kodi\nExec=kodi\n')
    original.write(panel_path,encoding='utf-8',xml_declaration=True)
    before=panel_path.read_bytes()
    from unittest.mock import patch
    from types import SimpleNamespace
    recorded=[]
    current={
        '/panels/panel-1/size':'44',
        '/panels/panel-1/icon-size':'32'
    }
    def run_xfconf(args, **kwargs):
        recorded.append(args)
        assert args[:4]==['/usr/bin/xfconf-query','-c','xfce4-panel','-p']
        assert 'plugin-ids' not in ' '.join(args)
        assert 'launcher' not in ' '.join(args)
        key=args[4]
        if '-s' in args:
            current[key]=args[-1]
            return SimpleNamespace(returncode=0,stdout='',stderr='')
        return SimpleNamespace(returncode=0,stdout=current[key]+'\n',stderr='')
    with patch.object(cp.os, 'geteuid', return_value=1000), \
         patch.object(cp.os, 'getuid', return_value=1000), \
         patch.object(cp.pwd, 'getpwuid', return_value=SimpleNamespace(pw_dir=str(home),pw_gid=1000)):
        cp.repair_child_panel()
        assert cp.xfconf_commands_for_panel(home)==[
            ('/panels/panel-1/size','44','40'),
            ('/panels/panel-1/icon-size','32','22')]
        assert cp.apply_session_panel(home=home,runner=run_xfconf)
        assert current=={
            '/panels/panel-1/size':'40',
            '/panels/panel-1/icon-size':'22'}
        recorded_before=list(recorded)
        assert cp.apply_session_panel(home=home,runner=run_xfconf)
        assert recorded==recorded_before, 'One-time migration ran twice'
        assert (home/cp.PANEL_SIZE_MARKER).is_file()
        # A child's manually customised panel size is explicitly preserved.
        (home/cp.PANEL_SIZE_MARKER).unlink()
        current['/panels/panel-1/size']='58'
        current['/panels/panel-1/icon-size']='18'
        previous=len(recorded)
        assert cp.apply_session_panel(home=home,runner=run_xfconf)
        assert len(recorded)==previous+2
        assert current['/panels/panel-1/size']=='58'
        assert current['/panels/panel-1/icon-size']=='18'
        assert (home/cp.PANEL_SIZE_MARKER).is_file()
    assert panel_path.read_bytes() == before, 'An update overwrote custom pinned Kodi or panel XML'
    assert (pinned/'kodi.desktop').is_file()
    assert cp.xfconf_commands_for_panel(home) == [], 'One-time sizing change must stay complete'
    for item in ['launcher-10/parentpilot-browser.desktop',
                 'launcher-11/thunar.desktop',
                 'launcher-12/parentpilot-youtube.desktop',
                 'launcher-13/parentpilot-netflix.desktop',
                 'launcher-14/parentpilot-vlc.desktop']:
        data=(home/'.config/xfce4/panel'/item).read_text()
        assert data.startswith('[Desktop Entry]\n'),item
        assert '\nIcon=' in data,item
    assert (home/'.config/autostart/parentpilot-panel-refresh.desktop').is_file()
    with tempfile.TemporaryDirectory() as unrelated:
        assert cp.xfconf_commands_for_panel(pathlib.Path(unrelated)) == []


import py_compile
for py in [R/'parentpilot/wizard.py',R/'parentpilot/preflight.py',R/'parentpilot/setup_root.py',R.parent/'desktop/max_desktop.py',R.parent/'desktop/parentpilot_lock_media.py',R.parent/'desktop/screen_view.py']:
    py_compile.compile(str(py),doraise=True)
print('PASS: six-character child password, compact panel layout/repair, and Python syntax; no system users modified')
