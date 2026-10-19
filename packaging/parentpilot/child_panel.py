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
    prop(prop(plugins,'plugin-18','string','separator'),'expand','bool','true')
    prop(prop(plugins,'plugin-19','string','separator'),'expand','bool','true')
    for number in launcher_ids:
        p=prop(plugins,f'plugin-{number}','string','launcher')
        array(p,'items','string',[labels[number]])
    # Status icons and clock are kept in their own natural-size area.
    prop(plugins,'plugin-21','string','systray')
    prop(plugins,'plugin-22','string','clock')
    ET.indent(root,space='  ')
    ET.ElementTree(root).write(conf/'xfce4-panel.xml',encoding='utf-8',xml_declaration=True)
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


if __name__ == '__main__':
    if sys.argv[1:] != ['--repair']:
        raise SystemExit('Usage: child_panel.py --repair')
    repair_child_panel()
