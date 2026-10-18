#!/usr/bin/env python3
"""ParentPilot v0.3 screen-time indicator and friendly access overlay for Linux Mint XFCE.
Best-effort graphical restriction. It is NOT a cryptographic or kernel-level kiosk.
"""
import json
from parentpilot_lock_media import LockGuard
from pathlib import Path
import ssl
import subprocess
import tkinter as tk
from tkinter import ttk
import urllib.error
import urllib.parse
import urllib.request

ENDPOINT = 'https://127.0.0.1:8743'
TOKEN_PATH = Path('/etc/max-family-control/desktop-token')

def desktop_headers():
    return {'X-MaxFC-Desktop-Token': TOKEN_PATH.read_text(encoding='ascii').strip()}
TLS = ssl._create_unverified_context()  # loopback, certificate is generated locally
BG, PANEL, WHITE, MUTED, ACCENT = '#0f172a', '#1e293b', '#f8fafc', '#bcccdc', '#38bdf8'


def request_state():
    req = urllib.request.Request(ENDPOINT + '/api/state', headers=desktop_headers())
    with urllib.request.urlopen(req, timeout=3, context=TLS) as resp:
        return json.loads(resp.read().decode('utf8'))


def send_grant(password, minutes):
    data = urllib.parse.urlencode({'password': password, 'minutes': str(minutes)}).encode('utf8')
    req = urllib.request.Request(ENDPOINT + '/local-grant', data=data, method='POST', headers={'Content-Type':'application/x-www-form-urlencoded', **desktop_headers()})
    try:
        with urllib.request.urlopen(req, timeout=6, context=TLS) as resp:
            return json.loads(resp.read().decode('utf8'))
    except urllib.error.HTTPError as exc:
        try:
            return json.loads(exc.read().decode('utf8'))
        except Exception:
            return {'ok':False, 'error':f'HTTP {exc.code}'}


def formatted(seconds):
    secs = max(0, int(seconds))
    if secs <= 60:
        return f'{secs // 60}:{secs % 60:02d}'
    minutes = (secs + 59) // 60
    hours, rem = divmod(minutes, 60)
    return f'{hours}h {rem:02d}m' if hours else f'{minutes} minutes'


class MaxUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title('ParentPilot')
        self.root.configure(bg=BG)
        self.overlay = None
        self.widget = None
        self.indicator = None
        self.remaining = 0
        self.last_allowed = False
        self.last_state = None
        self.offline = False
        self.guard = LockGuard()
        self.screen_notice = None
        self.seen_screen_requests = set()
        self.root.after(100, self.refresh)
        self.root.mainloop()

    def create_widget(self):
        self.widget = tk.Toplevel(self.root)
        self.widget.overrideredirect(True)
        self.widget.wm_attributes('-topmost', True)
        self.widget.configure(bg=BG, padx=14, pady=10)
        self.indicator = tk.Label(self.widget, text='', fg=WHITE, bg=BG, font=('Sans', 10, 'bold'))
        self.indicator.pack()
        self.widget.update_idletasks()
        width = 180; height = 44
        x = self.widget.winfo_screenwidth() - width - 20
        y = self.widget.winfo_screenheight() - height - 60
        self.widget.geometry(f'{width}x{height}+{x}+{y}')

    def hide_widget(self):
        if self.widget is not None:
            self.widget.destroy()
            self.widget = None
            self.indicator = None

    def create_overlay(self):
        self.overlay = tk.Toplevel(self.root)
        self.overlay.withdraw()  # Build controls offscreen first. One cover, no blank curtain.
        self.overlay.overrideredirect(True)
        self.overlay.title('ParentPilot — time is up')
        self.overlay.configure(bg=BG)
        self.overlay.geometry(f'{self.overlay.winfo_screenwidth()}x{self.overlay.winfo_screenheight()}+0+0')
        self.overlay.attributes('-topmost', True)
        self.overlay.protocol('WM_DELETE_WINDOW', lambda: None)
        # Single-window override-redirect overlays XFCE panels without a second mask.
        self.overlay.bind('<Escape>', lambda _: 'break')
        self.overlay.bind('<Alt-F4>', lambda _: 'break')

        base = tk.Frame(self.overlay, bg=BG)
        base.place(relx=.5, rely=.5, anchor='center', relwidth=.85)
        try:
            # PhotoImage handles PNG without requiring third-party image libraries.
            self.logo_image = tk.PhotoImage(file=str(Path(__file__).resolve().parent / 'assets' / 'parentpilot-icon-128.png'))
            tk.Label(base, image=self.logo_image, bg=BG).pack(pady=(0, 6))
        except (tk.TclError, OSError):
            self.logo_image = None
        tk.Label(base, text='PARENTPILOT', fg=ACCENT, bg=BG, font=('Sans', 13, 'bold')).pack(pady=(0, 12))
        self.title_label = tk.Label(base, text='Time to take a break', fg=WHITE, bg=BG, font=('Sans', 28, 'bold'))
        self.title_label.pack(pady=(0, 12))
        self.description = tk.Label(base, text='Ask Mum or Dad if you can have some more time.', fg=MUTED, bg=BG, font=('Sans', 14), wraplength=630)
        self.description.pack(pady=(0, 28))
        form = tk.Frame(base, bg=PANEL, padx=18, pady=18)
        form.pack(fill='x')
        tk.Label(form, text='Parents only — add time', fg=WHITE, bg=PANEL, font=('Sans', 13, 'bold')).pack(anchor='w', pady=(0, 9))
        tk.Label(form, text='Parent PIN (6 digits)', fg=MUTED, bg=PANEL, font=('Sans', 10)).pack(anchor='w')
        self.password = tk.Entry(form, show='•', font=('Sans', 13), width=16)
        self.password.pack(fill='x', pady=(4, 12))
        tk.Label(form, text='Extra minutes', fg=MUTED, bg=PANEL, font=('Sans', 10)).pack(anchor='w')
        self.minutes = tk.StringVar(value='30')
        ttk.Combobox(form, textvariable=self.minutes, values=['15','30','45','60','90','120'], state='normal', font=('Sans', 12)).pack(fill='x', pady=(4, 14))
        tk.Button(form, text='Add time and return to desktop', command=self.parent_grant, bg='#0284c7', fg=WHITE, activebackground='#0369a1', font=('Sans', 12, 'bold'), padx=14, pady=10, borderwidth=0).pack(fill='x')
        self.msg = tk.Label(form, text='', fg='#fca5a5', bg=PANEL, font=('Sans', 10), wraplength=540)
        self.msg.pack(pady=(8, 0))
        self.connection_warning = tk.Label(base, text='', fg='#fcd34d', bg=BG,
                                           font=('Sans', 10, 'bold'), wraplength=620)
        self.connection_warning.pack(pady=(10, 0))
        bottom = tk.Frame(base, bg=BG)
        bottom.pack(pady=(23, 0))
        tk.Button(bottom, text='Switch user', command=self.switch_user, bg='#334155', fg=WHITE, font=('Sans', 11), padx=12, pady=8, borderwidth=0).pack(side='left', padx=10)
        tk.Button(bottom, text='Shut down', command=self.shutdown, bg='#334155', fg=WHITE, font=('Sans', 11), padx=12, pady=8, borderwidth=0).pack(side='left', padx=10)
        self.overlay.deiconify()
        self.overlay.lift()
        # Focus PIN field once; avoid stealing focus on every timer refresh.
        self.overlay.after(150, lambda: self.password.focus_force() if self.password.winfo_exists() else None)

    def parent_grant(self):
        password = self.password.get()
        try:
            minutes = int(self.minutes.get())
        except ValueError:
            self.msg.configure(text='Enter the number of extra minutes.'); return
        if not (1 <= minutes <= 720):
            self.msg.configure(text='Choose between 1 and 720 minutes.'); return
        if len(password) != 6 or not password.isascii() or not password.isdigit():
            self.msg.configure(text='Please enter all six digits of the parent PIN.')
            self.password.focus_set()
            return
        try:
            result = send_grant(password, minutes)
            self.password.delete(0,'end')
            if result.get('ok'):
                self.msg.configure(text='Approved. Returning to your desktop.', fg='#86efac')
                self.root.after(500, self.refresh)
            else:
                self.msg.configure(text='PIN not accepted. After repeated wrong attempts, wait five minutes.')
                self.password.focus_set()
        except Exception:
            self.msg.configure(text='Cannot reach the local control service. Please ask a parent.')

    def switch_user(self):
        # This remains a normal user operation, no admin privilege needed.
        try:
            subprocess.Popen(['dm-tool', 'switch-to-greeter'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            self.msg.configure(text='Switch user is unavailable. Use Ctrl+Alt+F1 to reach the login screen.')

    def shutdown(self):
        try:
            subprocess.Popen(['xfce4-session-logout','--halt'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            self.msg.configure(text='Shut down from the system power menu instead.')

    def hide_overlay(self):
        self.guard.release()
        if self.overlay is not None:
            self.overlay.destroy()
            self.overlay = None

    def show_screen_notice(self, text):
        """Persistent child-visible notice before capture and during image availability."""
        if self.screen_notice is None or not self.screen_notice.winfo_exists():
            self.screen_notice = tk.Toplevel(self.root)
            self.screen_notice.overrideredirect(True)
            self.screen_notice.attributes('-topmost', True)
            self.screen_notice.configure(bg='#14532d', padx=14, pady=10)
            self.screen_notice_label = tk.Label(
                self.screen_notice, bg='#14532d', fg=WHITE,
                font=('Sans', 10, 'bold'), wraplength=460
            )
            self.screen_notice_label.pack()
        self.screen_notice_label.configure(text=text)
        self.screen_notice.geometry('+25+25')
        self.screen_notice.lift()
        self.screen_notice.update_idletasks()

    def hide_screen_notice(self, notice):
        if self.screen_notice is notice and notice.winfo_exists():
            notice.destroy()
            self.screen_notice = None

    def report_screen_failure(self, request_id):
        # Child-side operation uses the existing LOCAL desktop token.
        # A failed capture never silently retries or generates a fake image.
        try:
            body = urllib.parse.urlencode({'request': request_id}).encode('utf8')
            req = urllib.request.Request(
                ENDPOINT + '/api/screen/fail', data=body,
                headers={'Content-Type': 'application/x-www-form-urlencoded',
                         **desktop_headers()}
            )
            with urllib.request.urlopen(req, timeout=3, context=TLS):
                pass
        except (OSError, urllib.error.URLError):
            pass

    def share_one_screen(self, request_id):
        try:
            from screen_view import capture_jpeg
            picture = capture_jpeg()
            req = urllib.request.Request(
                ENDPOINT + '/api/screen/upload', data=picture, method='POST',
                headers={'Content-Type': 'image/jpeg',
                         'X-ParentPilot-Screen-Request': request_id,
                         **desktop_headers()}
            )
            with urllib.request.urlopen(req, timeout=8, context=TLS) as response:
                if response.status != 200:
                    raise RuntimeError('ParentPilot did not accept the preview.')
            self.show_screen_notice(
                'ParentPilot: your parent viewed a picture of this screen'
            )
        except Exception:
            self.report_screen_failure(request_id)
            self.show_screen_notice(
                'ParentPilot: your parent requested a screen picture, but it failed'
            )
        finally:
            notice = self.screen_notice
            if notice is not None and notice.winfo_exists():
                notice.after(30000, lambda: self.hide_screen_notice(notice))

    def parent_requested_screen(self, request_id):
        """The parent opted in during installation; show a notice, not an approval prompt."""
        if not request_id:
            return
        # Display a visible notice BEFORE taking the image; do not capture covertly.
        self.show_screen_notice(
            'ParentPilot: your parent is viewing one picture of this screen'
        )
        self.root.after(400, lambda: self.share_one_screen(request_id))

    def refresh(self):
        try:
            state = request_state()
            self.offline = False
        except Exception:
            state = None
            self.offline = True

        if state is None:
            # A single failed HTTPS poll must never remove an established lock.
            # If the timer service is genuinely down, the adult can still use
            # Switch user on the same overlay to repair it from their account.
            # Prior to ANY valid state we keep the previous recovery behaviour.
            if (self.overlay is not None or
                    (self.last_state is not None and not self.last_state.get('allowed', True))):
                self.hide_widget()
                if self.overlay is None: self.create_overlay()
                self.connection_warning.configure(
                    text='ParentPilot connection interrupted. Screen stays paused. '
                         'A parent can switch users to check the control service.')
                self.guard.enforce(self.overlay)
            else:
                self.hide_overlay()
                if self.widget is None: self.create_widget()
                self.indicator.configure(text='Parent control offline — ask a parent')
        elif state['allowed']:
            self.hide_overlay()
            if self.widget is None: self.create_widget()
            self.indicator.configure(text='Free time' if state['unlimited'] else f"Time left: {formatted(state['remaining_seconds'])}")
        else:
            self.hide_widget()
            if self.overlay is None: self.create_overlay()
            self.connection_warning.configure(text='')
            if state['paused']:
                self.title_label.configure(text='Laptop paused')
                self.description.configure(text='Mum or Dad can resume your time from their phone, or approve some more time here.')
            else:
                self.title_label.configure(text='Time to take a break')
                self.description.configure(text='Your time is up. Ask Mum or Dad if you can have some more time.')
            # The parent PIN controls are in THIS foreground window, not behind an extra mask.
            self.guard.enforce(self.overlay)
        if state is not None:
            self.last_state = state
        if state is not None and state.get('allowed') and state.get('screen_enabled'):
            request_id = state.get('screen_request', '')
            if request_id and request_id not in self.seen_screen_requests:
                self.seen_screen_requests.add(request_id)
                self.parent_requested_screen(request_id)
        # Refresh once per second during the final minute, otherwise every 2s.
        # Server is authoritative; the overlay appears when it reports expiry.
        short_countdown = (state is not None and state.get('allowed')
                           and not state.get('unlimited')
                           and 0 < int(state.get('remaining_seconds', 0)) <= 60)
        self.root.after(1000 if short_countdown else 2000, self.refresh)


if __name__ == '__main__':
    MaxUI()
