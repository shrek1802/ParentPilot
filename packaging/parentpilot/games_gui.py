#!/usr/bin/python3
"""Adult-only ParentPilot Games & Learning: selected APT apps with live progress.

A familiar XFCE window; does not read protected child files or change any
existing account, limits, PINs, screen pictures, or installed applications.
"""
import grp
import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from games_catalog import GAMES, MEDIA_PLAYERS
from games_install import EVENT_PREFIX, is_installed

BG = '#0f172a'
PANEL = '#1e293b'
INSET = '#111d31'
TEXT = '#f8fafc'
SUB = '#cbd5e1'
MUTED = '#94a3b8'
ACCENT = '#38bdf8'
GREEN = '#34d399'
AMBER = '#fbbf24'
RED = '#fca5a5'
HELPER = '/usr/lib/parentpilot/games_install.py'
CATALOGUE = GAMES + MEDIA_PLAYERS
BY_ENTRY = {item[0]: item for item in CATALOGUE}
COMPLETED = {'already', 'installed', 'failed'}


def adult_account():
    if os.geteuid() == 0:
        return False
    try:
        names = {grp.getgrgid(gid).gr_name for gid in os.getgroups()}
    except KeyError:
        return False
    return bool(names & {'sudo', 'wheel', 'admin'})


def window_size(sw, sh):
    return min(sw, max(310, min(750, sw - 70))), min(sh, max(300, min(630, sh - 100)))


class GamesGUI:
    def __init__(self, parent=None):
        self.embedded = parent is not None
        self.root = tk.Frame(parent, bg=BG) if self.embedded else tk.Tk()
        if self.embedded:
            self.root.pack(fill='both', expand=True)
        else:
            self.root.title('ParentPilot — Games & Learning')
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        width, height = window_size(sw, sh)
        if not self.embedded:
            self.root.geometry(f'{width}x{height}+{max(0, (sw-width)//2)}+{max(0, (sh-height)//2)}')
            self.root.minsize(min(width, 380), min(height, 330))
            self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.root.configure(bg=BG)
        self.events = queue.Queue()
        self.running = False
        self.total = 0
        self.completed = set()
        self.failed = []
        self.row_checks = []

        style = ttk.Style(self.root)
        try:
            style.theme_use('clam')
        except tk.TclError:
            pass
        style.configure('PP.Horizontal.TProgressbar', background=ACCENT,
                        troughcolor='#334155', lightcolor=ACCENT,
                        darkcolor=ACCENT, bordercolor=INSET, thickness=9)

        main = tk.Frame(self.root, bg=BG, padx=14, pady=10)
        main.pack(fill='both', expand=True)

        # Keep controls visible even at 800x480 and high font scaling.
        footer = tk.Frame(main, bg=BG)
        footer.pack(side='bottom', fill='x', pady=(8, 0))
        button_row = tk.Frame(footer, bg=BG)
        button_row.pack(fill='x', pady=(5, 0))
        self.install_btn = tk.Button(
            button_row, text='Install selected apps', command=self.install,
            bg=ACCENT, fg='#082f49', activebackground='#7dd3fc',
            activeforeground='#082f49', font=('Sans', 10, 'bold'),
            relief='flat', padx=12, pady=7, cursor='hand2')
        self.install_btn.pack(side='left')
        self.toggle_btn = tk.Button(
            button_row, text='Show details', command=self.toggle_details,
            bg=PANEL, fg=SUB, activebackground='#334155',
            activeforeground=TEXT, font=('Sans', 9), relief='flat',
            padx=9, pady=7)
        self.toggle_btn.pack(side='right')

        self.detail_container = tk.Frame(footer, bg=PANEL)
        self.detail = tk.Text(
            self.detail_container, height=3, wrap='word',
            bg=INSET, fg=SUB, font=('Sans', 9),
            relief='flat', padx=8, pady=5, state='disabled')
        self.detail.pack(fill='both', expand=True)
        self.set_detail('Installer activity will appear here after adult approval.')
        self.details_open = False

        progress_panel = tk.Frame(footer, bg=PANEL, padx=10, pady=8)
        progress_panel.pack(fill='x')
        self.status = tk.StringVar(value='Ready — select the apps you want')
        tk.Label(progress_panel, textvariable=self.status, bg=PANEL, fg=TEXT,
                 font=('Sans', 10, 'bold'), anchor='w').pack(fill='x')
        self.progress_info = tk.StringVar(value='No changes will be made until you approve installation.')
        tk.Label(progress_panel, textvariable=self.progress_info,
                 bg=PANEL, fg=MUTED, font=('Sans', 9), anchor='w',
                 justify='left', wraplength=max(230, width-65)).pack(fill='x', pady=(2, 5))
        self.progress = ttk.Progressbar(progress_panel, orient='horizontal',
                                        mode='determinate', maximum=1, value=0,
                                        style='PP.Horizontal.TProgressbar')
        self.progress.pack(fill='x')
        self.activity_bar = ttk.Progressbar(
            progress_panel, orient='horizontal', mode='indeterminate',
            style='PP.Horizontal.TProgressbar')
        # The pulsing bar is only shown while a real install is in progress.

        heading = tk.Frame(main, bg=BG)
        heading.pack(fill='x', pady=(0, 8))
        self.logo = None
        try:
            self.logo = tk.PhotoImage(file='/usr/share/pixmaps/parentpilot.png').subsample(3, 3)
            tk.Label(heading, image=self.logo, bg=BG).pack(side='left', padx=(0, 10))
        except (OSError, tk.TclError):
            tk.Label(heading, text='P', bg=ACCENT, fg=BG,
                     font=('Sans', 18, 'bold'), width=2).pack(side='left', padx=(0, 10))
        title_panel = tk.Frame(heading, bg=BG)
        title_panel.pack(side='left', fill='x', expand=True)
        tk.Label(title_panel, text='Games & Learning', bg=BG, fg=TEXT,
                 font=('Sans', 18, 'bold'), anchor='w').pack(fill='x')
        tk.Label(title_panel, text='Official Linux Mint apps · Adult approved installs',
                 bg=BG, fg=MUTED, font=('Sans', 9), anchor='w').pack(fill='x')

        tk.Label(main, text='Choose games and media players. Installed apps stay available.',
                 bg=BG, fg=SUB, font=('Sans', 9), anchor='w',
                 wraplength=max(250, width-40)).pack(fill='x', pady=(0, 6))
        self.selection = tk.StringVar(value='0 apps selected')
        tk.Label(main, textvariable=self.selection, bg=BG, fg=ACCENT,
                 font=('Sans', 9, 'bold'), anchor='w').pack(fill='x', pady=(0, 5))

        holder = tk.Frame(main, bg=PANEL)
        holder.pack(fill='both', expand=True)
        canvas = tk.Canvas(holder, bg=PANEL, highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(holder, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        body = tk.Frame(canvas, bg=PANEL, padx=11, pady=8)
        window = canvas.create_window((0, 0), window=body, anchor='nw')
        body.bind('<Configure>', lambda _e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfigure(window, width=e.width))
        canvas.bind('<MouseWheel>', lambda e: canvas.yview_scroll(-1 if e.delta > 0 else 1, 'units'))
        body.bind('<MouseWheel>', lambda e: canvas.yview_scroll(-1 if e.delta > 0 else 1, 'units'))

        self.checks = {}
        self.media_checks = {}
        self.installed = {}
        self.rows = {}
        last = None
        for item_id, title, category, description, package in CATALOGUE:
            if category != last:
                last = category
                tk.Label(body, text=category.upper(), bg=PANEL, fg=ACCENT,
                         font=('Sans', 10, 'bold'), anchor='w').pack(
                             fill='x', pady=(10, 5))
            try:
                installed = is_installed(package)
            except (OSError, subprocess.TimeoutExpired):
                installed = False
            self.installed[item_id] = installed
            choice = tk.BooleanVar(value=False)
            if item_id in dict((entry[0], entry) for entry in GAMES):
                self.checks[item_id] = choice
            else:
                self.media_checks[item_id] = choice
            choice.trace_add('write', lambda *_: self.update_selection())

            row = tk.Frame(body, bg=INSET, padx=10, pady=8)
            row.pack(fill='x', pady=(0, 5))
            self.rows[item_id] = row
            topline = tk.Frame(row, bg=INSET)
            topline.pack(fill='x')
            check = tk.Checkbutton(
                topline, text=title, variable=choice, bg=INSET, fg=TEXT,
                activebackground=INSET, activeforeground=TEXT,
                selectcolor=BG, anchor='w', font=('Sans', 10, 'bold'),
                disabledforeground=MUTED, borderwidth=0)
            check.pack(side='left', fill='x', expand=True)
            self.row_checks.append(check)
            if installed:
                tk.Label(topline, text='INSTALLED', bg='#134e4a', fg=GREEN,
                         font=('Sans', 8, 'bold'), padx=6, pady=2).pack(side='right')
                check.configure(state='disabled')
            else:
                tk.Label(topline, text='AVAILABLE', bg='#334155', fg=SUB,
                         font=('Sans', 8, 'bold'), padx=6, pady=2).pack(side='right')
            note = description + (' · VLC stays installed.' if category == 'Media Players' else '')
            tk.Label(row, text=note, bg=INSET, fg=MUTED,
                     font=('Sans', 9), anchor='w', justify='left',
                     wraplength=max(230, width-105)).pack(fill='x', padx=(22, 0), pady=(2, 0))
            for widget in (row, topline, check):
                widget.bind('<MouseWheel>', lambda e: canvas.yview_scroll(-1 if e.delta > 0 else 1, 'units'), add='+')

        self.root.after(120, self.poll)

    def update_selection(self):
        count = sum(bool(var.get()) for var in
                    tuple(self.checks.values()) + tuple(self.media_checks.values()))
        self.selection.set(str(count) + (' app selected' if count == 1 else ' apps selected'))

    def set_detail(self, value):
        self.detail.configure(state='normal')
        self.detail.delete('1.0', 'end')
        self.detail.insert('1.0', value)
        self.detail.see('end')
        self.detail.configure(state='disabled')

    def add_detail(self, value):
        if not value:
            return
        self.detail.configure(state='normal')
        self.detail.insert('end', value[:700] + '\n')
        self.detail.see('end')
        if int(self.detail.index('end-1c').split('.')[0]) > 180:
            self.detail.delete('1.0', '40.0')
        self.detail.configure(state='disabled')

    def toggle_details(self):
        if self.details_open:
            self.detail_container.pack_forget()
            self.toggle_btn.configure(text='Show details')
        else:
            # Put the optional activity log immediately before the actions.
            self.detail_container.pack(fill='x', before=self.toggle_btn.master,
                                       pady=(0, 5))
            self.toggle_btn.configure(text='Hide details')
        self.details_open = not self.details_open

    def start_progress(self, total):
        self.running = True
        self.total = total
        self.completed.clear()
        self.failed = []
        self.progress.configure(maximum=max(1, total), value=0)
        self.progress_info.set('0 of ' + str(total) + ' apps completed')
        self.status.set('Waiting for administrator password…')
        self.install_btn.configure(state='disabled')
        for check in self.row_checks:
            check.configure(state='disabled')
        self.activity_bar.pack(fill='x', pady=(4, 0))
        self.activity_bar.start(12)

    def install(self):
        if self.running:
            return
        ids = [key for key, var in self.checks.items() if var.get()]
        media_ids = [key for key, var in self.media_checks.items() if var.get()]
        count = len(ids) + len(media_ids)
        if not count:
            messagebox.showinfo('Games & Learning',
                                'Tick one or more available games or media players first.',
                                parent=self.root)
            return
        if not messagebox.askyesno(
            'Install selected apps',
            'Install ' + str(count) + ' selected app(s) from Linux Mint APT?\n\n'
            'The Linux administrator password prompt will appear. '
            'Only selected packages are requested; nothing will be removed. '
            'The child account and ParentPilot screen-time limits are unchanged.',
            parent=self.root,
        ):
            return
        self.start_progress(count)
        self.set_detail('Waiting for administrator approval…')
        args = ['pkexec', '/usr/bin/python3', HELPER, '--from-manager']
        request = json.dumps({'games': ids, 'media': media_ids})

        def work():
            try:
                # A pipe + Popen is essential: subprocess.run(capture_output=True)
                # would hide every stage until APT finally finished.
                with subprocess.Popen(
                    args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, text=True, errors='replace', bufsize=1,
                ) as process:
                    process.stdin.write(request)
                    process.stdin.close()
                    for raw in process.stdout:
                        self.events.put(('line', raw.rstrip('\r\n')))
                    code = process.wait()
                self.events.put(('done', code))
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                self.events.put(('error', str(exc)))
        threading.Thread(target=work, daemon=True).start()

    def process_line(self, line):
        if line.startswith(EVENT_PREFIX):
            try:
                item = json.loads(line[len(EVENT_PREFIX):])
                event = item['event']
                item_id = item['id']
                if item_id not in BY_ENTRY or event not in (
                    'checking', 'installing', 'already', 'installed', 'failed'):
                    return
                name = BY_ENTRY[item_id][1]  # Never trust names from process text.
            except (ValueError, KeyError, TypeError):
                return
            if event == 'checking':
                self.status.set('Checking ' + name)
            elif event == 'installing':
                self.status.set('Installing ' + name + '…')
            else:
                if item_id not in self.completed:
                    self.completed.add(item_id)
                    self.progress.configure(value=len(self.completed))
                self.progress_info.set(str(len(self.completed)) + ' of ' +
                                       str(self.total) + ' apps completed')
                if event == 'failed':
                    self.failed.append(name)
                    self.status.set('Could not install ' + name)
                elif event == 'already':
                    self.status.set('Already installed: ' + name)
                else:
                    self.status.set('Installed: ' + name)
            return
        self.add_detail(line)

    def finish(self, code, explanation=''):
        self.running = False
        self.activity_bar.stop()
        self.activity_bar.pack_forget()
        self.install_btn.configure(state='normal')
        for item_id, check in zip(self.installed, self.row_checks):
            if not self.installed[item_id]:
                check.configure(state='normal')
        if explanation:
            self.add_detail('ERROR: ' + explanation)
        if code == 0 and not explanation:
            self.status.set('Installation completed')
            self.progress_info.set(str(self.total) + ' of ' + str(self.total) +
                                   ' apps processed · Ready in the Applications menu')
            self.progress.configure(value=self.total)
            self.add_detail('SUCCESS: Selected apps have been processed.')
            messagebox.showinfo('Apps ready',
                                'Selected apps have been processed. '
                                'Open the normal Applications menu to use them.',
                                parent=self.root)
        else:
            self.status.set('Installation stopped or partially failed')
            self.progress_info.set(str(len(self.completed)) + ' of ' + str(self.total) +
                                   ' apps processed · Check details below')
            if not self.details_open:
                self.toggle_details()
            if not explanation and not self.completed:
                self.add_detail('Administrator approval was cancelled or installer stopped.')
            messagebox.showwarning('Games & Learning',
                                   'Not all selected apps could be installed. '
                                   'Read the activity details and retry when ready.',
                                   parent=self.root)

    def poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == 'line':
                    self.process_line(value)
                elif kind == 'done':
                    self.finish(value)
                elif kind == 'error':
                    self.finish(1, value)
        except queue.Empty:
            pass
        self.root.after(150, self.poll)

    def close(self):
        if self.running:
            messagebox.showwarning('Installation in progress',
                                   'Please wait until the installer finishes before closing.',
                                   parent=self.root)
        else:
            self.root.destroy()


def main():
    # Private ParentPilot configuration is root:maxfamily 0750. Do not try
    # to read it in the unprivileged GUI: only the approved pkexec backend may.
    if not adult_account():
        root = tk.Tk()
        root.withdraw()
        try:
            messagebox.showinfo(
                'ParentPilot Games & Learning',
                'Please sign into the adult administrator account to install '
                'games. Children can use installed games from the normal '
                'Applications menu.', parent=root)
        finally:
            root.destroy()
        return
    try:
        app = GamesGUI()
    except Exception as exc:
        print('ParentPilot Games & Learning could not start: ' + str(exc),
              file=sys.stderr)
        root = tk.Tk()
        root.withdraw()
        try:
            messagebox.showerror(
                'ParentPilot Games & Learning',
                'The games window could not open. Run parentpilot-games from '
                'the adult account Terminal to see the error.\n\n' +
                str(exc), parent=root)
        finally:
            root.destroy()
        return
    app.root.mainloop()


if __name__ == '__main__':
    main()
