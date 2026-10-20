#!/usr/bin/python3
"""ParentPilot Screen Pictures: adult privacy controls for an existing laptop.

One clear setting, no re-running Family Setup, no terminal commands.
The privileged backend only runs after an adult's PolicyKit approval.
"""
import grp
import os
import subprocess
import sys
import threading
import queue
import tkinter as tk
from tkinter import messagebox, ttk

BG = '#0f172a'
CARD = '#1e293b'
TEXT = '#f8fafc'
SUB = '#cbd5e1'
MUTED = '#94a3b8'
BLUE = '#38bdf8'
GREEN = '#34d399'
AMBER = '#fbbf24'
HELPER = '/usr/lib/parentpilot/screen_settings.py'


def adult_account():
    if os.geteuid() == 0:
        return False
    try:
        return bool({grp.getgrgid(g).gr_name for g in os.getgroups()} &
                    {'sudo', 'wheel', 'admin'})
    except KeyError:
        return False


class ScreenSettings:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('ParentPilot — Screen Picture Settings')
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        width, height = min(600, max(330, sw-70)), min(470, max(325, sh-105))
        width, height = min(sw, width), min(sh, height)
        self.root.geometry(f'{width}x{height}+{max(0,(sw-width)//2)}+{max(0,(sh-height)//2)}')
        self.root.minsize(min(width, 370), min(height, 325))
        self.root.configure(bg=BG)
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.events = queue.Queue()
        self.busy = False
        self.enabled = None
        style = ttk.Style(self.root)
        try:
            style.theme_use('clam')
        except tk.TclError:
            pass
        style.configure('Screen.Horizontal.TProgressbar',
                        background=BLUE, troughcolor='#334155', thickness=9)

        main = tk.Frame(self.root, bg=BG, padx=17, pady=14)
        main.pack(fill='both', expand=True)

        foot = tk.Frame(main, bg=BG)
        foot.pack(side='bottom', fill='x', pady=(10, 0))
        self.enable_button = tk.Button(
            foot, text='Enable pictures', bg=BLUE, fg=BG,
            relief='flat', command=lambda: self.change(True),
            font=('Sans', 10, 'bold'), padx=10, pady=8)
        self.enable_button.pack(side='left', padx=(0, 7))
        self.disable_button = tk.Button(
            foot, text='Disable pictures', bg='#334155', fg=TEXT,
            relief='flat', command=lambda: self.change(False),
            font=('Sans', 10, 'bold'), padx=10, pady=8)
        self.disable_button.pack(side='left')

        self.status = tk.StringVar(value='Not checked')
        self.detail = tk.StringVar(
            value='Check the current setting or choose what to allow.')
        panel = tk.Frame(main, bg=CARD, padx=12, pady=11)
        panel.pack(side='bottom', fill='x', pady=(9, 0))
        tk.Label(panel, text='CURRENT SETTING', bg=CARD, fg=MUTED,
                 font=('Sans', 9, 'bold'), anchor='w').pack(fill='x')
        self.status_label = tk.Label(
            panel, textvariable=self.status, bg=CARD, fg=BLUE,
            font=('Sans', 13, 'bold'), anchor='w')
        self.status_label.pack(fill='x', pady=(3, 2))
        tk.Label(panel, textvariable=self.detail, bg=CARD, fg=SUB,
                 font=('Sans', 9), justify='left', anchor='w',
                 wraplength=width-65).pack(fill='x')
        self.spinner = ttk.Progressbar(
            panel, mode='indeterminate', style='Screen.Horizontal.TProgressbar')
        self.spinner.pack(fill='x', pady=(8, 0))
        self.check_button = tk.Button(
            panel, text='Check current setting', command=lambda: self.run('--status'),
            bg='#334155', fg=TEXT, relief='flat', padx=10, pady=5,
            font=('Sans', 9))
        self.check_button.pack(anchor='w', pady=(8, 0))

        header = tk.Frame(main, bg=BG)
        header.pack(fill='x', pady=(0, 11))
        self.icon = None
        try:
            self.icon = tk.PhotoImage(
                file='/usr/share/pixmaps/parentpilot.png').subsample(3, 3)
            tk.Label(header, image=self.icon, bg=BG).pack(side='left', padx=(0, 10))
        except (OSError, tk.TclError):
            tk.Label(header, text='P', bg=BLUE, fg=BG,
                     font=('Sans', 18, 'bold'), width=2).pack(side='left', padx=(0, 10))
        title = tk.Frame(header, bg=BG)
        title.pack(side='left', fill='x', expand=True)
        tk.Label(title, text='ParentPilot', bg=BG, fg=TEXT,
                 font=('Sans', 19, 'bold'), anchor='w').pack(fill='x')
        tk.Label(title, text='SCREEN PICTURE SETTINGS', bg=BG, fg=BLUE,
                 font=('Sans', 9, 'bold'), anchor='w').pack(fill='x')

        description = tk.Frame(main, bg=CARD, padx=13, pady=12)
        description.pack(fill='both', expand=True)
        tk.Label(description, text='View the child’s screen', bg=CARD, fg=TEXT,
                 font=('Sans', 13, 'bold'), anchor='w').pack(fill='x')
        for label in (
            'When enabled, an authenticated parent can request one screen picture from the phone app.',
            'A visible notification appears on the child’s laptop before each picture.',
            'Screen pictures are off by default. There is no continuous recording or hidden streaming.',
            'Disabling requests does not delete previously saved pictures.'):
            tk.Label(description, text='•  ' + label, bg=CARD, fg=SUB,
                     font=('Sans', 9), anchor='w', justify='left',
                     wraplength=max(220, width-90)).pack(fill='x', pady=(6, 0))
        self.root.after(120, self.poll)

    def update_busy(self, busy):
        self.busy = busy
        for button in (self.enable_button, self.disable_button, self.check_button):
            button.configure(state='disabled' if busy else 'normal')
        if busy:
            self.spinner.start(12)
        else:
            self.spinner.stop()

    def change(self, enable):
        if self.busy:
            return
        description = ('ENABLE' if enable else 'DISABLE')
        if not messagebox.askyesno(
            'Confirm screen picture permission',
            description + ' screen picture requests for the child account?\n\n'
            'The child will receive an on-screen notice before each captured picture. '
            'An authenticated parent must request each picture separately. '
            'This action does not alter accounts, PINs, timers or saved screenshots.',
            parent=self.root):
            return
        self.run('--enable' if enable else '--disable')

    def run(self, operation):
        if self.busy or operation not in ('--status', '--enable', '--disable'):
            return
        self.status.set('Waiting for administrator approval…')
        self.detail.set('Enter your adult Linux password in the system authentication prompt.')
        self.status_label.configure(fg=AMBER)
        self.update_busy(True)
        def work():
            try:
                done = subprocess.run(
                    ['pkexec', '/usr/bin/python3', HELPER, operation],
                    capture_output=True, text=True, timeout=120, check=False)
                self.events.put((done.returncode, done.stdout, done.stderr))
            except (OSError, subprocess.TimeoutExpired) as exc:
                self.events.put((1, '', str(exc)))
        threading.Thread(target=work, daemon=True).start()

    def poll(self):
        try:
            while True:
                code, output, error = self.events.get_nowait()
                self.update_busy(False)
                if code == 0 and 'SCREEN_PICTURES:' in output:
                    token = output.strip().split('SCREEN_PICTURES:')[-1].splitlines()[0].strip()
                    if token not in ('enabled', 'disabled'):
                        self.status.set('Unable to verify status')
                        self.detail.set('The settings helper returned an unexpected result.')
                        continue
                    self.enabled = token == 'enabled'
                    self.status.set('Enabled' if self.enabled else 'Disabled')
                    self.status_label.configure(fg=GREEN if self.enabled else SUB)
                    self.detail.set('Your phone can request a picture.' if self.enabled else
                                    'The phone will not be allowed to request pictures.')
                else:
                    self.status.set('Unable to change or read the setting')
                    self.status_label.configure(fg=AMBER)
                    self.detail.set((error or 'Administrator approval cancelled.').strip()[-320:])
        except queue.Empty:
            pass
        self.root.after(150, self.poll)

    def close(self):
        if self.busy:
            messagebox.showwarning(
                'Setting change in progress',
                'Please wait for confirmation before closing ParentPilot Settings.',
                parent=self.root)
        else:
            self.root.destroy()


def main():
    if not adult_account():
        root = tk.Tk()
        root.withdraw()
        try:
            messagebox.showinfo(
                'ParentPilot Screen Pictures',
                'Only the adult Linux administrator can change screen picture settings.',
                parent=root)
        finally:
            root.destroy()
        return
    ScreenSettings().root.mainloop()


if __name__ == '__main__':
    main()
