#!/usr/bin/env python3
"""ParentPilot 0.3 developer preview - local timer service and authenticated parent panel.
Copyright (c) 2026 - MIT licensed. Uses only Python standard library.
"""
import base64
import datetime as dt
import hashlib
import hmac
import html
import json
import os
import re
from pathlib import Path
import secrets
import ssl
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie
from urllib.parse import parse_qs, urlsplit

CONFIG_DIR = Path(os.environ.get('MAXFC_CONFIG_DIR', '/etc/max-family-control'))
DATA_DIR = Path(os.environ.get('MAXFC_DATA_DIR', '/var/lib/max-family-control'))
PORT = int(os.environ.get('MAXFC_PORT', '8743'))
LOCAL_USERS = {'127.0.0.1', '::1'}
CONFIG_FILE = CONFIG_DIR / 'config.json'
STATE_FILE = DATA_DIR / 'state.json'
DESKTOP_TOKEN_FILE = CONFIG_DIR / 'desktop-token'
MAX_SCREEN_BYTES = 4 * 1024 * 1024  # bounded, in-memory, one parent-requested JPEG
SCREEN_REQUEST_INTERVAL = 45  # prevents automated rapid-fire captures
SCREEN_PREVIEW_SECONDS = 120  # unsaved preview expires after two minutes
MAX_SAVED_PICTURES = 20
SAVED_PICTURES_DIR = DATA_DIR / 'saved-screens'
SAVED_ID = re.compile(r'^[0-9]{8}T[0-9]{6}Z-[a-f0-9]{20}[.]jpg$')
VIEWER_JS = Path(__file__).resolve().parent / 'parentpilot_screen_parent.js'


def new_day():
    return dt.date.today().isoformat()


def clean_state():
    return {'day': new_day(), 'allowance_seconds': 0, 'used_seconds': 0.0, 'paused': True, 'unlimited': False}


def atomic_write(file, value):
    file = Path(file)
    file.parent.mkdir(parents=True, exist_ok=True)
    tmp = file.with_suffix(file.suffix + '.tmp')
    with open(tmp, 'w', encoding='utf8') as fp:
        json.dump(value, fp, sort_keys=True, indent=2)
        fp.flush()
        os.fsync(fp.fileno())
    os.replace(tmp, file)
    os.chmod(file, 0o600)


def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    hashed = hashlib.pbkdf2_hmac('sha256', password.encode('utf8'), salt, 320000)
    return {'salt': base64.b64encode(salt).decode('ascii'), 'hash': base64.b64encode(hashed).decode('ascii')}


def verify_password(password, data):
    try:
        salt = base64.b64decode(data['salt'], validate=True)
        expected = base64.b64decode(data['hash'], validate=True)
        supplied = hashlib.pbkdf2_hmac('sha256', password.encode('utf8'), salt, 320000)
        return hmac.compare_digest(expected, supplied)
    except (ValueError, KeyError, TypeError):
        return False


def session_is_max(target_user):
    """Count usage only while Max owns active local seat. Conservatively false on errors."""
    try:
        r = subprocess.run(['loginctl', 'show-seat', 'seat0', '-p', 'ActiveSession', '--value'], capture_output=True, text=True, timeout=3)
        sid = r.stdout.strip()
        if sid and sid not in ('n/a', '-'):  # systemd versions may use either
            n = subprocess.run(['loginctl', 'show-session', sid, '-p', 'Name', '--value'], capture_output=True, text=True, timeout=3)
            if n.returncode == 0:
                return n.stdout.strip() == target_user
        r = subprocess.run(['loginctl', 'list-sessions', '--no-legend'], capture_output=True, text=True, timeout=3)
        if r.returncode:
            return False
        for line in r.stdout.splitlines():
            parts = line.strip().split()
            if len(parts) < 3 or parts[2] != target_user:
                continue
            sid = parts[0]
            p = subprocess.run(['loginctl', 'show-session', sid, '-p', 'Active', '--value'], capture_output=True, text=True, timeout=3)
            if p.stdout.strip().lower() == 'yes':
                return True
    except (OSError, subprocess.TimeoutExpired):
        return False
    return False


class Control:
    def __init__(self):
        self.cfg = json.loads(CONFIG_FILE.read_text())
        self.lock = threading.RLock()
        self.state = self._read_state()
        self.sessions = {}  # id => [expiry_monotonic, csrf]
        self.failures = {}  # ip => [fail_count, blocked_until]
        self.global_failures = [0, 0.0]  # per-process PIN brute-force throttle
        self.desktop_token = DESKTOP_TOKEN_FILE.read_text(encoding='ascii').strip()
        if len(self.desktop_token) < 40:
            raise RuntimeError('Desktop auth token missing or invalid. Restore backup or re-run the v0.2 update.')
        self.last_tick = time.monotonic()
        self.active = False
        # A parent must opt in at fresh setup, then authenticate each browser session.
        # Each screen request is visible on the child's desktop before capture.
        # No automatic recording, continuous streaming, or hidden capture.
        # Only a signed-in parent may save a picture to private storage.
        self.screen_request = ''
        self.screen_requested_at = 0.0
        self.screen_status = 'idle'
        self.screen_image = None
        self.screen_image_until = 0.0

    def request_screen(self):
        if self.cfg.get('screen_view_enabled') is not True:
            raise ValueError('Screen viewing has not been enabled on this laptop.')
        with self.lock:
            now = time.monotonic()
            if self.screen_requested_at and now - self.screen_requested_at < SCREEN_REQUEST_INTERVAL:
                raise ValueError('Please wait at least 45 seconds between screen pictures.')
            self.screen_request = secrets.token_urlsafe(24)
            self.screen_requested_at = now
            self.screen_status = 'pending'
            self.screen_image = None
            self.screen_image_until = 0.0

    def screen_state(self, desktop=False):
        with self.lock:
            now = time.monotonic()
            if self.screen_status == 'pending' and now - self.screen_requested_at > 30:
                self.screen_status = 'expired'
                self.screen_request = ''
            if self.screen_image is not None and now > self.screen_image_until:
                self.screen_image = None
                self.screen_status = 'expired'
                self.screen_request = ''
            status = self.screen_status if self.cfg.get('screen_view_enabled') is True else 'disabled'
            result = {'screen_enabled': self.cfg.get('screen_view_enabled') is True,
                      'screen_status': status}
            if desktop and status == 'pending':
                result['screen_request'] = self.screen_request
            return result

    def complete_screen(self, request_id, image=None):
        with self.lock:
            if self.screen_state()['screen_status'] != 'pending':
                return False
            if not request_id or not hmac.compare_digest(request_id, self.screen_request):
                return False
            if image is None:
                self.screen_status = 'failed'
                self.screen_request = ''
                return True
            if not (128 <= len(image) <= MAX_SCREEN_BYTES and
                    image[:3] == b'\xff\xd8\xff' and image[-2:] == b'\xff\xd9'):
                return False
            self.screen_image = image
            self.screen_image_until = time.monotonic() + SCREEN_PREVIEW_SECONDS
            self.screen_status = 'ready'
            self.screen_request = ''
            return True

    def get_screen(self):
        with self.lock:
            return self.screen_image if self.screen_state()['screen_status'] == 'ready' else None


    def _gallery_directory(self, create=False):
        """Private gallery; refuse symlinked storage."""
        directory = SAVED_PICTURES_DIR
        if directory.is_symlink():
            raise ValueError('Unsafe saved-picture directory.')
        if create:
            directory.mkdir(mode=0o700, exist_ok=True)
            directory.chmod(0o700)
        if not directory.exists():
            return None
        if not directory.is_dir():
            raise ValueError('Invalid saved-picture directory.')
        return directory

    def saved_pictures(self):
        with self.lock:
            directory = self._gallery_directory()
            if directory is None:
                return []
            pictures = []
            for file in directory.iterdir():
                if not SAVED_ID.fullmatch(file.name) or file.is_symlink() or not file.is_file():
                    continue
                stamp = dt.datetime.fromtimestamp(file.stat().st_mtime)
                pictures.append({'id': file.name, 'time': stamp.strftime('%d %b %Y, %H:%M')})
            return sorted(pictures, key=lambda item: item['id'], reverse=True)

    def save_picture(self):
        """A parent explicitly saves a current image; never archive automatically."""
        if self.cfg.get('screen_view_enabled') is not True:
            raise ValueError('Screen viewing is disabled.')
        with self.lock:
            jpeg = self.get_screen()
            if jpeg is None:
                raise ValueError('The picture has expired. Take another before saving.')
            if len(self.saved_pictures()) >= MAX_SAVED_PICTURES:
                raise ValueError('The gallery is full (20 pictures). Delete an older one first.')
            directory = self._gallery_directory(create=True)
            filename = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + secrets.token_hex(10) + '.jpg'
            file = directory / filename
            try:
                with file.open('xb') as stream:
                    file.chmod(0o600)
                    stream.write(jpeg)
                    stream.flush()
                    os.fsync(stream.fileno())
            except Exception:
                file.unlink(missing_ok=True)
                raise
            return filename

    def get_saved_picture(self, filename):
        if not SAVED_ID.fullmatch(filename) or self.cfg.get('screen_view_enabled') is not True:
            return None
        with self.lock:
            directory = self._gallery_directory()
            if directory is None:
                return None
            file = directory / filename
            if file.is_symlink() or not file.is_file() or file.stat().st_size > MAX_SCREEN_BYTES:
                return None
            return file.read_bytes()

    def delete_saved_picture(self, filename):
        if self.cfg.get('screen_view_enabled') is not True or not SAVED_ID.fullmatch(filename):
            raise ValueError('Invalid saved picture.')
        with self.lock:
            directory = self._gallery_directory()
            if directory is None:
                raise ValueError('Picture not found.')
            file = directory / filename
            if file.is_symlink() or not file.is_file():
                raise ValueError('Picture not found.')
            file.unlink()

    def _read_state(self):
        try:
            data = json.loads(STATE_FILE.read_text())
            if data.get('day') == new_day():
                clean = clean_state()
                for k in clean:
                    if k in data and type(data[k]) in (type(clean[k]), int, float):
                        clean[k] = data[k]
                clean['allowance_seconds'] = max(0, min(86400, int(clean['allowance_seconds'])))
                clean['used_seconds'] = max(0, min(86400, float(clean['used_seconds'])))
                return clean
        except (ValueError, OSError, TypeError):
            pass
        return clean_state()

    def _fresh_day(self):
        if self.state['day'] != new_day():
            self.state = clean_state()
            atomic_write(STATE_FILE, self.state)

    def remaining(self):
        return max(0, int(self.state['allowance_seconds'] - self.state['used_seconds']))

    def granted(self):
        return not self.state['paused'] and (self.state['unlimited'] or self.remaining() > 0)

    def snapshot(self, desktop=False):
        with self.lock:
            self._fresh_day()
            return {
                **self.screen_state(desktop=desktop),
                'day': self.state['day'],
                'allowance_seconds': self.state['allowance_seconds'],
                'used_seconds': int(self.state['used_seconds']),
                'remaining_seconds': self.remaining(),
                'paused': self.state['paused'],
                'unlimited': self.state['unlimited'],
                'allowed': self.granted(),
                'max_active': self.active,
                'child': self.cfg['child'],
                'display_name': self.cfg.get('display_name', self.cfg['child'].capitalize()),
            }

    def tick_loop(self):
        previous_save = time.monotonic()
        while True:
            time.sleep(1)
            now = time.monotonic()
            elapsed = max(0, min(now - self.last_tick, 5))
            self.last_tick = now
            active = session_is_max(self.cfg['child'])
            with self.lock:
                self._fresh_day()
                self.active = active
                # Purge ephemeral images on schedule even if no parent reconnects.
                self.screen_state()
                if active and self.granted() and not self.state['unlimited']:
                    self.state['used_seconds'] = min(86400, self.state['used_seconds'] + elapsed)
                if now - previous_save >= 5:
                    atomic_write(STATE_FILE, self.state)
                    previous_save = now
                # Expire old sessions.
                for token, val in list(self.sessions.items()):
                    if val[0] < now:
                        self.sessions.pop(token, None)

    def change(self, action, minutes=0):
        with self.lock:
            self._fresh_day()
            if action == 'set':
                self.state['allowance_seconds'] = min(86400, int(self.state['used_seconds']) + minutes * 60)
                self.state['paused'] = False
                self.state['unlimited'] = False
            elif action == 'add':
                self.state['allowance_seconds'] = min(86400, self.state['allowance_seconds'] + minutes * 60)
                self.state['paused'] = False
                self.state['unlimited'] = False
            elif action == 'pause':
                self.state['paused'] = True
            elif action == 'resume':
                if self.remaining() <= 0 and not self.state['unlimited']:
                    raise ValueError('Set or add time before resuming.')
                self.state['paused'] = False
            elif action == 'unlimited':
                self.state['unlimited'] = True
                self.state['paused'] = False
            elif action == 'managed':
                self.state['unlimited'] = False
                self.state['paused'] = True
            elif action == 'end':
                self.state['allowance_seconds'] = int(self.state['used_seconds'])
                self.state['unlimited'] = False
                self.state['paused'] = True
            else:
                raise ValueError('Unknown action')
            atomic_write(STATE_FILE, self.state)
            return self.snapshot()


CSS = '''
:root{color-scheme:dark;--bg:#0a1122;--card:#19243a;--text:#f6f9ff;--muted:#a8bad3;--accent:#63d9d0;--border:#31415c;--shadow:#04081766}
*{box-sizing:border-box}
body{background:radial-gradient(circle at 90% 0%,#234767 0,#101d35 35%,#080f20 100%);min-height:100vh;color:var(--text);font:16px/1.48 system-ui,-apple-system,Segoe UI,sans-serif;margin:0}
main{max-width:650px;margin:0 auto;padding:22px 15px 70px}
header{display:flex;align-items:center;justify-content:space-between;gap:14px;margin-bottom:14px}
h1{font-size:1.42rem;letter-spacing:-.025em;margin:0}h2{font-size:1.12rem;margin:0 0 8px}p{margin:5px 0 15px}
.small{font-size:.88rem;color:var(--muted)}.brand{display:flex;align-items:center;gap:10px}
.brand-icon{width:52px;height:52px;object-fit:contain;filter:drop-shadow(0 3px 8px #0b132560)}
.card{background:linear-gradient(140deg,#1a2a44,#17233a);border:1px solid var(--border);border-radius:19px;padding:21px;margin:15px 0;box-shadow:0 9px 26px var(--shadow)}
.card.primary{background:linear-gradient(135deg,#1a3a57,#172940);border-color:#45718e}
.eyebrow{font-size:.8rem;color:#b4c5dc;text-transform:uppercase;letter-spacing:.11em;font-weight:700}
.stat{font-weight:800;font-size:clamp(2.7rem,9vw,4rem);letter-spacing:-.06em;line-height:1.3}
.status{font-weight:750;font-size:1.05rem;color:var(--accent)}
label{font-weight:650;display:block;margin:11px 0 6px}
input{display:block;background:#0c1930;border:1px solid #506583;border-radius:11px;color:#fff;width:100%;font-size:1.13rem;padding:13px}
input:focus,button:focus-visible{outline:3px solid #83e3de;outline-offset:2px}
button{background:#139aab;color:#fff;font:700 1rem system-ui,sans-serif;border:0;border-radius:12px;padding:13px 13px;cursor:pointer;min-height:50px;touch-action:manipulation}
button:active{filter:brightness(1.2)}button.alt{background:#344964}button.danger{background:#a84561}button.wide{width:100%}
.actions{display:grid;grid-template-columns:1fr 1fr;gap:11px}.actions form{margin:0}.actions button{width:100%}
.row{display:flex;align-items:flex-end;gap:10px}.row input{flex:1;min-width:0}.row button{flex:none}
.msg{background:#432f3e;border:1px solid #c0788b;border-radius:9px;padding:10px;margin:10px 0}.ok{color:#79e5d3}
.progress{height:11px;background:#344762;border-radius:30px;overflow:hidden;margin:12px 0}.bar{height:11px;background:linear-gradient(90deg,#39dbbc,#63c7f7);border-radius:30px}

.screen-preview{display:block;width:100%;max-width:100%;border-radius:12px;cursor:zoom-in;margin:10px 0}
.saved-picture{display:flex;gap:12px;padding:12px 0;border-bottom:1px solid var(--border);align-items:flex-start}
.saved-picture img{width:125px;max-width:38vw;border-radius:8px;cursor:zoom-in}
.saved-picture-detail{flex:1;min-width:0}.saved-picture-detail form{display:inline-block;margin-left:12px}
.saved-picture-detail a{color:#9be9e2}.saved-picture-detail button{min-height:36px;padding:7px 12px;font-size:.9rem}
#screen-modal{width:min(96vw,1100px);height:92vh;max-height:92vh;padding:0;border:1px solid #60789e;border-radius:14px;background:#101d35;color:white}
#screen-modal::backdrop{background:#020617ed}
#screen-modal-toolbar{display:flex;align-items:center;gap:9px;justify-content:center;padding:10px;position:sticky;top:0;background:#19243a;z-index:2}
#screen-modal-toolbar button{min-height:42px}
#screen-modal-area{overflow:auto;width:100%;height:calc(100% - 70px);touch-action:pan-x pan-y}
#screen-modal-image{width:100%;height:auto;max-width:none;display:block}
[hidden]{display:none!important}
@media(max-width:400px){.actions{grid-template-columns:1fr}.row{flex-wrap:wrap}.row button{width:100%}.stat{font-size:2.65rem}}
'''


def esc(s):
    return html.escape(str(s), quote=True)


def clock(seconds):
    seconds = max(0, int(seconds))
    if seconds <= 60:
        return f'{seconds // 60}:{seconds % 60:02d}'
    h, m = divmod((seconds + 59) // 60, 60)
    return f'{h}h {m:02d}m' if h else f'{m} min'


def login_html(error='', child_name='Child'):
    return f'''<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width,initial-scale=1"><meta charset="utf-8"><title>ParentPilot</title><link rel="icon" type="image/png" href="/assets/parentpilot-icon.png"><style>{CSS}</style></head>
<body><main><header><div class="brand"><img class="brand-icon" src="/assets/parentpilot-icon.png" alt="ParentPilot"><h1>ParentPilot</h1></div></header><section class="card"><h2>Parent sign in</h2><p class="small">Enter your 6-digit parent PIN. Your child does not need it.</p>
{f'<div class="msg">{esc(error)}</div>' if error else ''}
<form action="/login" method="post"><label for="password">Parent PIN</label><input id="password" type="password" name="password" required inputmode="numeric" pattern="[0-9]{{6}}" maxlength="6" autocomplete="off"><p></p><button class="wide">Open controls</button></form></section></main></body></html>'''


def dashboard_html(s, csrf, flash=''):
    child_name = esc(s.get('display_name', s['child'].capitalize()))
    mode = 'Unlimited' if s['unlimited'] else ('Paused' if s['paused'] else ('Time expired' if not s['allowed'] else 'Available'))
    rem = 'Unlimited today' if s['unlimited'] else clock(s['remaining_seconds'])
    used = clock(s['used_seconds'])
    total = s['allowance_seconds']
    pct = max(0, min(100, int(s['used_seconds']/total*100))) if total > 0 else 0
    def form(action, label, css='alt'):
        return f'<form action="/action" method="post"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="action" value="{action}"><button class="{css}">{label}</button></form>'

    screen_card = ''
    screen_modal = ''
    screen_script = ''
    if s.get('screen_enabled'):
        condition = s.get('screen_status', 'idle')
        ready = condition == 'ready'
        hidden = '' if ready else ' hidden'
        initial_img = ' src="/screen.jpg"' if ready else ''
        gallery_entries = []
        for entry in s.get('saved_pictures', []):
            picture_id = esc(entry['id'])
            picture_url = f'/saved-screen/{picture_id}'
            when = esc(entry['time'])
            gallery_entries.append(
                f'<div class="saved-picture"><a href="{picture_url}" class="open-screen-viewer" '
                f'data-screen-src="{picture_url}" aria-label="Enlarge saved picture">'
                f'<img src="{picture_url}" alt="Saved picture from {when}" loading="lazy"></a>'
                f'<div class="saved-picture-detail"><strong>{when}</strong><p>'
                f'<a href="{picture_url}?download=1">Download</a>'
                f'<form action="/action" method="post" data-delete-screen>'
                f'<input type="hidden" name="csrf" value="{esc(csrf)}">'
                f'<input type="hidden" name="action" value="delete-saved-screen">'
                f'<input type="hidden" name="saved_id" value="{picture_id}">'
                f'<button class="danger" type="submit">Delete</button></form></p></div></div>')
        gallery_html = ''.join(gallery_entries) or '<p class="small">No saved pictures yet.</p>'
        gallery_count = len(s.get('saved_pictures', []))
        screen_card = (f'<section class="card" id="screen-card"><h2>View child screen</h2>'
                       f'<p class="small">A parent can request one screen picture. '
                       f'The child sees a notification before capture. Unsaved pictures '
                       f'expire after two minutes. Saved pictures stay until you delete them; '
                       f'nothing is saved automatically.</p>'
                       f'<p>Picture status: <strong id="screen-status">{esc(condition)}</strong></p>'
                       f'{form("request-screen", "Take one screen picture")}'
                       f'<div id="screen-preview-container"{hidden}><p>'
                       f'<a href="/screen.jpg" class="open-screen-viewer" '
                       f'id="screen-preview-link" data-screen-src="/screen.jpg">'
                       f'<img id="screen-preview" class="screen-preview"{initial_img} '
                       f'alt="Tap to enlarge this screen picture"></a>'
                       f'<small>Tap to enlarge and zoom.</small></p></div>'
                       f'<form id="save-screen-form" action="/action" method="post"{hidden}>'
                       f'<input type="hidden" name="csrf" value="{esc(csrf)}">'
                       f'<input type="hidden" name="action" value="save-screen">'
                       f'<button type="submit">Save this picture</button></form>'
                       f'<hr style="border:0;border-top:1px solid var(--border);margin:24px 0">'
                       f'<h3>Saved pictures ({gallery_count}/{MAX_SAVED_PICTURES})</h3>'
                       f'<p class="small">Only manually saved pictures are kept privately '
                       f'on this laptop. Download them to your phone or delete them here.</p>'
                       f'{gallery_html}</section>')
        screen_modal = ("""<dialog id="screen-modal" aria-label="Enlarged screen picture">
<div id="screen-modal-toolbar"><button type="button" id="screen-close">Close</button>
<button type="button" id="screen-zoom-out" class="alt">−</button>
<button type="button" id="screen-zoom-in" class="alt">+</button>
<button type="button" id="screen-zoom-fit" class="alt">Fit</button></div>
<div id="screen-modal-area"><img id="screen-modal-image" alt="Enlarged screen picture"></div></dialog>""")
        screen_script = '<script src="/assets/parentpilot-screen-parent.js" defer></script>'
    return f'''<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width,initial-scale=1"><meta charset="utf-8"><title>ParentPilot</title><link rel="icon" type="image/png" href="/assets/parentpilot-icon.png"><style>{CSS}</style>{screen_script}</head>
<body><main><header><div class="brand"><img class="brand-icon" src="/assets/parentpilot-icon.png" alt="ParentPilot"><h1>ParentPilot</h1></div>{form('logout','Sign out')}</header>
{f'<div class="msg">{esc(flash)}</div>' if flash else ''}
<section class="card primary"><div class="eyebrow">{child_name}'s laptop · {esc(s['day'])}</div><div class="status">{esc(mode)}</div><div class="stat">{esc(rem)}</div><div class="progress"><div class="bar" style="width:{pct}%"></div></div><p class="small">Used today: {esc(used)} · <span id="presence">{ 'Child is using the laptop' if s['max_active'] else 'Child is not at the laptop'}</span></p></section>
<section class="card"><h2>Set today's time</h2><p class="small">Replaces the remaining time with the amount you choose.</p>
<form action="/action" method="post"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="action" value="set"><div class="row"><div><label for="setmin">Minutes</label><input id="setmin" type="number" name="minutes" min="1" max="720" value="60" required></div><button>Set time</button></div></form></section>
<section class="card"><h2>Add extra time</h2><div class="actions">{form('add15','+15 minutes','')}{form('add30','+30 minutes','')}{form('add60','+1 hour','')}{form('add120','+2 hours','')}</div>
<form action="/action" method="post"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="action" value="add"><div class="row"><div><label for="bonus">Custom minutes</label><input id="bonus" name="minutes" type="number" min="1" max="720" value="20" required></div><button>Add time</button></div></form></section>
<section class="card"><h2>Access controls</h2><p class="small">Pause immediately hides the child's desktop; Resume restores access while your child has time remaining.</p><div class="actions">{form('pause','Pause laptop','danger')}{form('resume','Resume laptop','')}{form('unlimited','Unlimited today')}{form('managed','Managed time')}</div><p></p>{form('end','End time for today','danger')}</section>
{screen_card}{screen_modal}
<p class="small">For phone use, bookmark this page or Add to Home Screen. Controls work over Wi-Fi or a private VPN such as Tailscale. Your child's screen is restored without closing open apps, but this first version is not tamper-proof against a technically skilled child.</p></main></body></html>'''


class Handler(BaseHTTPRequestHandler):
    server_version = 'ParentPilot/0.3'

    def log_message(self, fmt, *args):
        # Do not log secrets or request bodies.
        print(f'[{self.address_string()}] {fmt % args}', flush=True)

    @property
    def ctl(self):
        return self.server.control

    def send_bytes(self, data, status=200, content_type='text/html; charset=utf-8', cookie=None):
        payload = data.encode('utf8') if isinstance(data, str) else data
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Content-Security-Policy', "default-src 'none'; style-src 'unsafe-inline'; img-src 'self'; script-src 'self'; connect-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        if cookie: self.send_header('Set-Cookie', cookie)
        self.end_headers()
        self.wfile.write(payload)

    def redirect(self, where='/', cookie=None):
        self.send_response(303)
        self.send_header('Location', where)
        self.send_header('Cache-Control', 'no-store')
        if cookie: self.send_header('Set-Cookie', cookie)
        self.send_header('Content-Length', '0')
        self.end_headers()

    def get_session(self):
        header = self.headers.get('Cookie', '')
        if len(header) > 4096:
            return None
        try:
            cookie = SimpleCookie(); cookie.load(header)
            token = cookie.get('maxfc_session')
            if not token: return None
            with self.ctl.lock:
                val = self.ctl.sessions.get(token.value)
                return (token.value, val) if val and val[0] > time.monotonic() else None
        except Exception:
            return None

    def read_form(self):
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 8192:
                return None
            body = self.rfile.read(length)
            return {k: v[0] for k, v in parse_qs(body.decode('utf8'), max_num_fields=12).items() if v}
        except (ValueError, UnicodeError):
            return None

    def desktop_authorized(self):
        # A proxied remote request can appear to originate at 127.0.0.1.
        # Require the separate, root-owned local desktop token as well.
        supplied = self.headers.get('X-MaxFC-Desktop-Token', '')
        return (self.client_address[0] in LOCAL_USERS and
                len(supplied) <= 256 and
                hmac.compare_digest(supplied, self.ctl.desktop_token))

    def do_GET(self):
        if self.path == '/assets/parentpilot-icon.png':
            logo = Path(__file__).resolve().parent / 'assets' / 'parentpilot-icon.png'
            try:
                self.send_bytes(logo.read_bytes(), content_type='image/png')
            except OSError:
                self.send_bytes('Asset unavailable', 404)
            return

        if self.path == '/assets/parentpilot-screen-parent.js':
            if not self.get_session():
                self.send_bytes('Forbidden', 403); return
            try:
                self.send_bytes(VIEWER_JS.read_bytes(), content_type='application/javascript; charset=utf-8')
            except OSError:
                self.send_bytes('Viewer unavailable', 404)
            return
        if self.path == '/api/parent/v1/status':
            # Stable native-Android endpoint. The desktop's local token is NEVER
            # sufficient to access the parent dashboard: require signed-in parent.
            session = self.get_session()
            if not session:
                self.send_bytes('Forbidden', 403); return
            summary = self.ctl.snapshot()
            summary['csrf'] = session[1][1]
            summary['saved_pictures'] = (
                self.ctl.saved_pictures() if summary.get('screen_enabled') else []
            )
            self.send_bytes(json.dumps(summary), content_type='application/json')
            return
        if self.path == '/api/parent-screen':
            if not self.get_session():
                self.send_bytes('Forbidden', 403); return
            self.send_bytes(json.dumps(self.ctl.screen_state()), content_type='application/json'); return
        route = urlsplit(self.path).path
        if route.startswith('/saved-screen/'):
            if not self.get_session():
                self.send_bytes('Forbidden', 403); return
            filename = route[len('/saved-screen/'):]
            picture = self.ctl.get_saved_picture(filename)
            if picture is None:
                self.send_bytes('Saved picture not found', 404); return
            if urlsplit(self.path).query == 'download=1':
                self.send_response(200)
                self.send_header('Content-Type', 'image/jpeg')
                self.send_header('Content-Length', str(len(picture)))
                self.send_header('Content-Disposition', 'attachment; filename="' + filename + '"')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.send_header('X-Frame-Options', 'DENY')
                self.send_header('Referrer-Policy', 'no-referrer')
                self.end_headers()
                self.wfile.write(picture)
            else:
                self.send_bytes(picture, content_type='image/jpeg')
            return
        if self.path == '/api/state':
            if not self.desktop_authorized():
                self.send_bytes('Forbidden', 403); return
            self.send_bytes(json.dumps(self.ctl.snapshot(desktop=True)), content_type='application/json'); return
        if self.path == '/screen.jpg':
            auth = self.get_session()
            if not auth:
                self.send_bytes('Authentication required', 403); return
            picture = self.ctl.get_screen()
            if picture is None:
                self.send_bytes('Picture unavailable or expired', 404); return
            self.send_bytes(picture, content_type='image/jpeg'); return
        if self.path != '/':
            self.send_bytes('Not found', 404); return
        auth = self.get_session()
        if not auth:
            self.send_bytes(login_html(child_name=self.ctl.cfg.get('display_name', 'Child'))); return
        self.send_bytes(dashboard_html({**self.ctl.snapshot(), 'saved_pictures': self.ctl.saved_pictures()}, auth[1][1]))

    def password_ok(self, value):
        ip = self.client_address[0]
        with self.ctl.lock:
            count, until = self.ctl.failures.get(ip, (0, 0))
            if time.monotonic() < until or time.monotonic() < self.ctl.global_failures[1]:
                return False
        ok = verify_password(value, self.ctl.cfg['password'])
        with self.ctl.lock:
            if ok:
                self.ctl.failures.pop(ip, None)
                self.ctl.global_failures = [0, 0.0]
            else:
                count += 1
                global_count = self.ctl.global_failures[0] + 1
                # 5 bad guesses trigger a five-minute lockout, including across proxies.
                self.ctl.failures[ip] = (count, time.monotonic() + 300 if count >= 5 else 0)
                self.ctl.global_failures = [global_count, time.monotonic() + 300 if global_count >= 5 else 0]
        return ok

    def do_POST(self):
        if self.path == '/api/screen/upload':
            if not self.desktop_authorized():
                self.send_bytes('Forbidden', 403); return
            try:
                size = int(self.headers.get('Content-Length', '0'))
            except ValueError:
                size = 0
            if not 128 <= size <= MAX_SCREEN_BYTES or self.headers.get('Content-Type') != 'image/jpeg':
                self.send_bytes('Invalid picture', 400); return
            request_id = self.headers.get('X-ParentPilot-Screen-Request', '')
            if len(request_id) > 128:
                self.send_bytes('Invalid request', 400); return
            image = self.rfile.read(size)
            if not self.ctl.complete_screen(request_id, image):
                self.send_bytes('Request expired, invalid, or not enabled', 409); return
            self.send_bytes('OK', content_type='text/plain'); return
        if self.path not in ('/login', '/action', '/local-grant', '/api/screen/fail'):
            self.send_bytes('Not found', 404); return
        if not self.headers.get('Content-Type','').lower().startswith('application/x-www-form-urlencoded'):
            self.send_bytes('Invalid content type', 415); return
        fields = self.read_form()
        if fields is None:
            self.send_bytes('Invalid form', 400); return
        if self.path == '/api/screen/fail':
            if not self.desktop_authorized():
                self.send_bytes('Forbidden', 403); return
            request_id = fields.get('request', '')
            if len(request_id) > 128 or not self.ctl.complete_screen(request_id):
                self.send_bytes('Request expired or invalid', 409); return
            self.send_bytes('OK', content_type='text/plain'); return
        if self.path == '/login':
            if not self.password_ok(fields.get('password','')):
                self.send_bytes(login_html('Incorrect PIN or temporarily rate-limited.', self.ctl.cfg.get('display_name', 'Child')), 403); return
            token = secrets.token_urlsafe(36)
            csrf = secrets.token_urlsafe(24)
            with self.ctl.lock:
                self.ctl.sessions[token] = (time.monotonic() + 1800, csrf)
            self.redirect('/', f'maxfc_session={token}; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age=1800')
            return
        if self.path == '/local-grant':
            if not self.desktop_authorized():
                self.send_bytes('Forbidden', 403); return
            if not self.password_ok(fields.get('password','')):
                self.send_bytes(json.dumps({'ok':False,'error':'Incorrect password or temporarily rate-limited.'}),403,'application/json'); return
            try:
                minutes = int(fields.get('minutes','0'))
                if not 1 <= minutes <= 720: raise ValueError('Enter 1–720 minutes.')
                result = self.ctl.change('add', minutes)
                self.send_bytes(json.dumps({'ok':True,'remaining_seconds':result['remaining_seconds']}),content_type='application/json')
            except (ValueError, TypeError) as ex:
                self.send_bytes(json.dumps({'ok':False,'error':str(ex)}),400,'application/json')
            return
        auth = self.get_session()
        if not auth or not hmac.compare_digest(fields.get('csrf',''), auth[1][1]):
            self.send_bytes('Authentication required', 403); return
        action = fields.get('action','')
        if action == 'logout':
            with self.ctl.lock:
                self.ctl.sessions.pop(auth[0], None)
            self.redirect('/', 'maxfc_session=; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age=0'); return
        try:
            if action.startswith('add') and action[3:].isdigit():
                minutes = int(action[3:])
                action = 'add'
            else:
                minutes = int(fields.get('minutes','0') or '0')
            if action in ('set', 'add') and not (1 <= minutes <= 720):
                raise ValueError('Enter 1–720 minutes.')
            if action == 'request-screen':
                self.ctl.request_screen()
            elif action == 'save-screen':
                self.ctl.save_picture()
            elif action == 'delete-saved-screen':
                self.ctl.delete_saved_picture(fields.get('saved_id', ''))
            else:
                self.ctl.change(action, minutes)
            self.redirect('/#screen-card' if action in ('request-screen', 'save-screen', 'delete-saved-screen') else '/')
        except (ValueError, TypeError) as exc:
            self.send_bytes(dashboard_html({**self.ctl.snapshot(), 'saved_pictures': self.ctl.saved_pictures()}, auth[1][1], str(exc)), 400)
        except OSError:
            self.send_bytes('Unable to access private picture storage.', 500)


def main():
    control = Control()
    srv = ThreadingHTTPServer(('0.0.0.0', PORT), Handler)
    srv.control = control
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(str(CONFIG_DIR/'server.crt'), str(CONFIG_DIR/'server.key'))
    srv.socket = context.wrap_socket(srv.socket, server_side=True)
    threading.Thread(target=control.tick_loop, daemon=True).start()
    print(f'Max Family Control listening on HTTPS port {PORT}', flush=True)
    srv.serve_forever(poll_interval=0.5)


if __name__ == '__main__':
    main()
