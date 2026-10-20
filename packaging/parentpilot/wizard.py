#!/usr/bin/python3
"""ParentPilot first-run GUI setup. No account modifications without PolicyKit approval."""
import json
import os
import queue
import unicodedata
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from games_catalog import GAMES

ROOT = Path('/usr/lib/parentpilot')
MARKER = Path('/etc/max-family-control/config.json')
BG = '#0f172a'; CARD = '#1e293b'; PANEL = CARD; INSET = '#111d31'
TEXT = '#f8fafc'; SUB = '#cbd5e1'; MUTED = '#94a3b8'
BLUE = '#38bdf8'; TEAL = '#34d399'; RED = '#fca5a5'
STEP_TITLES = ('Welcome', 'Child account', 'Family controls', 'Review')

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
        width=min(self.root.winfo_screenwidth(), max(460, min(780, self.root.winfo_screenwidth()-65)))
        height=min(self.root.winfo_screenheight(), max(340, min(650, self.root.winfo_screenheight()-100)))
        self.root.geometry(f'{width}x{height}')
        self.root.minsize(min(width, 460), min(height, 340))
        self.root.configure(bg=BG)
        self.root.protocol('WM_DELETE_WINDOW',self.close)
        self.step=0
        self.installing=False
        self.install_events=queue.Queue()
        self.preflight=self.load_preflight()
        self._previous_suggestion=''
        self._suggesting_user=False
        self.v={
            'child_name':tk.StringVar(value=''),
            'child_user':tk.StringVar(value=''),
            'child_password':tk.StringVar(value=''),
            'child_password2':tk.StringVar(value=''),
            'parent_pin':tk.StringVar(value=''),
            'parent_pin2':tk.StringVar(value=''),
            'youtube':tk.StringVar(value='kids'),
            'netflix':tk.BooleanVar(value=True),
            'autologin':tk.BooleanVar(value=bool(self.preflight.get('lightdm'))),
            'family_filter':tk.BooleanVar(value=True),
            'screen_view':tk.BooleanVar(value=False),
            'kodi':tk.BooleanVar(value=False),
        }
        # Optional game choices are independent of child account/settings
        # and default OFF to avoid cluttering older laptops.
        self.game_choices = {game_id: tk.BooleanVar(value=False)
                             for game_id, *_ in GAMES}
        self.v['child_name'].trace_add('write', self.suggest_user)
        self.main=tk.Frame(self.root,bg=BG)
        self.main.pack(fill='both',expand=True,padx=14,pady=10)
        self.draw()
        self.root.after(140,self.poll_install)
        self.root.mainloop()

    @staticmethod
    def load_preflight():
        try:
            result=subprocess.run(['/usr/bin/python3','/usr/lib/parentpilot/preflight.py','--json'],
                                  capture_output=True,text=True,timeout=5,check=True)
            state = json.loads(result.stdout)
            # pkexec can clear desktop variables later, but the interactive
            # wizard must verify a real XFCE/X11 parent login first.
            if state.get('session') != 'x11' or 'XFCE' not in state.get('desktop', '').upper():
                state['compatible'] = False
                state.setdefault('errors', []).append('Sign into an XFCE desktop using an X11 session, then reopen ParentPilot Family Setup.')
            return state
        except (OSError, ValueError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
            return {'compatible':False, 'os':'Unknown system', 'errors':['Could not run the compatibility check. Reinstall ParentPilot.'], 'notices':[], 'lightdm':False}

    def suggest_user(self,*_):
        name=unicodedata.normalize('NFKD',self.v['child_name'].get())
        latin=name.encode('ascii','ignore').decode('ascii').lower()
        suggestion=re.sub(r'[^a-z0-9_-]', '', latin)[:30]
        if suggestion and not suggestion[0].isalpha(): suggestion='kid'+suggestion
        if not suggestion: suggestion='child'
        current=self.v['child_user'].get()
        if not current or current==self._previous_suggestion:
            self.v['child_user'].set(suggestion)
        self._previous_suggestion=suggestion

    def refresh_check(self):
        self.preflight=self.load_preflight()
        if not self.preflight.get('lightdm'):
            self.v['autologin'].set(False)
        self.draw()

    def lbl(self,parent,txt,size=11,col=TEXT,bold=False,wrap=670,pad=7):
        w=tk.Label(parent,text=txt,bg=parent.cget('bg'),fg=col,
                   font=('Sans',size,'bold' if bold else 'normal'),
                   justify='left',anchor='w',wraplength=wrap)
        w.pack(fill='x',anchor='w',pady=(pad,2))
        return w

    def entry(self,parent,title,key,mask=False):
        self.lbl(parent,title,11,SUB,True,pad=10)
        e=tk.Entry(parent,textvariable=self.v[key],font=('DejaVu Sans',12),
                   show='•' if mask else '',relief='flat',bg='#e2e8f0',fg='#0f172a',insertbackground='#0f172a',highlightthickness=2,highlightcolor=BLUE)
        e.pack(fill='x',ipady=7)
        return e

    def checked(self,parent,label,key):
        value = self.game_choices[key[5:]] if key.startswith('game:') else self.v[key]
        tk.Checkbutton(parent,text=label,variable=value,bg=parent.cget('bg'),
                       fg=TEXT,activebackground=parent.cget('bg'),selectcolor=BG,
                       activeforeground=TEXT,font=('Sans',10),anchor='w',wraplength=595,justify='left').pack(fill='x',pady=7)

    def draw(self):
        for widget in self.main.winfo_children():
            widget.destroy()
        head=tk.Frame(self.main,bg=BG)
        head.pack(fill='x')
        self.photo=None
        try:
            # The source image is 128px; a 64px header leaves room on a 480px screen.
            self.photo=tk.PhotoImage(file=str(ROOT/'desktop/assets/parentpilot-icon-128.png')).subsample(2,2)
            tk.Label(head,image=self.photo,bg=BG).pack(side='left',padx=(0,10))
        except (tk.TclError,OSError):
            tk.Label(head,text='P',bg=BLUE,fg=BG,font=('Sans',19,'bold'),width=2).pack(side='left',padx=(0,10))
        branding=tk.Frame(head,bg=BG)
        branding.pack(side='left',fill='x',expand=True)
        self.lbl(branding,'ParentPilot',20,TEXT,True,pad=0)
        self.lbl(branding,'FAMILY SETUP  ·  '+STEP_TITLES[self.step].upper(),
                 9,MUTED,True,pad=0)

        steps=tk.Frame(self.main,bg=BG)
        steps.pack(fill='x',pady=(8,4))
        for index,name in enumerate(STEP_TITLES):
            active=index==self.step
            complete=index<self.step
            color=BLUE if active else TEAL if complete else PANEL
            fg=BG if active or complete else SUB
            tk.Label(steps,text=str(index+1)+'  '+name,fg=fg,bg=color,
                     font=('Sans',8,'bold'),padx=6,pady=6,anchor='center').pack(
                         side='left',fill='x',expand=True,padx=(0,4))

        # Navigation is reserved at the bottom before allocating scroll space.
        nav=tk.Frame(self.main,bg=BG)
        nav.pack(side='bottom',fill='x',pady=(8,1))
        self.nav_buttons=[]
        def action(label,func,colour=BLUE):
            button=tk.Button(nav,text=label,command=func,bg=colour,fg=BG,
                             activebackground=TEAL,activeforeground=BG,
                             relief='flat',borderwidth=0,padx=14,pady=8,
                             font=('Sans',10,'bold'))
            self.nav_buttons.append(button)
            return button
        if self.step:
            action('Back',self.back,PANEL).configure(fg=TEXT)
            self.nav_buttons[-1].pack(side='left')
        if self.step==3:
            action('Install ParentPilot',self.install,TEAL).pack(side='right')
        else:
            action('Continue',self.next).pack(side='right')

        card=tk.Frame(self.main,bg=CARD)
        card.pack(fill='both',expand=True,pady=(7,0))
        canvas=tk.Canvas(card,bg=CARD,highlightthickness=0,borderwidth=0)
        bar=ttk.Scrollbar(card,orient='vertical',command=canvas.yview)
        canvas.configure(yscrollcommand=bar.set)
        bar.pack(side='right',fill='y')
        canvas.pack(side='left',fill='both',expand=True)
        body=tk.Frame(canvas,bg=CARD,padx=14,pady=11)
        window=canvas.create_window((0,0),window=body,anchor='nw')
        body.bind('<Configure>',lambda _:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda event:canvas.itemconfigure(window,width=event.width))
        self.body=body
        if self.step==0:
            self.welcome()
        elif self.step==1:
            self.child()
        elif self.step==2:
            self.controls()
        else:
            self.review()
        self.root.update_idletasks()

    def summary_row(self, title, value):
        row=tk.Frame(self.body,bg=INSET,padx=10,pady=7)
        row.pack(fill='x',pady=3)
        tk.Label(row,text=title.upper(),bg=INSET,fg=MUTED,
                 font=('Sans',8,'bold'),anchor='w').pack(fill='x')
        tk.Label(row,text=value,bg=INSET,fg=TEXT,
                 font=('Sans',10),anchor='w',justify='left',
                 wraplength=570).pack(fill='x',pady=(2,0))

    def welcome(self):
        self.lbl(self.body,'Welcome to ParentPilot',19,TEXT,True)
        self.lbl(self.body,'Follow a few simple steps to set up your child’s laptop. You won’t need to type Terminal commands.',11,SUB,wrap=620,pad=6)
        osname=self.preflight.get('os','Unknown Linux')
        allowed=self.preflight.get('compatible',False)
        self.lbl(self.body,('✓ Laptop check passed: ' if allowed else '⚠ Setup cannot continue: ')+osname,
                 12,TEAL if allowed else '#fca5a5',True,pad=15)
        errors=self.preflight.get('errors',[])
        if errors:
            for err in errors[:5]: self.lbl(self.body,'• '+err,10,'#fca5a5',wrap=600,pad=1)
        else:
            self.lbl(self.body,'XFCE desktop, required tools and Chromium were checked. This preview uses X11.',10,SUB,pad=2)
        notices=self.preflight.get('notices',[])
        for msg in notices[:2]: self.lbl(self.body,'Note: '+msg,9,SUB,wrap=610,pad=3)
        tk.Button(self.body,text='Check this laptop again',command=self.refresh_check,bg='#334155',fg=TEXT,
                  activebackground='#475569',font=('DejaVu Sans',10),borderwidth=0,padx=12,pady=6).pack(anchor='w',pady=(12,2))
        self.lbl(self.body,'Next: child account → parental PIN & family apps → final confirmation.',10,TEAL,pad=16)
        self.lbl(self.body,'If you already have a working ParentPilot installation, this setup will not touch it.',10,SUB,pad=3)

    def child(self):
        self.lbl(self.body,'Who will use this laptop?',18,TEXT,True)
        self.lbl(self.body,'Their Linux account will be separate from your administrator account.',11,SUB)
        self.entry(self.body,'Child’s name (shown on their screen)','child_name')
        self.entry(self.body,'Suggested child login name (you can change it)','child_user')
        self.entry(self.body,'Child account password (at least 6 characters)','child_password',True)
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
        if self.preflight.get('lightdm'):
            self.checked(self.body,'Automatically sign the child in at startup (LightDM)','autologin')
        else:
            self.v['autologin'].set(False)
            self.lbl(self.body,'Automatic login is unavailable without LightDM. Your child can still sign in normally.',10,SUB,pad=7)
        self.checked(self.body,'Apply family filtering to Chromium on this computer','family_filter')
        self.lbl(self.body,'Filtering policies apply to ALL Chromium accounts on this computer, including the parent. YouTube and Netflix age/profile settings must be set up separately.',10,SUB,pad=7)
        self.checked(self.body,"Optional: let a parent request a picture of the child's screen",'screen_view')
        self.lbl(self.body,'OFF by default. If enabled, a signed-in parent can ask for one screen picture without the child approving each request. The child sees a clear on-screen viewing notice each time. No hidden capture, live video or recording. Each picture expires after 30 seconds.',10,SUB,pad=7)
        self.lbl(self.body, 'Optional free games (tick any you want)', 12, TEXT, True, pad=18)
        self.lbl(self.body,
                 'Suitable for many older PCs including the Dell Inspiron N5110. '
                 'No games are selected by default. Downloads need internet access. '
                 'They appear in the normal Linux applications menu.',
                 10, SUB, wrap=625, pad=2)
        last_category = ''
        for game_id, title, category, description, package in GAMES:
            if category != last_category:
                last_category = category
                self.lbl(self.body, category.upper(), 10, TEAL, True, pad=10)
            self.checked(self.body, title + ' — ' + description,
                         'game:' + game_id)
        self.lbl(self.body, 'Media Players', 12, TEXT, True, pad=18)
        self.checked(self.body, 'Kodi Media Centre — local videos, films, cartoons and music', 'kodi')
        self.lbl(self.body, 'Kodi is optional and uses the official Linux Mint/Ubuntu APT package. '
                 'VLC stays installed. No extra Kodi repositories or streaming add-ons are added.',
                 10, SUB, wrap=625, pad=2)

    def review(self):
        self.lbl(self.body,'Ready to install',18,TEXT,True)
        self.lbl(self.body,'Confirm your settings before approving the administrator prompt.',
                 10,SUB,pad=4)
        self.summary_row('Child account',
                         self.v['child_name'].get()+' ('+self.v['child_user'].get()+')')
        self.summary_row('YouTube',
                         'YouTube Kids' if self.v['youtube'].get()=='kids' else 'Supervised YouTube')
        self.summary_row('Netflix',
                         'Shortcut selected' if self.v['netflix'].get() else 'Not selected')
        self.summary_row('Automatic login',
                         'Enabled' if self.v['autologin'].get() else 'Off')
        self.summary_row('Chromium family policy',
                         'Enabled' if self.v['family_filter'].get() else 'Off')
        self.summary_row('Parent screen picture requests',
                         'Parent-authorised with a child notice' if self.v['screen_view'].get() else 'Off')
        chosen=[title for game_id,title,*_ in GAMES if self.game_choices[game_id].get()]
        self.summary_row('Optional games',', '.join(chosen) if chosen else 'None selected')
        self.summary_row('Kodi Media Centre',
                         'Install from official APT' if self.v['kodi'].get() else 'Not selected')
        self.lbl(self.body,'The normal Linux Mint desktop and VLC remain available. '
                 'Installing requires your existing administrator password. '
                 'It does not display or store your child password or parent PIN in the log.',
                 10,SUB,wrap=570,pad=8)
        self.install_status=tk.StringVar(value='Ready for administrator approval')
        self.lbl(self.body,'SETUP PROGRESS',10,BLUE,True,pad=12)
        tk.Label(self.body,textvariable=self.install_status,bg=CARD,fg=TEXT,
                 font=('Sans',10),anchor='w',justify='left').pack(fill='x')
        style=ttk.Style(self.root)
        style.configure('Setup.Horizontal.TProgressbar',background=BLUE,
                        troughcolor='#334155',thickness=8)
        self.install_progress=ttk.Progressbar(
            self.body,mode='indeterminate',style='Setup.Horizontal.TProgressbar')
        self.install_progress.pack(fill='x',pady=(6,8))
        self.result=tk.Text(self.body,height=4,bg=INSET,fg=SUB,
                            insertbackground=TEXT,font=('DejaVu Sans Mono',9),
                            wrap='word',padx=8,pady=6,relief='flat')
        self.result.pack(fill='both',expand=True,pady=(2,4))
        self.result.insert('1.0','Nothing has been installed yet.\n')
        self.result.configure(state='disabled')

    def check_step(self):
        if self.step==1:
            if not 1<=len(self.v['child_name'].get().strip())<=32:
                return 'Enter the child’s name (1–32 characters).'
            username=self.v['child_user'].get().strip()
            if not re.fullmatch(r'[a-z][a-z0-9_-]{0,30}',username) or username in ('root','maxfamily','nobody'):
                return 'Use a new lowercase Linux username (letters, numbers, hyphens).'
            if not 6<=len(self.v['child_password'].get())<=128:
                return 'The child password needs at least six characters.'
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
        if self.installing: return
        if self.step == 0 and not self.preflight.get('compatible',False):
            messagebox.showerror('Laptop not ready','See the reasons above. Nothing has been changed.');return
        err=self.check_step()
        if err:messagebox.showerror('Check setup details',err);return
        self.step+=1;self.draw()

    def back(self):
        if self.installing: return
        self.step-=1;self.draw()

    def append(self,txt):
        self.result.configure(state='normal')
        self.result.insert('end',txt+'\n')
        self.result.see('end')
        self.result.configure(state='disabled')

    def install(self):
        if self.installing:
            return
        if not messagebox.askyesno(
            'Confirm ParentPilot setup',
            'Create the new child account and install the timer, family shortcuts '
            'and Wi-Fi discovery?\n\nYour existing adult account will not be changed.',
            parent=self.root):
            return
        self.installing=True
        self.append('Waiting for administrator approval…')
        self.install_status.set('Waiting for your Linux administrator password…')
        self.install_progress.start(12)
        for button in self.nav_buttons:
            button.configure(state='disabled')
        data={k:v.get() for k,v in self.v.items()
              if k not in ('child_password2','parent_pin2')}
        data['games']=[key for key,var in self.game_choices.items() if var.get()]
        # Sensitive values are sent only over the child's creation request
        # stdin pipe, never command-line arguments, release notes or logs.
        def task():
            try:
                with subprocess.Popen(
                    ['pkexec','/usr/lib/parentpilot/setup-root','--from-wizard'],
                    stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,text=True,errors='replace',
                    bufsize=1,
                ) as proc:
                    proc.stdin.write(json.dumps(data))
                    proc.stdin.close()
                    for line in proc.stdout:
                        self.install_events.put(('line',line.rstrip('\r\n')))
                    code=proc.wait()
                self.install_events.put(('done',code))
            except (OSError,ValueError,subprocess.SubprocessError) as exc:
                self.install_events.put(('error',str(exc)))
        threading.Thread(target=task,daemon=True).start()

    def poll_install(self):
        try:
            while True:
                kind,value=self.install_events.get_nowait()
                if kind=='line':
                    # The privileged installer only logs fixed operation names
                    # and APT progress; it never prints passwords or PINs.
                    if value:
                        self.append(value)
                        if value.startswith('SETUP_PROGRESS:'):
                            self.install_status.set(value.split(':',1)[1][:110])
                elif kind=='done':
                    self.finish(value==0,
                                '' if value==0 else 'Setup failed or administrator approval was cancelled.')
                elif kind=='error':
                    self.finish(False,value)
        except queue.Empty:
            pass
        self.root.after(150,self.poll_install)

    def finish(self,success,output):
        self.installing=False
        self.install_progress.stop()
        if output:
            self.append(output)
        if success:
            self.install_status.set('Family setup completed')
            self.append('Success. The child account is ready for its next sign-in.')
            messagebox.showinfo('ParentPilot ready',
                'Setup complete!\n\nSign into the new child account and check the timer. '
                'Connect the phone and laptop to the same Wi-Fi to use the '
                'ParentPilot Android app. Your adult account remains unchanged.',
                parent=self.root)
        else:
            self.install_status.set('Setup did not complete — see details')
            for button in self.nav_buttons:
                button.configure(state='normal')
            messagebox.showerror('Setup was not completed',
                'The installation stopped. Review the messages in the setup window. '
                'ParentPilot will not overwrite an existing installation.',
                parent=self.root)

    def close(self):
        if self.installing:
            messagebox.showwarning(
                'Family setup in progress',
                'Please keep this window open until setup finishes. '
                'Closing it during account creation could interrupt the installation.',
                parent=self.root)
        else:
            self.root.destroy()


if __name__=='__main__':
    Wizard(autostart='--autostart' in sys.argv)
