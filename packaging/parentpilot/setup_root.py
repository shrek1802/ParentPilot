#!/usr/bin/python3
"""Privileged one-time ParentPilot setup. Only run through PolicyKit on XFCE/X11.

Never run from package postinst: package installation and child provisioning are separate,
so upgrades cannot accidentally recreate users or reset screen-time state.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import pwd
import grp
import re
import secrets
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
sys.path.insert(0, str(Path(__file__).resolve().parent))
from preflight import report as host_report
from child_panel import write_child_panel

APP = Path('/usr/lib/parentpilot/desktop')
TARGET = Path('/opt/max-family-control')
CFG = Path('/etc/max-family-control')
STATE = Path('/var/lib/max-family-control')
POLICY = Path('/etc/chromium/policies/managed/90-parentpilot-family.json')
SERVICE = 'max-family-control.service'
USERNAME = re.compile(r'^[a-z][a-z0-9_-]{0,30}$')


def run(*args, input=None):
    # PolicyKit may reset PATH; Debian keeps system administration commands
    # under /usr/sbin (not available on all default user paths).
    command = str(args[0])
    if '/' not in command and not shutil.which(command):
        for directory in ('/usr/sbin', '/sbin', '/usr/bin', '/bin'):
            candidate = Path(directory)/command
            if candidate.is_file():
                command = str(candidate)
                break
    return subprocess.run((command, *args[1:]), input=input, text=True, check=True, capture_output=True)


def validate(data):
    if not isinstance(data, dict): raise ValueError('Invalid setup information.')
    name = str(data.get('child_name', '')).strip()
    user = str(data.get('child_user', '')).strip()
    password = str(data.get('child_password', ''))
    pin = str(data.get('parent_pin', ''))
    if not 1 <= len(name) <= 32 or any(ord(c) < 32 or c in '\r\n' for c in name):
        raise ValueError('Child name must be 1–32 characters.')
    if not USERNAME.fullmatch(user) or user in ('root','maxfamily','nobody'):
        raise ValueError('Invalid child Linux username.')
    if len(password) < 6 or len(password) > 128 or '\n' in password or ':' in password:
        raise ValueError('Child account password must be 6–128 characters without a colon.')
    if not re.fullmatch(r'[0-9]{6}', pin) or pin in ('000000','111111','123456'):
        raise ValueError('Choose a less obvious six-digit parent PIN.')
    if data.get('youtube') not in ('kids','supervised'):
        raise ValueError('Select the YouTube Kids or supervised option.')
    for flag in ('netflix','autologin','family_filter','screen_view'):
        if type(data.get(flag)) is not bool: raise ValueError(f'Invalid {flag} option.')
    return name, user, password, pin


def check_host(user, autologin=False, family_filter=False):
    status = host_report()
    if status['errors']:
        raise RuntimeError('Laptop compatibility check failed: ' + ' '.join(status['errors']))
    if not Path('/run/systemd/system').exists():
        raise RuntimeError('Systemd services are not available. Start a normal Linux desktop session and try again.')
    if autologin and not status['lightdm']:
        raise RuntimeError('Automatic child login needs LightDM. Go Back and turn off auto login, or set up LightDM first.')
    if family_filter and POLICY.exists():
        raise RuntimeError('Chromium family policy already exists. Go Back and turn off filtering; existing policies will never be overwritten.')
    if (CFG / 'config.json').exists() or (TARGET / 'control_server.py').exists():
        raise RuntimeError('An existing ParentPilot/Max Family Control installation was found. This fresh installer will not reset existing settings.')
    if (Path('/home') / user).exists():
        raise RuntimeError('This child home already exists. Choose a different username.')
    try: pwd.getpwnam(user)
    except KeyError: pass
    else: raise RuntimeError('That Linux user already exists. Choose another username.')
    if not all(APP.joinpath(f).is_file() for f in ('max_desktop.py', 'parentpilot_lock_media.py', 'screen_view.py')):
        raise RuntimeError('ParentPilot files are incomplete. Reinstall the .deb.')
    return status


def make_desktop(path, name, exec_cmd, icon, comment):
    path.write_text('[Desktop Entry]\nType=Application\n'
                    f'Name={name}\nComment={comment}\nExec={exec_cmd}\n'
                    f'Icon={icon}\nTerminal=false\nCategories=Network;AudioVideo;\n'
                    'StartupNotify=true\n', encoding='utf8')
    path.chmod(0o644)



def child_desktop(user, name, youtube, netflix):
    pw=pwd.getpwnam(user)
    home=Path(pw.pw_dir)
    appl=home/'.local/share/applications'; appl.mkdir(parents=True,exist_ok=True)
    icons=home/'.local/share/icons'; icons.mkdir(parents=True,exist_ok=True)
    for icon in ('browser.svg','files.svg','youtube.svg','netflix.svg'):
        shutil.copy2(Path('/usr/lib/parentpilot/icons')/icon,icons/f'parentpilot-{icon}')
    browser=shutil.which('chromium') or shutil.which('chromium-browser')
    if not browser: raise RuntimeError('Chromium is missing. Please install it and retry.')
    make_desktop(appl/'parentpilot-browser.desktop','Family Chromium',f'{browser} --no-first-run',str(Path('/usr/lib/parentpilot/icons/browser.svg')),'Chromium browser with available family policies')
    if youtube == 'kids': url='https://www.youtubekids.com/'; title='YouTube Kids'
    else: url='https://www.youtube.com/'; title='YouTube (Supervised)'
    make_desktop(appl/'parentpilot-youtube.desktop',title,f'{browser} --no-first-run --app={url}',str(Path('/usr/lib/parentpilot/icons/youtube.svg')),'A parent must configure the age/maturity setting online')
    if netflix:
        make_desktop(appl/'parentpilot-netflix.desktop','Netflix', f'{browser} --no-first-run --app=https://www.netflix.com/',str(Path('/usr/lib/parentpilot/icons/netflix.svg')),'Use a Kids profile and lock adult profiles. DRM requires Widevine.')
    autostart=home/'.config/autostart'; autostart.mkdir(parents=True,exist_ok=True)
    (autostart/'parentpilot.desktop').write_text('[Desktop Entry]\nType=Application\nName=ParentPilot Timer\nExec=/usr/bin/python3 -B /opt/max-family-control/max_desktop_supervisor.py\nTerminal=false\nOnlyShowIn=XFCE;\nX-GNOME-Autostart-enabled=true\n',encoding='utf8')
    # App hiding is per-child and cosmetic: scripts/keyboard shortcuts still exist.
    hidden=('xfce4-terminal.desktop','org.xfce.Terminal.desktop','mintinstall.desktop',
            'synaptic.desktop','software-properties-gtk.desktop','org.gnome.Software.desktop',
            'timeshift-gtk.desktop','org.xfce.terminal.desktop','gdebi.desktop',
            'firefox.desktop','google-chrome.desktop','brave-browser.desktop',
            'gnome-terminal.desktop','org.xfce.appfinder.desktop')
    for item in hidden:
        dest=appl/item
        if not dest.exists(): dest.write_text('[Desktop Entry]\nType=Application\nName=Hidden from child menu\nHidden=true\n',encoding='utf8')
    # Child-specific preferred browser, without changing parent account defaults.
    mime=home/'.config/mimeapps.list';mime.parent.mkdir(parents=True,exist_ok=True)
    mime.write_text('[Default Applications]\ntext/html=parentpilot-browser.desktop\nx-scheme-handler/http=parentpilot-browser.desktop\nx-scheme-handler/https=parentpilot-browser.desktop\n',encoding='utf8')
    write_child_panel(home,pw.pw_gid,netflix=netflix)
    # Fresh child home only: recursive chown touches no existing parent's files.
    run('chown','-R',f'{user}:{grp.getgrgid(pw.pw_gid).gr_name}',str(home/'.local'),str(home/'.config'))


def configure_chromium(mode, family_filter):
    if not family_filter: return
    POLICY.parent.mkdir(parents=True,exist_ok=True)
    if POLICY.exists(): raise RuntimeError('A ParentPilot Chromium policy already exists; refusing to overwrite.')
    data={'ForceGoogleSafeSearch':True, 'ForceYouTubeRestrict':2,
          'DnsOverHttpsMode':'secure','DnsOverHttpsTemplates':'https://family.cloudflare-dns.com/dns-query',
          'IncognitoModeAvailability':1,'BrowserGuestModeEnabled':False,
          'BrowserAddPersonEnabled':False}
    if mode=='kids': data['URLBlocklist']=['youtube.com','youtu.be']
    POLICY.write_text(json.dumps(data,indent=2)+'\n',encoding='utf8')
    POLICY.chmod(0o644)


def install_timer(user, name, parent_pin, autologin, screen_view=False):
    if not run('getent','passwd',user).stdout: raise RuntimeError('Child account not found.')
    run('id','-u',user)
    if not shutil.which('setfacl'): raise RuntimeError('acl tools unavailable.')
    if not Path('/usr/sbin/nologin').exists(): raise RuntimeError('System nologin shell unavailable.')
    try: pwd.getpwnam('maxfamily')
    except KeyError: run('useradd','--system','--user-group','--home-dir',str(STATE),'--shell','/usr/sbin/nologin','--no-create-home','maxfamily')
    TARGET.mkdir(mode=0o755,parents=True,exist_ok=True)
    (TARGET/'assets').mkdir(mode=0o755,exist_ok=True)
    for name_file in ('control_server.py','max_desktop.py','max_desktop_supervisor.py','parentpilot_lock_media.py','admin.py','screen_view.py','parentpilot_screen_parent.js'):
        shutil.copy2(APP/name_file,TARGET/name_file)
        (TARGET/name_file).chmod(0o644)
    for pic in ('parentpilot-icon-128.png','parentpilot-icon-64.png','parentpilot-icon.png'):
        shutil.copy2(APP/'assets'/pic,TARGET/'assets'/pic)
    CFG.mkdir(mode=0o750,parents=True,exist_ok=True)
    STATE.mkdir(mode=0o700,parents=True,exist_ok=True)
    cfg_group=grp.getgrnam('maxfamily').gr_gid
    os.chown(CFG,0,cfg_group)
    os.chown(STATE,pwd.getpwnam('maxfamily').pw_uid,cfg_group)
    sys.path.insert(0,str(TARGET))
    from control_server import atomic_write, hash_password, clean_state
    atomic_write(CFG/'config.json', {'child':user, 'display_name':name,
                                     'password':hash_password(parent_pin),
                                     'screen_view_enabled':screen_view})
    os.chown(CFG/'config.json',0,cfg_group); (CFG/'config.json').chmod(0o640)
    token=CFG/'desktop-token'; token.write_text(secrets.token_hex(32)+'\n',encoding='ascii')
    os.chown(token,0,cfg_group);token.chmod(0o640)
    run('setfacl','-m',f'u:{user}:--x',str(CFG))
    run('setfacl','-m',f'u:{user}:r--',str(token))
    run('openssl','req','-x509','-newkey','rsa:3072','-sha256','-nodes','-days','825',
        '-keyout',str(CFG/'server.key'),'-out',str(CFG/'server.crt'),
        '-subj','/CN=ParentPilot','-addext','subjectAltName=DNS:localhost,IP:127.0.0.1')
    os.chown(CFG/'server.key',0,cfg_group);(CFG/'server.key').chmod(0o640)
    (CFG/'server.crt').chmod(0o644)
    atomic_write(STATE/'state.json',clean_state())
    os.chown(STATE/'state.json',pwd.getpwnam('maxfamily').pw_uid,cfg_group)
    unit=Path('/etc/systemd/system/max-family-control.service')
    unit.write_text('''[Unit]
Description=ParentPilot Screen Time Control
After=network.target
Wants=network.target
[Service]
Type=simple
User=maxfamily
Group=maxfamily
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=/usr/bin/python3 -B /opt/max-family-control/control_server.py
WorkingDirectory=/opt/max-family-control
Restart=on-failure
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/max-family-control
ProtectKernelTunables=true
ProtectControlGroups=true
CapabilityBoundingSet=
LockPersonality=true
RestrictSUIDSGID=true
[Install]
WantedBy=multi-user.target
''',encoding='utf8')
    unit.chmod(0o644)
    run('systemctl','daemon-reload')
    run('systemctl','enable','--now',SERVICE)
    avahi=Path('/etc/avahi/services/family-control.service')
    avahi.parent.mkdir(parents=True,exist_ok=True)
    if not avahi.exists():
        avahi.write_text('''<?xml version="1.0" standalone='no'?>
<!DOCTYPE service-group SYSTEM "avahi-service.dtd">
<service-group><name replace-wildcards="yes">ParentPilot (%h)</name>
<service><type>_maxfamily._tcp</type><port>8743</port></service></service-group>
''',encoding='utf8')
    run('systemctl','enable','--now','avahi-daemon.service')
    if autologin:
        directory=Path('/etc/lightdm/lightdm.conf.d');directory.mkdir(parents=True,exist_ok=True)
        (directory/'99-parentpilot-autologin.conf').write_text(f'[Seat:*]\nautologin-user={user}\nautologin-user-timeout=0\nautologin-session=xfce\n',encoding='utf8')
    # A marker is created ONLY after the new DEB-controlled first-run setup
    # succeeds. It prevents the updater from ever overwriting a customised
    # or legacy ParentPilot laptop by accident.
    marker=CFG/'.parentpilot-deb-managed'
    marker.write_text('ParentPilot-DEB-managed-v1\n',encoding='ascii')
    marker.chmod(0o600)


def main():
    if len(sys.argv)==2 and sys.argv[1]=='--preflight':
        print(json.dumps(host_report(), indent=2));return
    if len(sys.argv)==2 and sys.argv[1]=='--validate-json':
        validate(json.load(sys.stdin));print('VALIDATION PASS');return
    if os.geteuid()!=0 or len(sys.argv)!=2 or sys.argv[1]!='--from-wizard':
        raise RuntimeError('Run the branded ParentPilot Setup wizard from the applications menu.')
    raw=sys.stdin.read(8193)
    if len(raw)>8192: raise ValueError('Setup payload too large.')
    data=json.loads(raw)
    name,user,password,pin=validate(data)
    check_host(user, autologin=data['autologin'], family_filter=data['family_filter'])
    # Preserve parent account; never change the adult's password or session.
    run('adduser','--disabled-password','--gecos',f'{name},,,',user)
    run('chpasswd',input=f'{user}:{password}\n')
    child_desktop(user,name,data['youtube'],data['netflix'])
    configure_chromium(data['youtube'],data['family_filter'])
    install_timer(user,name,pin,data['autologin'],data['screen_view'])
    print('SUCCESS: ParentPilot is installed for '+name+'.\n')
    print('The child desktop will be ready next time they sign in. Parental controls are paused until approved.')
    print('Browse to https://<laptop-ip>:8743 from your phone, or use the ParentPilot Android app on the same Wi-Fi.')
    print('IMPORTANT: Select the real maturity settings within YouTube and Netflix; shortcuts alone do not guarantee child-safe content.')


if __name__=='__main__':
    try:main()
    except (ValueError, RuntimeError, subprocess.CalledProcessError, OSError, KeyError) as exc:
        print('SETUP STOPPED: '+str(exc),file=sys.stderr)
        if isinstance(exc,subprocess.CalledProcessError) and exc.stderr:
            print(exc.stderr[-1500:],file=sys.stderr)
        sys.exit(1)
