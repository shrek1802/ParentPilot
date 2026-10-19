#!/usr/bin/python3
"""ParentPilot child-only XFCE panel layout.

The parent installer calls write_child_panel for a freshly created account.
During an upgrade, --repair runs as the *child Linux user*, never root,
and changes ONLY a recognised ParentPilot-generated XFCE panel. No other
parent/child files or XFCE account settings are reset.
"""
from pathlib import Path
import os
import pwd
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

def prop(parent, name, typ=None, value=None):
    attrs={'name':name}
    if typ is not None:
        attrs['type'] = typ
        # XFCE's xfconf serialisation omits value for array and empty nodes.
        if typ not in ('array', 'empty') and value is not None:
            attrs['value'] = str(value)
    return ET.SubElement(parent,'property',attrs)


def array(parent,name,typ,values):
    p=prop(parent,name,'array','')
    for v in values: ET.SubElement(p,'value',{'type':typ,'value':str(v)})
    return p


def write_child_panel(home, group, youtube=True, netflix=True):
    """Only for freshly created child homes. Single bottom XFCE panel with curated launchers.
    This customisation changes visible launchers, not access control or parent panel.
    """
    conf=home/'.config/xfce4/xfconf/xfce-perchannel-xml'
    conf.mkdir(parents=True,exist_ok=True)
    root=ET.Element('channel',{'name':'xfce4-panel','version':'1.0'})
    prop(root,'configver','int',2)
    panels=array(root,'panels','int',[1])
    panel=prop(panels,'panel-1','empty','')
    prop(panel,'position','string','p=10;x=0;y=0')
    prop(panel,'position-locked','bool','true')
    # Consistent compact 42px taskbar; launcher group is centred by two
    # expanding separators rather than being crushed against the menu.
    prop(panel,'size','uint',42)
    prop(panel,'length','uint',100)
    prop(panel,'length-adjust','bool','false')
    prop(panel,'autohide-behavior','uint',0)
    launcher_ids=[10,11]+([12] if youtube else [])+([13] if netflix else [])
    plugin_ids=[1,18,*launcher_ids,19,21,22]
    array(panel,'plugin-ids','int',plugin_ids)
    plugins=prop(root,'plugins','empty','')
    prop(prop(plugins,'plugin-1','string','applicationsmenu'),'show-button-title','bool','false')
    labels={10:'parentpilot-browser.desktop',11:'thunar.desktop',12:'parentpilot-youtube.desktop',13:'parentpilot-netflix.desktop'}
    # Separator 18 and 19 expand equally; the tray and clock retain space
    # on the right while the child app shortcuts form an uncluttered dock.
    for spacer_id in (18,19):
        spacer = prop(plugins, f'plugin-{spacer_id}', 'string', 'separator')
        prop(spacer, 'style', 'uint', 0)
        prop(spacer, 'expand', 'bool', 'true')
    for number in launcher_ids:
        p=prop(plugins,f'plugin-{number}','string','launcher')
        array(p,'items','string',[labels[number]])
    # Status icons and clock are kept in their own natural-size area.
    prop(plugins,'plugin-21','string','systray')
    prop(plugins,'plugin-22','string','clock')
    ET.indent(root,space='  ')
    ET.ElementTree(root).write(conf/'xfce4-panel.xml',encoding='utf-8',xml_declaration=True)
    # Reapply the curated dock through the active XFCE settings service on
    # the child's NEXT login. Updating the offline XML alone can be ignored
    # by a cached xfconfd process.
    startup = home/'.config/autostart'
    startup.mkdir(parents=True, exist_ok=True)
    (startup/'parentpilot-panel-refresh.desktop').write_text(
        '[Desktop Entry]\nType=Application\n'
        'Name=ParentPilot Panel Layout\n'
        'Exec=/usr/bin/python3 /usr/lib/parentpilot/child_panel.py --apply-session\n'
        'Terminal=false\nOnlyShowIn=XFCE;\n'
        'X-GNOME-Autostart-enabled=true\nNoDisplay=true\n',
        encoding='utf8')
    pdir=home/'.config/xfce4/panel'
    for number in launcher_ids:
        folder=pdir/f'launcher-{number}'; folder.mkdir(parents=True,exist_ok=True)
        source=home/'.local/share/applications'/labels[number]
        if number==11:
            (folder/'thunar.desktop').write_text('[Desktop Entry]\nType=Application\nName=Files\nExec=thunar\nIcon=system-file-manager\nTerminal=false\n',encoding='utf8')
        elif source.is_file(): shutil.copy2(source,folder/labels[number])



def existing_parentpilot_panel(home):
    """Return True only for our own existing panel, not a custom XFCE desktop."""
    home = Path(home)
    config = home / '.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-panel.xml'
    shortcut = home / '.config/xfce4/panel/launcher-10/parentpilot-browser.desktop'
    if config.is_symlink() or shortcut.is_symlink():
        return False
    if not config.is_file() or not shortcut.is_file():
        return False
    try:
        root = ET.parse(config).getroot()
        return (
            root.tag == 'channel' and root.get('name') == 'xfce4-panel'
            and root.find(".//property[@name='plugin-10']") is not None
            and 'parentpilot-browser.desktop' in shortcut.name
        )
    except (ET.ParseError, OSError):
        return False


def repair_child_panel():
    """Update the child-owned dock layout only after parent approved DEB upgrade."""
    if os.geteuid() == 0:
        raise RuntimeError('Child panel repair must not run as root.')
    user = pwd.getpwuid(os.getuid())
    home = Path(user.pw_dir)
    if not existing_parentpilot_panel(home):
        print('SKIPPED: existing panel is not recognisably ParentPilot-managed.')
        return
    app_dir = home / '.local/share/applications'
    youtube = (app_dir / 'parentpilot-youtube.desktop').is_file()
    netflix = (app_dir / 'parentpilot-netflix.desktop').is_file()
    write_child_panel(home, user.pw_gid, youtube=youtube, netflix=netflix)
    print('Child ParentPilot panel updated; existing account settings preserved.')


# XFCE saves its panel in xfconf, not just xfce4-panel.xml. A resident xfconfd
# process can keep the previous left-aligned layout after a package upgrade,
# or overwrite edited XML when the child next signs in. Apply layout once in
# the CHILD's own graphical session, through xfconf-query, after XFCE starts.
LAYOUT_REVISION = 'centre-shortcuts-v3'


def xfconf_commands_for_panel(home):
    """Pure commands for the known ParentPilot panel; never touch other users."""
    home = Path(home)
    if not existing_parentpilot_panel(home):
        return []
    xml_file = home / '.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-panel.xml'
    root = ET.parse(xml_file).getroot()
    values = root.findall(".//property[@name='panel-1']/property[@name='plugin-ids']/value")
    plugin_ids = [int(v.get('value')) for v in values]
    # The only supported template: menu, equal expanding left/right spacers,
    # curated app launchers, notification tray, and clock. Never mutate a
    # generic XFCE panel or make guesses about plugin identifiers.
    if (len(plugin_ids) < 7 or plugin_ids[:2] != [1, 18] or
            19 not in plugin_ids or plugin_ids[-2:] != [21, 22]):
        return []
    if plugin_ids.index(19) <= 2:
        return []
    query = 'xfconf-query'
    commands = []
    for plugin_id in (18, 19):
        commands.extend([
            [query, '-c', 'xfce4-panel', '-p', f'/plugins/plugin-{plugin_id}',
             '-n', '-t', 'string', '-s', 'separator'],
            [query, '-c', 'xfce4-panel', '-p', f'/plugins/plugin-{plugin_id}/style',
             '-n', '-t', 'uint', '-s', '0'],
            [query, '-c', 'xfce4-panel', '-p', f'/plugins/plugin-{plugin_id}/expand',
             '-n', '-t', 'bool', '-s', 'true'],
        ])
    # Reassert the plugin order after xfconf has recognised the separators.
    args = [query, '-c', 'xfce4-panel', '-p', '/panels/panel-1/plugin-ids',
            '-n', '-a']
    for plugin_id in plugin_ids:
        args.extend(['-t', 'int', '-s', str(plugin_id)])
    commands.append(args)
    return commands


def apply_session_panel(home=None, runner=subprocess.run):
    """Repair the live XFCE panel once per layout revision and child profile.

    Called only by the managed CHILD session autostart, using that session's
    DBus and xfconf. Never run as root, never restart the window manager, and
    never overwrite administrator panels. A failing command does not leave
    a success marker: the next login can retry.
    """
    if os.geteuid() == 0:
        raise RuntimeError('Refusing to manage a root XFCE panel.')
    user = pwd.getpwuid(os.getuid())
    user_home = Path(home or user.pw_dir)
    commands = xfconf_commands_for_panel(user_home)
    if not commands:
        print('SKIPPED: not a ParentPilot-managed child panel.')
        return False
    state = user_home / '.local/state/parentpilot'
    marker = state / ('panel-' + LAYOUT_REVISION + '.done')
    if marker.exists():
        return True
    if not shutil.which('xfconf-query'):
        print('DEFERRED: xfconf-query not available yet.')
        return False
    # A real graphical session is required; avoid accidentally writing to a
    # separate DBus service or another logged-in user's panel.
    if not os.environ.get('DISPLAY') or not os.environ.get('DBUS_SESSION_BUS_ADDRESS'):
        print('DEFERRED: XFCE session display or DBus is not ready.')
        return False
    for argv in commands:
        result = runner(argv, capture_output=True, text=True, timeout=8, check=False)
        if result.returncode != 0:
            print('DEFERRED: XFCE rejected a panel setting. Will retry at next login.')
            return False
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    marker.write_text(LAYOUT_REVISION + '\n', encoding='ascii')
    marker.chmod(0o600)
    print('ParentPilot dock centred through the active XFCE settings service.')
    return True


if __name__ == '__main__':
    if sys.argv[1:] == ['--repair']:
        repair_child_panel()
    elif sys.argv[1:] == ['--apply-session']:
        apply_session_panel()
    else:
        raise SystemExit('Usage: child_panel.py --repair | --apply-session')
