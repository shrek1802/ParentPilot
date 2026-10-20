#!/usr/bin/python3
"""ParentPilot Games & Learning: optional games manager for an existing laptop.

Administrator only; no changes to accounts or timer settings. Uses the same
allowlisted games as the fresh-install wizard. Installed games stay installed
until an adult explicitly removes them with the regular Linux package manager.
"""
import grp
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from games_catalog import GAMES, MEDIA_PLAYERS
from games_install import is_installed
import sys

BG = '#101827'
PANEL = '#1d2b43'
FOREGROUND = '#f8fafc'
MUTED = '#c9d7e7'
ACCENT = '#38bdf8'
HELPER = '/usr/lib/parentpilot/games_install.py'


def adult_account():
    if os.geteuid() == 0:
        return False
    try:
        names = {grp.getgrgid(gid).gr_name for gid in os.getgroups()}
    except KeyError:
        return False
    return bool(names & {'sudo', 'wheel', 'admin'})


class GamesGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('ParentPilot — Games & Learning')
        width = min(690, max(380, self.root.winfo_screenwidth() - 70))
        height = min(620, max(340, self.root.winfo_screenheight() - 105))
        self.root.geometry(f'{width}x{height}')
        self.root.minsize(min(380, width), min(340, height))
        self.root.configure(bg=BG)
        self.events = queue.Queue()
        self.running = False

        outer = tk.Frame(self.root, bg=BG, padx=16, pady=13)
        outer.pack(fill='both', expand=True)
        tk.Label(outer, text='Games & Learning', font=('Sans', 19, 'bold'),
                 bg=BG, fg=FOREGROUND).pack(anchor='w')
        tk.Label(
            outer,
            text='Free Linux games suited to older laptops. Tick only what you want.',
            font=('Sans', 10), bg=BG, fg=MUTED, wraplength=width - 45,
            justify='left',
        ).pack(anchor='w', pady=(4, 9))
        footer = tk.Frame(outer, bg=BG)
        footer.pack(side='bottom', fill='x', pady=(8, 0))
        self.install_btn = tk.Button(
            footer, text='Install selected apps', bg=ACCENT, fg='#082f49',
            font=('Sans', 11, 'bold'), relief='flat', padx=12, pady=7,
            command=self.install,
        )
        self.install_btn.pack(side='left')
        self.status = tk.StringVar(value='Only selected games will be installed.')
        tk.Label(footer, textvariable=self.status, bg=BG, fg=MUTED,
                 font=('Sans', 9), wraplength=300, justify='left').pack(
                     side='left', padx=10, fill='x', expand=True,
                 )
        self.detail = tk.Text(
            outer, height=3, bg='#0a1424', fg=FOREGROUND,
            font=('Sans', 9), relief='flat', wrap='word',
        )
        self.detail.pack(side='bottom', fill='x', pady=(4, 0))
        self.detail.insert('1.0', 'A parent must approve installation. Games appear in the normal Applications menu, not a locked-down launcher.')
        self.detail.configure(state='disabled')

        holder = tk.Frame(outer, bg=PANEL)
        holder.pack(fill='both', expand=True)
        canvas = tk.Canvas(holder, bg=PANEL, highlightthickness=0)
        sc = ttk.Scrollbar(holder, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=sc.set)
        sc.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        body = tk.Frame(canvas, bg=PANEL, padx=14, pady=8)
        widget = canvas.create_window((0, 0), window=body, anchor='nw')
        body.bind('<Configure>', lambda _e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfigure(widget, width=e.width))

        self.checks = {}
        last_category = ''
        for game_id, title, category, description, package in GAMES:
            if category != last_category:
                last_category = category
                tk.Label(body, text=category.upper(), bg=PANEL, fg=ACCENT,
                         font=('Sans', 10, 'bold')).pack(anchor='w', pady=(9, 3))
            # dpkg-query can be slow or unavailable on an unusual Linux
            # desktop. Opening the window should still work; the privileged
            # installer does the authoritative package check later.
            try:
                installed = is_installed(package)
            except (OSError, subprocess.TimeoutExpired):
                installed = False
            value = tk.BooleanVar(value=False)
            self.checks[game_id] = value
            label = title + ('  ✓ already installed' if installed else '')
            cb = tk.Checkbutton(
                body, text=label, variable=value, bg=PANEL, fg=FOREGROUND,
                selectcolor=BG, activebackground=PANEL,
                activeforeground=FOREGROUND, anchor='w',
                font=('Sans', 11, 'bold'), disabledforeground=MUTED,
            )
            cb.pack(anchor='w')
            if installed:
                cb.configure(state='disabled')
            tk.Label(
                body, text=description, bg=PANEL, fg=MUTED, anchor='w',
                justify='left', wraplength=width - 95,
                font=('Sans', 9),
            ).pack(anchor='w', padx=23, pady=(0, 4))
        tk.Label(body, text='MEDIA PLAYERS', bg=PANEL, fg=ACCENT,
                 font=('Sans', 10, 'bold')).pack(anchor='w', pady=(14, 4))
        self.media_checks = {}
        for media_id, title, _category, description, package in MEDIA_PLAYERS:
            try:
                installed = is_installed(package)
            except (OSError, subprocess.TimeoutExpired):
                installed = False
            value = tk.BooleanVar(value=False)
            self.media_checks[media_id] = value
            cb = tk.Checkbutton(
                body, text=title + ('  ✓ already installed' if installed else ''),
                variable=value, bg=PANEL, fg=FOREGROUND, selectcolor=BG,
                activebackground=PANEL, activeforeground=FOREGROUND,
                anchor='w', font=('Sans', 11, 'bold'), disabledforeground=MUTED,
            )
            cb.pack(anchor='w')
            if installed:
                cb.configure(state='disabled')
            tk.Label(body, text=description + '. VLC remains available.',
                     bg=PANEL, fg=MUTED, anchor='w', justify='left',
                     wraplength=width - 95, font=('Sans', 9)).pack(
                         anchor='w', padx=23, pady=(0, 6))
        self.root.after(120, self.poll)

    def set_detail(self, value):
        self.detail.configure(state='normal')
        self.detail.delete('1.0', 'end')
        self.detail.insert('1.0', value)
        self.detail.configure(state='disabled')

    def install(self):
        if self.running:
            return
        ids = [key for key, var in self.checks.items() if var.get()]
        media_ids = [key for key, var in self.media_checks.items() if var.get()]
        if not ids and not media_ids:
            messagebox.showinfo('Games & Learning', 'Tick one or more games or media players first.', parent=self.root)
            return
        if not messagebox.askyesno(
            'Install selected apps',
            'Install ' + str(len(ids) + len(media_ids)) + ' free app(s) through Linux Mint APT?\\n\\n'
            'This requires internet access and administrator permission. '
            'Apps will be available in the normal Linux Applications menu '
            'for the family. No accounts, timer data or existing programs '
            'will be removed.',
            parent=self.root,
        ):
            return
        self.running = True
        self.install_btn.configure(state='disabled')
        self.status.set('Installing selected apps…')
        self.set_detail('An administrator password prompt should appear. Please do not close the window.')
        def work():
            try:
                result = subprocess.run(
                    ['pkexec', '/usr/bin/python3', HELPER, '--from-manager'],
                    input=json.dumps({'games': ids, 'media': media_ids}), text=True, capture_output=True,
                    timeout=3000, check=False,
                )
                self.events.put((result.returncode, result.stdout + '\n' + result.stderr))
            except (OSError, subprocess.TimeoutExpired) as exc:
                self.events.put((1, str(exc)))
        threading.Thread(target=work, daemon=True).start()

    def poll(self):
        try:
            while True:
                code, result = self.events.get_nowait()
                self.running = False
                self.install_btn.configure(state='normal')
                self.status.set('Finished.' if code == 0 else 'Some apps could not be installed.')
                self.set_detail(result.strip()[-4500:] or 'Administrator approval was cancelled.')
                if code == 0:
                    messagebox.showinfo('Apps installed',
                                        'Selected apps are ready in the Applications menu.',
                                        parent=self.root)
                    self.root.destroy()
                    return
                messagebox.showwarning(
                    'Games & Learning',
                    'Not all selected games were installed. Read the details below.',
                    parent=self.root,
                )
        except queue.Empty:
            pass
        self.root.after(150, self.poll)


def main():
    # The ParentPilot marker and configuration live inside
    # /etc/max-family-control (root:maxfamily, mode 0750). Ordinary adult
    # sudo accounts cannot stat those files. In Preview 15 the startup code
    # silently returned because Path.is_file() could not traverse that
    # directory, even though ParentPilot was correctly configured.
    #
    # Only the privileged games_install backend may check the private marker
    # AFTER the parent explicitly approves PolicyKit authentication.
    if not adult_account():
        root = tk.Tk()
        root.withdraw()
        try:
            messagebox.showinfo(
                'ParentPilot Games & Learning',
                'Please sign into the adult administrator account to install '
                'games. Children can play installed games from the normal '
                'Applications menu.',
                parent=root,
            )
        finally:
            root.destroy()
        return
    try:
        app = GamesGUI()
    except Exception as exc:
        # Do not silently vanish on Tk/font/dpkg failures. Keep diagnostics
        # available for adults launching 'parentpilot-games' in a terminal.
        print('ParentPilot Games & Learning could not start: ' + str(exc),
              file=sys.stderr)
        root = tk.Tk()
        root.withdraw()
        try:
            messagebox.showerror(
                'ParentPilot Games & Learning',
                'The games window could not open. Run parentpilot-games from '
                'the adult account Terminal to see the error.\n\n'
                + str(exc), parent=root,
            )
        finally:
            root.destroy()
        return
    app.root.mainloop()


if __name__ == '__main__':
    main()
