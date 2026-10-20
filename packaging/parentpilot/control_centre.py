#!/usr/bin/python3
"""ParentPilot Control Centre — one adult app for the family laptop.

Native Tk/XFCE tabs reuse the real Updates and Games installers in the same
window. Security changes use separately authenticated PolicyKit requests and
never print, store in a log, or pass a password on command-line arguments.
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

from updates_gui import UpdatesGUI
from games_gui import GamesGUI
from update_release import installed_version

BG='#0f172a'
PANEL='#1e293b'
INSET='#111d31'
TEXT='#f8fafc'
SUB='#cbd5e1'
MUTED='#94a3b8'
ACCENT='#38bdf8'
GREEN='#34d399'
RED='#fca5a5'
HELPER='/usr/lib/parentpilot/account_settings.py'


def adult_account():
    if os.geteuid()==0:
        return False
    try:
        groups={grp.getgrgid(g).gr_name for g in os.getgroups()}
    except KeyError:
        return False
    return bool(groups & {'sudo','admin','wheel'})


class SecurityPane:
    def __init__(self,parent):
        self.frame=tk.Frame(parent,bg=BG,padx=12,pady=8)
        self.frame.pack(fill='both',expand=True)
        self.queue=queue.Queue()
        self.busy=False
        self.all_entries=[]
        self.current=tk.StringVar()
        self.pin=tk.StringVar()
        self.pin_again=tk.StringVar()
        self.child_password=tk.StringVar()
        self.child_again=tk.StringVar()

        title=tk.Frame(self.frame,bg=BG)
        title.pack(fill='x')
        tk.Label(title,text='Family security',bg=BG,fg=TEXT,
                 font=('Sans',15,'bold')).pack(anchor='w')
        tk.Label(title,text='Adult-only changes · Linux administrator approval required',
                 bg=BG,fg=MUTED,font=('Sans',9)).pack(anchor='w',pady=(0,5))

        style=ttk.Style(parent)
        style.configure('Security.TNotebook',background=BG,borderwidth=0)
        style.configure('Security.TNotebook.Tab',padding=(10,5),
                        background=PANEL,foreground=SUB,font=('Sans',9,'bold'))
        style.map('Security.TNotebook.Tab',background=[('selected',INSET)],
                  foreground=[('selected',ACCENT)])
        self.tabs=ttk.Notebook(self.frame,style='Security.TNotebook')
        self.tabs.pack(fill='both',expand=True)
        pin_page=tk.Frame(self.tabs,bg=PANEL,padx=13,pady=10)
        pw_page=tk.Frame(self.tabs,bg=PANEL,padx=13,pady=10)
        self.tabs.add(pin_page,text='Parent PIN')
        self.tabs.add(pw_page,text='Child login password')

        tk.Label(pin_page,text='Change the six-digit parent PIN',bg=PANEL,fg=TEXT,
                 font=('Sans',11,'bold')).pack(anchor='w',pady=(0,7))
        self.field(pin_page,'Current parent PIN',self.current)
        self.field(pin_page,'New six-digit PIN',self.pin)
        self.field(pin_page,'Confirm new PIN',self.pin_again)
        tk.Label(pin_page,text='Your time limits remain the same. The parent phone app will need the new PIN.',
                 bg=PANEL,fg=MUTED,font=('Sans',9),
                 wraplength=580,justify='left').pack(anchor='w')

        tk.Label(pw_page,text='Change the existing child login password',
                 bg=PANEL,fg=TEXT,font=('Sans',11,'bold')).pack(anchor='w',pady=(0,7))
        self.field(pw_page,'New login password (8+ characters)',self.child_password)
        self.field(pw_page,'Confirm login password',self.child_again)
        tk.Label(pw_page,text='Changes the already-existing child account only. It takes effect at their next sign-in; no accounts are recreated.',
                 bg=PANEL,fg=MUTED,font=('Sans',9),
                 wraplength=580,justify='left').pack(anchor='w')

        bottom=tk.Frame(self.frame,bg=INSET,padx=9,pady=6)
        bottom.pack(side='bottom',fill='x',pady=(5,0))
        self.action_button=tk.Button(
            bottom,text='Change parent PIN',command=self.active_action,
            bg=ACCENT,fg=BG,relief='flat',font=('Sans',10,'bold'),padx=12,pady=6)
        self.action_button.pack(side='right',padx=(8,0))
        self.message=tk.StringVar(value='No changes made.')
        tk.Label(bottom,textvariable=self.message,bg=INSET,fg=SUB,
                 anchor='w',justify='left',wraplength=365,
                 font=('Sans',9)).pack(side='left',fill='x',expand=True)
        self.tabs.bind('<<NotebookTabChanged>>',self.sync_action)
        self.frame.after(150,self.poll)

    def sync_action(self,_event=None):
        self.action_button.configure(
            text='Change parent PIN' if self.tabs.index('current')==0
            else 'Change child password')

    def active_action(self):
        if self.tabs.index('current')==0:
            self.change_pin()
        else:
            self.change_password()

    def field(self,parent,title,var):
        tk.Label(parent,text=title,bg=PANEL,fg=SUB,
                 font=('Sans',9),anchor='w').pack(fill='x',pady=(3,1))
        entry=tk.Entry(parent,textvariable=var,show='•',bg='#e2e8f0',
                       fg=BG,insertbackground=BG,relief='flat',
                       font=('Sans',11))
        entry.pack(fill='x',ipady=4)
        self.all_entries.append(entry)

    def change_pin(self):
        current=self.current.get()
        first=self.pin.get()
        second=self.pin_again.get()
        if len(first)!=6 or not first.isascii() or not first.isdecimal():
            messagebox.showerror('Parent PIN','Choose a six-digit parent PIN.',
                                 parent=self.frame.winfo_toplevel())
            return
        if first!=second:
            messagebox.showerror('Parent PIN','The new PIN entries do not match.',
                                 parent=self.frame.winfo_toplevel())
            return
        if len(current)!=6 or not current.isascii() or not current.isdecimal():
            messagebox.showerror('Parent PIN','Enter the current six-digit parent PIN.',
                                 parent=self.frame.winfo_toplevel())
            return
        if messagebox.askyesno('Change parent PIN',
            'Change the parent PIN? This will sign the parent app out. '
            'Screen-time limits, accounts and saved pictures will be preserved.',
            parent=self.frame.winfo_toplevel()):
            self.run({'action':'pin','current':current,'new':first})

    def change_password(self):
        first=self.child_password.get()
        if not 8<=len(first)<=128 or ':' in first or '\n' in first or '\r' in first:
            messagebox.showerror('Child password','Use 8–128 characters without colons or line breaks.',
                                 parent=self.frame.winfo_toplevel())
            return
        if first!=self.child_again.get():
            messagebox.showerror('Child password','The two password entries do not match.',
                                 parent=self.frame.winfo_toplevel())
            return
        if messagebox.askyesno('Change child password',
            'Change the existing child account login password? '
            'The new password will be needed next time the child signs in.',
            parent=self.frame.winfo_toplevel()):
            self.run({'action':'child_password','new':first})

    def run(self,request):
        if self.busy:
            return
        self.busy=True
        self.message.set('Waiting for Linux administrator approval…')
        for entry in self.all_entries:
            entry.configure(state='disabled')
        self.action_button.configure(state='disabled')
        # Clear all Tk password fields promptly; only the worker thread keeps
        # the one-use request to deliver through stdin to the root helper.
        for value in (self.current,self.pin,self.pin_again,
                      self.child_password,self.child_again):
            value.set('')
        def worker():
            try:
                proc=subprocess.run(
                    ['pkexec','/usr/bin/python3',HELPER,'--from-centre'],
                    input=json.dumps(request),capture_output=True,
                    text=True,timeout=90,check=False)
                self.queue.put((proc.returncode,proc.stdout,proc.stderr))
            except (OSError,subprocess.TimeoutExpired) as error:
                self.queue.put((1,'',str(error)))
        threading.Thread(target=worker,daemon=True).start()

    def poll(self):
        try:
            while True:
                code,out,err=self.queue.get_nowait()
                self.busy=False
                for entry in self.all_entries:
                    entry.configure(state='normal')
                self.action_button.configure(state='normal')
                if code==0 and out.startswith('SECURITY_RESULT:'):
                    self.message.set(out.split('SECURITY_RESULT:',1)[1].strip()[:220])
                else:
                    # Backend errors are fixed explanations, never requests or
                    # the password itself. Bound the displayed diagnostic.
                    self.message.set((err or 'Approval cancelled or operation failed.').strip()[-240:])
        except queue.Empty:
            pass
        self.frame.after(150,self.poll)


class Centre:
    def __init__(self):
        self.root=tk.Tk()
        self.root.title('ParentPilot | Control Centre')
        sw,sh=self.root.winfo_screenwidth(),self.root.winfo_screenheight()
        width=min(sw,max(430,min(880,sw-65)))
        height=min(sh,max(350,min(690,sh-95)))
        self.root.geometry(f'{width}x{height}+{max(0,(sw-width)//2)}+{max(0,(sh-height)//2)}')
        self.root.minsize(min(430,width),min(350,height))
        self.root.configure(bg=BG)
        self.root.protocol('WM_DELETE_WINDOW',self.close)

        header=tk.Frame(self.root,bg=BG,padx=12,pady=6)
        header.pack(fill='x')
        self.logo=None
        try:
            self.logo=tk.PhotoImage(file='/usr/share/pixmaps/parentpilot.png').subsample(4,4)
            tk.Label(header,image=self.logo,bg=BG).pack(side='left',padx=(0,8))
        except (OSError,tk.TclError):
            tk.Label(header,text='P',bg=ACCENT,fg=BG,font=('Sans',18,'bold'),
                     width=2).pack(side='left',padx=(0,8))
        title=tk.Frame(header,bg=BG)
        title.pack(side='left')
        tk.Label(title,text='ParentPilot Control Centre',fg=TEXT,bg=BG,
                 font=('Sans',16,'bold')).pack(anchor='w')
        tk.Label(title,text='Manage your family laptop in one place',
                 bg=BG,fg=MUTED,font=('Sans',9)).pack(anchor='w')
        style=ttk.Style(self.root)
        try:
            style.theme_use('clam')
        except tk.TclError:
            pass
        style.configure('Centre.TNotebook',background=BG,borderwidth=0)
        style.configure('Centre.TNotebook.Tab',background=PANEL,foreground=SUB,
                        padding=(9,6),font=('Sans',9,'bold'))
        style.map('Centre.TNotebook.Tab',background=[('selected',INSET)],
                  foreground=[('selected',ACCENT)])
        self.tabs=ttk.Notebook(self.root,style='Centre.TNotebook')
        self.tabs.pack(fill='both',expand=True,padx=8,pady=(0,8))
        frames=[]
        for name in ('Home','Updates','Games & Media','Security','Help'):
            page=tk.Frame(self.tabs,bg=BG)
            self.tabs.add(page,text=name)
            frames.append(page)
        self.home(frames[0])
        self.updates=UpdatesGUI(parent=frames[1])
        self.games=GamesGUI(parent=frames[2])
        self.security=SecurityPane(frames[3])
        self.help(frames[4])

    def home(self,parent):
        frame=tk.Frame(parent,bg=BG,padx=18,pady=14)
        frame.pack(fill='both',expand=True)
        tk.Label(frame,text='Family laptop overview',bg=BG,fg=TEXT,
                 font=('Sans',17,'bold')).pack(anchor='w')
        try:
            version=installed_version()
        except (OSError,RuntimeError):
            version='Unknown'
        try:
            service=subprocess.run(
                ['systemctl','is-active','max-family-control.service'],
                capture_output=True,text=True,timeout=3,check=False)
            state='Running' if service.returncode==0 else 'Not running — check service'
        except (OSError,subprocess.TimeoutExpired):
            state='Status unavailable'
        for heading,value in (('INSTALLED VERSION',version),
                              ('SCREEN-TIME SERVICE',state),
                              ('FAMILY SETTINGS','Existing accounts and time allowances retained')):
            panel=tk.Frame(frame,bg=PANEL,padx=13,pady=9)
            panel.pack(fill='x',pady=(9,0))
            tk.Label(panel,text=heading,bg=PANEL,fg=ACCENT,
                     font=('Sans',9,'bold'),anchor='w').pack(fill='x')
            tk.Label(panel,text=value,bg=PANEL,fg=TEXT,
                     font=('Sans',11),anchor='w',wraplength=550).pack(fill='x')
        tk.Label(frame,text='Use the tabs above to install games or Kodi, check updates, '
                 'or change the parent PIN and child login password. '
                 'The timer and screen lock continue working independently.',
                 bg=BG,fg=SUB,font=('Sans',9),justify='left',
                 wraplength=700).pack(anchor='w',pady=(14,0))

    def help(self,parent):
        frame=tk.Frame(parent,bg=BG,padx=15,pady=14)
        frame.pack(fill='both',expand=True)
        tk.Label(frame,text='Help & information',bg=BG,fg=TEXT,
                 font=('Sans',16,'bold')).pack(anchor='w',pady=(0,8))
        topics=(
            ('Updates','Check the preview/stable channel. Review release details, then approve the administrator password. Existing child settings are backed up first.'),
            ('Games & media','Select official APT apps such as Kodi. A real live progress bar and activity details appear during installation. VLC stays available.'),
            ('Parent PIN','Enter the current PIN, choose and confirm a new six-digit PIN. The phone app may need you to sign in again.'),
            ('Child password','Change the existing Linux account password; do not run Family Setup again. New password applies at the next sign-in.'),
            ('Pinned apps','ParentPilot no longer rebuilds the child taskbar during upgrades, preserving manually pinned Kodi and other shortcuts.'),
            ('Screen pictures','The authenticated parent can request one picture at a time. The child sees a notice; nothing is recorded continuously.'),
        )
        for heading,detail in topics:
            tk.Label(frame,text=heading,bg=BG,fg=ACCENT,
                     font=('Sans',10,'bold'),anchor='w').pack(fill='x',pady=(7,0))
            tk.Label(frame,text=detail,bg=BG,fg=SUB,
                     font=('Sans',9),wraplength=685,justify='left',
                     anchor='w').pack(fill='x')
        tk.Label(frame,text='ParentPilot is a preview. Report problems through the project GitHub repository.',
                 bg=BG,fg=MUTED,font=('Sans',9),
                 wraplength=650,justify='left').pack(anchor='w',pady=(14,0))

    def close(self):
        if self.updates.busy or self.games.running or self.security.busy:
            messagebox.showwarning('Please wait',
                'An update, app installation or security change is in progress. '
                'Keep ParentPilot open until the operation finishes.',
                parent=self.root)
        else:
            self.root.destroy()


def main():
    if not adult_account():
        root=tk.Tk()
        root.withdraw()
        try:
            messagebox.showinfo('ParentPilot',
                'ParentPilot Control Centre is for an adult administrator. '
                'The child desktop and screen-time controls remain available.',
                parent=root)
        finally:
            root.destroy()
        return
    Centre().root.mainloop()


if __name__=='__main__':
    main()
