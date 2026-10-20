#!/usr/bin/python3
"""ParentPilot Updates: responsive, parent-only update installer for XFCE/X11.

Display real milestones from the privileged installer while retaining PolicyKit,
verified GitHub releases, backups, child sign-out and service recovery.
"""
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
BG = '#0f172a'
PANEL = '#1e293b'
PANEL_DARK = '#111d31'
TEXT = '#f8fafc'
SOFT = '#cbd5e1'
MUTED = '#94a3b8'
ACCENT = '#38bdf8'
GREEN = '#34d399'
AMBER = '#fbbf24'
RED = '#fca5a5'
PHASES = {
    'verify': (1, 'Checking release', 'Confirming the chosen version with GitHub.'),
    'download': (2, 'Downloading update', 'Downloading and verifying the official package.'),
    'backup': (3, 'Saving private backup', 'Preserving settings, PIN, timer and saved screen pictures.'),
    'signout': (4, 'Checking child session', 'Signing out the child only if you approved it.'),
    'install': (5, 'Installing the update', 'APT is installing the verified Debian package.'),
    'deploy': (6, 'Updating ParentPilot', 'Updating program files and the managed child panel.'),
    'health': (7, 'Checking everything works', 'Restarting and checking the ParentPilot service.'),
    'complete': (7, 'Update completed', 'The installer finished and its service check passed.'),
    'restore': (7, 'Restoring from backup', 'An error occurred. Attempting safe recovery.'),
}


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
        return


def fit_update_window(screen_width, screen_height):
    """Fit controls onto older 800x480 and 1024x600 XFCE displays."""
    w = max(300, min(740, int(screen_width) - 65))
    h = max(270, min(640, int(screen_height) - 105))
    return min(w, int(screen_width)), min(h, int(screen_height))


class UpdatesGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('ParentPilot | Updates')
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        width, height = fit_update_window(sw, sh)
        self.root.geometry(f'{width}x{height}+{max(0, (sw - width)//2)}+{max(0, (sh - height)//2)}')
        self.root.minsize(min(430, width), min(350, height))
        self.root.configure(background=BG)
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.events = queue.Queue()
        self.release = None
        self.busy = False
        self.installing = False
        self.activity_lines = 0

        style = ttk.Style(self.root)
        try:
            style.theme_use('clam')
        except tk.TclError:
            pass
        style.configure('Parent.TCombobox', padding=(6, 4))
        style.configure('Parent.TNotebook', background=BG, borderwidth=0, tabmargins=(0, 0, 0, 0))
        style.configure('Parent.TNotebook.Tab', background=PANEL, foreground=SOFT,
                        padding=(12, 5), font=('Sans', 9, 'bold'))
        style.map('Parent.TNotebook.Tab',
                  background=[('selected', PANEL_DARK)],
                  foreground=[('selected', ACCENT)])
        style.configure('Parent.Horizontal.TProgressbar', background=ACCENT,
                        troughcolor='#334155', lightcolor=ACCENT, darkcolor=ACCENT,
                        bordercolor='#334155', thickness=9)

        main = tk.Frame(self.root, bg=BG, padx=16, pady=12)
        main.pack(fill='both', expand=True)

        # Footer is packed first, so actions remain visible on small displays.
        footer = tk.Frame(main, bg=BG)
        footer.pack(side='bottom', fill='x', pady=(8, 0))
        self.check_button = tk.Button(
            footer, text='Check for updates', command=self.check,
            bg=PANEL, fg=TEXT, activebackground='#334155',
            activeforeground=TEXT, font=('Sans', 10, 'bold'),
            relief='flat', padx=12, pady=7, cursor='hand2',
        )
        self.check_button.pack(side='left', padx=(0, 8))
        self.install_button = tk.Button(
            footer, text='Install update', command=self.install,
            bg=ACCENT, fg='#082f49', activebackground='#7dd3fc',
            activeforeground='#082f49', font=('Sans', 10, 'bold'),
            relief='flat', padx=12, pady=7, cursor='hand2', state='disabled',
        )
        self.install_button.pack(side='left')
        self.bottom_hint = tk.StringVar(
            value='Administrator approval required  •  Private backup before installation'
        )
        tk.Label(main, textvariable=self.bottom_hint, bg=BG, fg=MUTED,
                 font=('Sans', 8), anchor='w').pack(
                     side='bottom', fill='x', pady=(8, 0))

        # Header and branded identity.
        header = tk.Frame(main, bg=BG)
        header.pack(fill='x', pady=(0, 9))
        self.logo = None
        try:
            path = '/usr/share/pixmaps/parentpilot.png'
            self.logo = tk.PhotoImage(file=path).subsample(3, 3)
            tk.Label(header, image=self.logo, bg=BG).pack(side='left', padx=(0, 10))
        except (tk.TclError, OSError):
            tk.Label(header, text='P', bg=ACCENT, fg=BG,
                     font=('Sans', 19, 'bold'), width=2).pack(side='left', padx=(0, 10))
        header_text = tk.Frame(header, bg=BG)
        header_text.pack(side='left', fill='x', expand=True)
        tk.Label(header_text, text='ParentPilot Updates', bg=BG, fg=TEXT,
                 font=('Sans', 19, 'bold'), anchor='w').pack(fill='x')
        tk.Label(header_text, text='Safe updates for your family laptop',
                 bg=BG, fg=MUTED, font=('Sans', 9), anchor='w').pack(fill='x')

        # Installed version and channel are presented together.
        selector = tk.Frame(main, bg=PANEL, padx=11, pady=8)
        selector.pack(fill='x', pady=(0, 8))
        try:
            self.current_version = installed_version()
        except (OSError, RuntimeError):
            self.current_version = 'Unknown'
        self.installed_label = tk.Label(
            selector, text='INSTALLED  ' + self.current_version,
            bg=PANEL, fg=SOFT, font=('Sans', 10, 'bold'), anchor='w')
        self.installed_label.pack(side='left', fill='x', expand=True)
        self.channel = tk.StringVar(value='stable')
        self.channel_select = ttk.Combobox(
            selector, textvariable=self.channel, state='readonly',
            values=('stable', 'preview'), width=9, style='Parent.TCombobox')
        self.channel_select.pack(side='right')
        tk.Label(selector, text='Channel', bg=PANEL, fg=MUTED,
                 font=('Sans', 9)).pack(side='right', padx=(4, 9))
        self.channel_select.bind('<<ComboboxSelected>>', lambda _event: self.check())

        # Live installation state; the bar pulses rather than claiming a
        # fictitious percentage during unknown-duration APT/systemd operations.
        progress_card = tk.Frame(main, bg=PANEL_DARK, padx=11, pady=9)
        progress_card.pack(fill='x', pady=(0, 8))
        self.status = tk.StringVar(value='Ready to check for updates')
        self.status_label = tk.Label(
            progress_card, textvariable=self.status, bg=PANEL_DARK,
            fg=TEXT, font=('Sans', 11, 'bold'), anchor='w')
        self.status_label.pack(fill='x')
        self.phase = tk.StringVar(value='Select a channel, then check for a published update.')
        self.phase_label = tk.Label(
            progress_card, textvariable=self.phase, bg=PANEL_DARK, fg=MUTED,
            font=('Sans', 9), wraplength=width-70, justify='left', anchor='w')
        self.phase_label.pack(fill='x', pady=(3, 6))
        self.progress = ttk.Progressbar(
            progress_card, orient='horizontal', mode='indeterminate',
            style='Parent.Horizontal.TProgressbar')
        self.progress.pack(fill='x')

        # Two actual panes: friendly release notes and live technical activity.
        self.tabs = ttk.Notebook(main, style='Parent.TNotebook')
        self.tabs.pack(fill='both', expand=True)
        self.notes = self.make_text_tab('What’s new')
        self.activity = self.make_text_tab('Update activity')
        self.set_notes('Checking for a published release…')
        self.set_activity('Installation activity will appear here as it happens.\n'
                          'Only an adult administrator can start an update.')

        self.root.after(150, self.process_events)
        self.root.after(450, self.check)

    def make_text_tab(self, title):
        container = tk.Frame(self.tabs, bg=PANEL_DARK, padx=2, pady=2)
        self.tabs.add(container, text=title)
        scrollbar = tk.Scrollbar(container, orient='vertical',
                                bg=PANEL, troughcolor=PANEL_DARK)
        body = tk.Text(container, height=2, wrap='word', bg=PANEL_DARK,
                       fg=SOFT, insertbackground=TEXT, font=('Sans', 9),
                       relief='flat', padx=9, pady=8, borderwidth=0,
                       yscrollcommand=scrollbar.set)
        scrollbar.configure(command=body.yview)
        scrollbar.pack(side='right', fill='y')
        body.pack(side='left', fill='both', expand=True)
        return body

    def set_notes(self, value):
        self.notes.configure(state='normal')
        self.notes.delete('1.0', 'end')
        self.notes.insert('1.0', value)
        self.notes.configure(state='disabled')

    def set_activity(self, value):
        self.activity.configure(state='normal')
        self.activity.delete('1.0', 'end')
        self.activity.insert('1.0', value)
        self.activity.configure(state='disabled')
        self.activity_lines = value.count('\n') + 1

    def add_activity(self, line):
        if not line:
            return
        self.activity.configure(state='normal')
        self.activity.insert('end', line[:1100] + '\n')
        self.activity_lines += 1
        if self.activity_lines > 300:
            self.activity.delete('1.0', '60.0')
            self.activity_lines -= 59
        self.activity.see('end')
        self.activity.configure(state='disabled')

    def set_busy(self, active, installing=False):
        self.busy = active
        self.installing = bool(active and installing)
        self.check_button.configure(state='disabled' if active else 'normal')
        self.channel_select.configure(state='disabled' if active else 'readonly')
        self.install_button.configure(
            state='disabled' if active or self.release is None else 'normal')
        if active:
            self.progress.start(12)
        else:
            self.progress.stop()

    def start_worker(self, operation, callback):
        if self.busy:
            return
        self.set_busy(True)
        def work():
            try:
                result = operation()
                self.events.put((callback, result, None))
            except Exception as exc:
                self.events.put((callback, None, str(exc)))
        threading.Thread(target=work, daemon=True).start()

    def start_install_worker(self, args):
        """Stream pkexec stdout incrementally; never block Tk or use a shell."""
        self.set_busy(True, installing=True)
        def work():
            lines = []
            try:
                with subprocess.Popen(
                    args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, errors='replace', bufsize=1,
                ) as process:
                    # Guard against hung package installations without stopping
                    # the tkinter thread. The installer has its own APT timeout.
                    expired = threading.Event()
                    def timeout_kill():
                        if process.poll() is None:
                            expired.set()
                            process.kill()
                    watchdog = threading.Timer(480, timeout_kill)
                    watchdog.daemon = True
                    watchdog.start()
                    try:
                        for raw in process.stdout:
                            line = raw.rstrip('\r\n')
                            if line.startswith('PARENTPILOT_PROGRESS:'):
                                self.events.put(('phase', line.split(':', 1)[1], None))
                            else:
                                lines.append(line[-1100:])
                                if len(lines) > 200:
                                    lines.pop(0)
                                self.events.put(('activity', line, None))
                        code = process.wait(timeout=10)
                    finally:
                        watchdog.cancel()
                self.events.put((self.installed,
                                 (code, '\n'.join(lines)),
                                 'Update process timed out.' if expired.is_set() else None))
            except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
                self.events.put((self.installed, None, str(exc)))
        threading.Thread(target=work, daemon=True).start()

    def process_events(self):
        try:
            while True:
                kind, result, error = self.events.get_nowait()
                if kind == 'phase':
                    self.set_phase(result)
                elif kind == 'activity':
                    self.add_activity(result)
                else:
                    self.set_busy(False)
                    kind(result, error)
        except queue.Empty:
            pass
        try:
            self.root.after(150, self.process_events)
        except tk.TclError:
            pass

    def set_phase(self, identifier):
        """Only known, hardcoded stages may control the friendly status."""
        if identifier not in PHASES:
            self.add_activity('Unknown installer stage: ' + str(identifier)[:90])
            return
        number, title, detail = PHASES[identifier]
        self.status.set(title)
        self.phase.set('Step ' + str(number) + ' of 7  •  ' + detail)
        self.status_label.configure(fg=RED if identifier == 'restore' else
                                    GREEN if identifier == 'complete' else TEXT)
        if identifier == 'restore':
            self.tabs.select(self.activity)

    def check(self):
        if self.busy:
            return
        self.release = None
        self.set_busy(False)
        self.status_label.configure(fg=TEXT)
        self.status.set('Checking for updates…')
        self.phase.set('Checking published ' + self.channel.get() + ' releases over HTTPS.')
        self.set_notes('Contacting official ParentPilot GitHub Releases…')
        self.tabs.select(self.notes)
        chosen = self.channel.get()
        self.start_worker(lambda: fetch_updates(chosen), self.checked)

    def checked(self, result, error):
        if error:
            self.status.set('Unable to check for updates')
            self.phase.set('Check your internet connection, then try again.')
            self.status_label.configure(fg=RED)
            self.set_notes(error)
        elif result is None:
            self.status.set('You’re up to date')
            self.phase.set('No newer update is available on this channel.')
            self.status_label.configure(fg=GREEN)
            self.set_notes('Your installed version is the latest published for '
                           'this channel, or no verified release is currently available.')
        else:
            self.release = result
            self.status.set('Update available: ' + result['version'])
            self.phase.set('Review what’s new, then choose Install update.')
            self.status_label.configure(fg=ACCENT)
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
        self.status.set('Waiting for administrator approval')
        self.status_label.configure(fg=AMBER)
        self.phase.set('Please enter your Linux password in the system security prompt.')
        self.bottom_hint.set('Please keep this window open until the result is confirmed.')
        self.set_activity('Starting the approved update for ' + update['version'] +
                          '\nWaiting for the system administrator password…\n')
        self.tabs.select(self.activity)
        args = ['pkexec', '/usr/bin/python3', BACKEND, self.channel.get(),
                update['tag'], '--sign-out-child']
        self.start_install_worker(args)

    def installed(self, result, error):
        self.bottom_hint.set('Administrator approval required  •  Private backup before installation')
        if error:
            self.status.set('Update could not finish')
            self.phase.set('Review the activity below. Your existing data is not reset.')
            self.status_label.configure(fg=RED)
            self.add_activity('ERROR: ' + error)
            if self.release:
                self.install_button.configure(state='normal')
            return
        code, output = result
        if code != 0:
            self.status.set('Update stopped')
            self.phase.set('See the activity log for the reason; verify the installed version before retrying.')
            self.status_label.configure(fg=RED)
            if not output.strip():
                self.add_activity('Administrator approval was cancelled or the installer stopped.')
            if self.release:
                self.install_button.configure(state='normal')
            return
        self.release = None
        self.status.set('Update installed successfully')
        self.phase.set('The service check passed. Sign the child back in when ready.')
        self.status_label.configure(fg=GREEN)
        self.add_activity('SUCCESS: The ParentPilot installer completed successfully.')
        self.add_activity('The child can sign back into the updated desktop.')
        try:
            self.current_version = installed_version()
            self.installed_label.configure(text='INSTALLED  ' + self.current_version)
        except (OSError, RuntimeError):
            pass

    def close(self):
        if self.installing:
            messagebox.showwarning(
                'Update in progress',
                'ParentPilot is currently installing or checking an update. '
                'Keep this window open until the final result is shown.',
                parent=self.root)
        else:
            self.root.destroy()

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
