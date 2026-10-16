#!/usr/bin/python3
"""ParentPilot first-run GUI setup. No account modifications without PolicyKit approval."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox

ROOT = Path('/usr/lib/parentpilot')
MARKER = Path('/etc/max-family-control/config.json')
BG = '#101a30'; CARD = '#1b2a41'; TEXT = '#f8fafc'; SUB = '#b9ccdf'; BLUE = '#38bdf8'; TEAL = '#26c5b4'

class Wizard:
    def __init__(self, autostart=False):
        if MARKER.exists():
            if not autostart: messagebox.showinfo('ParentPilot', 'ParentPilot is already configured. The existing family settings have not been changed.')
            return
        if autostart:
            import grp
            groups = {grp.getgrgid(g).gr_name for g in os.getgroups()}
            if not groups.intersection(('sudo','admin')):
                return
        self.root=tk.Tk()
        self.root.title('ParentPilot — Family Setup')
        self.root.geometry('780x690')
        self.root.minsize(700,610)
        self.root.configure(bg=BG)
        self.root.protocol('WM_DELETE_WINDOW',self.root.destroy)
        self.step=0
        self.installing=False
        self.v={
            'child_name':tk.StringVar(value=''),
            'child_user':tk.StringVar(value=''),
            'child_password':tk.StringVar(value=''),
            'child_password2':tk.StringVar(value=''),
            'parent_pin':tk.StringVar(value=''),
            'parent_pin2':tk.StringVar(value=''),
            'youtube':tk.StringVar(value='kids'),
            'netflix':tk.BooleanVar(value=True),
            'autologin':tk.BooleanVar(value=True),
            'family_filter':tk.BooleanVar(value=True),
        }
        self.main=tk.Frame(self.root,bg=BG)
        self.main.pack(fill='both',expand=True,padx=28,pady=20)
        self.draw()
        self.root.mainloop()

    def lbl(self,parent,txt,size=11,col=TEXT,bold=False,wrap=670,pad=7):
        w=tk.Label(parent,text=txt,bg=parent.cget('bg'),fg=col,
                   font=('DejaVu Sans',size,'bold' if bold else 'normal'),
                   justify='left',anchor='w',wraplength=wrap)
        w.pack(fill='x',anchor='w',pady=(pad,2))
        return w

    def entry(self,parent,title,key,mask=False):
        self.lbl(parent,title,11,SUB,True,pad=10)
        e=tk.Entry(parent,textvariable=self.v[key],font=('DejaVu Sans',12),
                   show='•' if mask else '',relief='flat',bg='#f8fafc',fg='#0f172a',insertbackground='#0f172a')
        e.pack(fill='x',ipady=8)
        return e

    def checked(self,parent,label,key):
        tk.Checkbutton(parent,text=label,variable=self.v[key],bg=parent.cget('bg'),
                       fg=TEXT,activebackground=parent.cget('bg'),selectcolor=BG,
                       activeforeground=TEXT,font=('DejaVu Sans',11),anchor='w').pack(fill='x',pady=8)

    def draw(self):
        for w in self.main.winfo_children():w.destroy()
        head=tk.Frame(self.main,bg=BG);head.pack(fill='x')
        self.photo=None
        try:
            self.photo=tk.PhotoImage(file=str(ROOT/'desktop/assets/parentpilot-icon-128.png'))
            tk.Label(head,image=self.photo,bg=BG).pack(side='left',padx=(0,15))
        except (tk.TclError,OSError):pass
        text=tk.Frame(head,bg=BG);text.pack(side='left',fill='x',expand=True)
        self.lbl(text,'ParentPilot',24,TEXT,True,pad=0)
        self.lbl(text,'FAMILY SETUP  •  STEP '+str(self.step+1)+' OF 4',10,TEAL,True,pad=1)
        card=tk.Frame(self.main,bg=CARD,padx=24,pady=15)
        card.pack(fill='both',expand=True,pady=(18,10))
        self.body=card
        if self.step==0:self.welcome()
        elif self.step==1:self.child()
        elif self.step==2:self.controls()
        else:self.review()
        nav=tk.Frame(self.main,bg=BG);nav.pack(fill='x',pady=(5,0))
        def b(txt,func,colour=BLUE):
            return tk.Button(nav,text=txt,command=func,bg=colour,fg='#082034',borderwidth=0,
                             activebackground=TEAL,activeforeground='#082034',padx=18,pady=10,
                             font=('DejaVu Sans',11,'bold'))
        if self.step:
            b('‹ Back',self.back,'#a8c5d6').pack(side='left')
        if self.step==3:
            b('Install ParentPilot',self.install,TEAL).pack(side='right')
        else:
            b('Continue ›',self.next).pack(side='right')
        self.root.update_idletasks()

    def welcome(self):
        self.lbl(self.body,'Welcome to your family’s new laptop',19,TEXT,True)
        self.lbl(self.body,'A guided setup will create a new child account and prepare a simple, child-friendly Linux Mint desktop.',12,SUB,wrap=620,pad=12)
        for txt in (
            '1   Create the child’s name, Linux username and password',
            '2   Choose your six-digit parent PIN and YouTube options',
            '3   Install safe Chromium shortcuts, YouTube and Netflix',
            '4   Set up the ParentPilot timer and phone discovery',
        ):self.lbl(self.body,txt,12,TEXT,pad=15)
        self.lbl(self.body,'This is for NEW Linux Mint XFCE setups. It will refuse to overwrite an existing ParentPilot/Max Family Control installation.',11,TEAL,wrap=620,pad=25)

    def child(self):
        self.lbl(self.body,'Who will use this laptop?',18,TEXT,True)
        self.lbl(self.body,'Their Linux account will be separate from your administrator account.',11,SUB)
        self.entry(self.body,'Child’s name (shown on their screen)','child_name')
        self.entry(self.body,'Child’s Linux username (lowercase; e.g. max)','child_user')
        self.entry(self.body,'Child account password (at least 8 characters)','child_password',True)
        self.entry(self.body,'Confirm the child account password','child_password2',True)
        self.lbl(self.body,'The child account will not have administrator privileges. This password is separate from your six-digit parent PIN.',10,SUB,pad=15)

    def controls(self):
        self.lbl(self.body,'Parental controls & apps',18,TEXT,True)
        self.entry(self.body,'Create a six-digit parent PIN','parent_pin',True)
        self.entry(self.body,'Confirm parent PIN','parent_pin2',True)
        self.lbl(self.body,'YouTube experience',11,SUB,True,pad=10)
        for value,label in [('kids','YouTube Kids (parent selects age range in YouTube Kids)'),('supervised','YouTube (supervised Google child account required)')]:
            tk.Radiobutton(self.body,text=label,value=value,variable=self.v['youtube'],bg=CARD,fg=TEXT,
                           selectcolor=BG,activeforeground=TEXT,activebackground=CARD,anchor='w',
                           font=('DejaVu Sans',10)).pack(fill='x',pady=2)
        self.checked(self.body,'Add Netflix shortcut (use a Kids profile and lock adult profiles)','netflix')
        self.checked(self.body,'Automatically sign the child in at startup','autologin')
        self.checked(self.body,'Apply family filtering to Chromium on this computer','family_filter')
        self.lbl(self.body,'Chromium policies apply to EVERY Chromium user on this PC (not Google Chrome). Some content filtering can be bypassed; Netflix playback may require Widevine DRM.',10,SUB,pad=9)

    def review(self):
        self.lbl(self.body,'Ready to install',18,TEXT,True)
        self.lbl(self.body,'Child: '+self.v['child_name'].get()+' ('+self.v['child_user'].get()+')',12,TEXT,pad=20)
        self.lbl(self.body,'YouTube: '+('YouTube Kids' if self.v['youtube'].get()=='kids' else 'Supervised YouTube'),11,SUB)
        self.lbl(self.body,'Netflix shortcut: '+('Yes' if self.v['netflix'].get() else 'No'),11,SUB)
        self.lbl(self.body,'Child automatic login: '+('Yes' if self.v['autologin'].get() else 'No'),11,SUB)
        self.lbl(self.body,'Chromium family policy: '+('Enabled' if self.v['family_filter'].get() else 'Not enabled'),11,SUB)
        self.lbl(self.body,'The child’s desktop will have a curated bottom bar with Chromium, YouTube, Files and optionally Netflix. Hidden menu icons are not an OS-level app block.',11,SUB,pad=25)
        self.lbl(self.body,'Installing requires your existing ADMINISTRATOR password in the system authentication popup. The child’s six-digit PIN will never appear in this window.',10,TEAL,pad=17)
        self.result=tk.Text(self.body,height=7,bg='#0d1728',fg=TEXT,insertbackground=TEXT,font=('DejaVu Sans Mono',9),wrap='word')
        self.result.pack(fill='both',expand=True,pady=(15,2))
        self.result.insert('1.0','Ready. Click Install ParentPilot below.\n')
        self.result.configure(state='disabled')

    def check_step(self):
        if self.step==1:
            if not 1<=len(self.v['child_name'].get().strip())<=32:
                return 'Enter the child’s name (1–32 characters).'
            username=self.v['child_user'].get().strip()
            if not re.fullmatch(r'[a-z][a-z0-9_-]{0,30}',username) or username in ('root','maxfamily','nobody'):
                return 'Use a new lowercase Linux username (letters, numbers, hyphens).'
            if not 8<=len(self.v['child_password'].get())<=128:
                return 'The child password needs at least eight characters.'
            if self.v['child_password'].get()!=self.v['child_password2'].get():
                return 'The child passwords do not match.'
        if self.step==2:
            pin=self.v['parent_pin'].get()
            if not re.fullmatch(r'[0-9]{6}',pin) or pin in ('000000','111111','123456'):
                return 'Choose a less obvious six-digit parent PIN.'
            if pin!=self.v['parent_pin2'].get():
                return 'The parent PINs do not match.'
        return None

    def next(self):
        err=self.check_step()
        if err:messagebox.showerror('Check setup details',err);return
        self.step+=1;self.draw()

    def back(self):self.step-=1;self.draw()

    def append(self,txt):
        self.result.configure(state='normal')
        self.result.insert('end',txt+'\n')
        self.result.see('end')
        self.result.configure(state='disabled')

    def install(self):
        if self.installing: return
        self.installing=True
        self.append('Requesting administrator permission…')
        data={k:v.get() for k,v in self.v.items() if k not in ('child_password2','parent_pin2')}
        # Never put secrets in command-line arguments, desktop files or persistent logs.
        def task():
            try:
                proc=subprocess.run(['pkexec','/usr/lib/parentpilot/setup-root','--from-wizard'],
                                    input=json.dumps(data),text=True,capture_output=True,timeout=240)
                success=(proc.returncode==0)
                output=(proc.stdout+'\n'+proc.stderr).strip()
                self.root.after(0,lambda:self.finish(success,output))
            except (OSError,subprocess.TimeoutExpired) as exc:
                self.root.after(0,lambda:self.finish(False,str(exc)))
        threading.Thread(target=task,daemon=True).start()

    def finish(self,success,output):
        self.installing=False
        self.append(output if output else 'The setup did not return a message.')
        if success:
            messagebox.showinfo('ParentPilot ready','Setup complete. Next, sign into the new child account to test its desktop. Your parent dashboard is ready.')
        else:
            messagebox.showerror('Setup was not completed','The installation stopped. Read the details above. ParentPilot will not overwrite an existing installation.')


if __name__=='__main__':
    Wizard(autostart='--autostart' in sys.argv)
