#!/usr/bin/python3
"""ParentPilot Updates: parent-only graphical update notice and approval.

No actions run as administrator until the parent clicks Install and confirms
the PolicyKit prompt. The child session cannot access the upgrade controls.
"""
import getpass
import grp
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from update_release import fetch_updates, installed_version

BACKEND = '/usr/lib/parentpilot/update_install.py'
CACHE = Path.home() / '.cache' / 'parentpilot' / 'last-release-notification.txt'


def adult_account():
    if os.geteuid() == 0:
        return False
    try:
        names = {grp.getgrgid(gid).gr_name for gid in os.getgroups()}
    except KeyError:
        return False
    return bool(names & {'sudo', 'wheel', 'admin'})


def notify_only():
    """Run from XFCE autostart; do nothing on child accounts."""
    if not adult_account():
        return
    try:
        update = fetch_updates('stable')
        if not update:
            return
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        if CACHE.is_file() and CACHE.read_text().strip() == update['tag']:
            return
        subprocess.run(['notify-send', '--app-name=ParentPilot',
                        'ParentPilot update available',
                        'Version ' + update['version'] +
                        ' is ready. Open ParentPilot Updates to review changes.'],
                       check=False, timeout=7)
        CACHE.write_text(update['tag'] + '\n')
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired):
        # Login remains unaffected when offline.
        return


def fit_update_window(screen_width, screen_height):
    """Keep the window within the usable screen even on compact XFCE laptops."""
    w = max(300, min(620, int(screen_width) - 65))
    h = max(270, min(525, int(screen_height) - 105))
    return min(w, int(screen_width)), min(h, int(screen_height))


class UpdatesGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('ParentPilot Updates')
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        width, height = fit_update_window(sw, sh)
        self.root.geometry(f'{width}x{height}+{max(0, (sw-width)//2)}+{max(0, (sh-height)//2)}')
        self.root.minsize(min(380, width), min(320, height))
        self.root.configure(background='#111827')
        self.events = queue.Queue()
        self.release = None
        self.busy = False

        style = ttk.Style(self.root)
        try:
            style.theme_use('clam')
        except tk.TclError:
            pass
        style.configure('Parent.TFrame', background='#111827')
        style.configure('Parent.TLabel', background='#111827', foreground='#F8FAFC',
                        font=('Sans', 10))
        style.configure('Muted.TLabel', background='#111827', foreground='#E2E8F0',
                        font=('Sans', 9))
        style.configure('Header.TLabel', background='#111827', foreground='#F8FAFC',
                        font=('Sans', 19, 'bold'))
        style.configure('Parent.TButton', padding=(12, 7), font=('Sans', 10, 'bold'))
        frame = ttk.Frame(self.root, style='Parent.TFrame', padding=14)
        frame.pack(fill='both', expand=True)

        # Reserve space for controls FIRST. On 1024x600/XFCE the previous
        # 11-line notes field and long disclaimer pushed these buttons below
        # the visible window; pack(bottom) prevents this on small displays.
        controls = ttk.Frame(frame, style='Parent.TFrame')
        controls.pack(side='bottom', fill='x', pady=(8, 0))
        self.check_button = ttk.Button(
            controls, text='Check for updates',
            style='Parent.TButton', command=self.check,
        )
        self.check_button.pack(side='left', padx=(0, 8))
        self.install_button = ttk.Button(
            controls, text='Install update',
            style='Parent.TButton', command=self.install,
            state='disabled',
        )
        self.install_button.pack(side='left')

        ttk.Label(
            frame,
            text='Adult approval required · Backup first · Child sign-out if needed',
            style='Muted.TLabel', wraplength=max(230, width - 55),
            justify='left',
        ).pack(side='bottom', anchor='w', pady=(8, 2))

        ttk.Label(frame, text='ParentPilot Updates',
                  style='Header.TLabel').pack(anchor='w')
        ttk.Label(
            frame, text='Updates for the family laptop',
            style='Muted.TLabel',
        ).pack(anchor='w', pady=(1, 9))
        try:
            version = installed_version()
        except (OSError, RuntimeError):
            version = 'Unknown'
        ttk.Label(frame, text='Installed version: ' + version,
                  style='Parent.TLabel').pack(anchor='w', pady=3)

        chooser = ttk.Frame(frame, style='Parent.TFrame')
        chooser.pack(fill='x', pady=(5, 8))
        ttk.Label(chooser, text='Update channel',
                  style='Parent.TLabel').pack(side='left')
        self.channel = tk.StringVar(value='stable')
        self.channel_select = ttk.Combobox(
            chooser, textvariable=self.channel, state='readonly',
            values=('stable', 'preview'), width=13,
        )
        self.channel_select.pack(side='left', padx=10)
        self.channel_select.bind('<<ComboboxSelected>>', lambda _event: self.check())

        self.status = tk.StringVar(value='Checking for updates…')
        ttk.Label(
            frame, textvariable=self.status, style='Parent.TLabel',
            wraplength=max(230, width - 45),
        ).pack(anchor='w', pady=(3, 7))
        ttk.Label(frame, text="Release notes / update details",
                  style='Parent.TLabel').pack(anchor='w')

        # Text shrinks before controls, with scrolling for long release notes.
        notes_frame = ttk.Frame(frame, style='Parent.TFrame')
        notes_frame.pack(fill='both', expand=True, pady=(4, 0))
        scroll = ttk.Scrollbar(notes_frame, orient='vertical')
        self.notes = tk.Text(
            notes_frame, height=3, wrap='word',
            bg='#1F2937', fg='#F8FAFC', insertbackground='#F8FAFC',
            font=('Sans', 10), relief='flat', borderwidth=0,
            padx=9, pady=8, yscrollcommand=scroll.set,
        )
        scroll.configure(command=self.notes.yview)
        scroll.pack(side='right', fill='y')
        self.notes.pack(side='left', fill='both', expand=True)
        self.set_notes('Select a channel to check published GitHub Releases.')

        self.root.after(150, self.process_events)
        self.root.after(450, self.check)

    def set_notes(self, value):
        self.notes.configure(state='normal')
        self.notes.delete('1.0', 'end')
        self.notes.insert('1.0', value)
        self.notes.configure(state='disabled')

    def start_worker(self, operation, callback):
        if self.busy:
            return
        self.busy = True
        self.check_button.configure(state='disabled')
        self.install_button.configure(state='disabled')
        def run():
            try:
                result = operation()
                self.events.put((callback, result, None))
            except Exception as exc:
                self.events.put((callback, None, str(exc)))
        threading.Thread(target=run, daemon=True).start()

    def process_events(self):
        try:
            while True:
                callback, result, error = self.events.get_nowait()
                self.busy = False
                self.check_button.configure(state='normal')
                callback(result, error)
        except queue.Empty:
            pass
        self.root.after(150, self.process_events)

    def check(self):
        if self.busy:
            return
        self.release = None
        self.install_button.configure(state='disabled')
        self.status.set('Checking published ' + self.channel.get() + ' releases…')
        self.set_notes('Contacting GitHub Releases over HTTPS.')
        chosen = self.channel.get()
        self.start_worker(lambda: fetch_updates(chosen), self.checked)

    def checked(self, result, error):
        if error:
            self.status.set('Could not check updates. Please try again when online.')
            self.set_notes(error)
        elif result is None:
            self.status.set('No newer published update is available on this channel.')
            self.set_notes('You are using the latest release available for this channel, '
                           'or no qualifying signed-off package has been published yet.')
        else:
            self.release = result
            self.status.set('New version available: ' + result['version'])
            self.set_notes(result['changes'])
            self.install_button.configure(state='normal')

    def install(self):
        update = self.release
        if not update or self.busy:
            return
        if not messagebox.askyesno(
                'Confirm update and child sign-out',
                'Install ParentPilot ' + update['version'] + '?\n\n'
                'If the child is still signed in (even in the background), '
                'ParentPilot will automatically sign out ONLY the child account '
                'before updating.\n\n'
                'WARNING: Please save the child\'s open work first. '
                'Unsaved work in their apps may be LOST.\n\n'
                'The adult account remains signed in. ParentPilot backs up '
                'the configuration, timer state and saved pictures before the '
                'child is signed out.\n\n'
                'Approve this update and any necessary child sign-out?',
                parent=self.root):
            return
        self.status.set('Verifying the update and preparing a private backup…')
        self.set_notes(
            'A PolicyKit password dialog should open. The package is verified '
            'and backed up before the child is signed out, if needed. '
            'Do not shut down the laptop during installation.'
        )
        args = ['pkexec', '/usr/bin/python3', BACKEND, self.channel.get(),
                update['tag'], '--sign-out-child']
        self.start_worker(
            lambda: subprocess.run(args, capture_output=True, text=True, timeout=480),
            self.installed
        )

    def installed(self, result, error):
        if error:
            self.status.set('Update did not complete.')
            self.set_notes(error)
            return
        output = (result.stdout + '\n' + result.stderr).strip()
        if result.returncode != 0:
            self.status.set('Update stopped; see details below.')
            self.set_notes(output[-4500:] or 'Administrator approval was cancelled.')
            if self.release:
                self.install_button.configure(state='normal')
        else:
            self.release = None
            self.status.set('Update installed successfully.')
            self.set_notes(output[-4500:] + '\n\nSign the child back in to '
                           'start the updated desktop controller.')

    def main(self):
        self.root.mainloop()


def main():
    if not adult_account():
        if '--notify' not in sys.argv:
            print('ParentPilot Updates is for an adult administrator account.',
                  file=sys.stderr)
        return
    if sys.argv[1:] == ['--notify']:
        notify_only()
    else:
        UpdatesGUI().main()


if __name__ == '__main__':
    main()
