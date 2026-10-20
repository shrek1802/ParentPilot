#!/usr/bin/env python3
"""Headless Control Centre integration smoke test on real small XFCE dimensions."""
from pathlib import Path
import sys
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent/'parentpilot'))
import control_centre as pp

with patch.object(pp,'installed_version',return_value='0.5.0~preview24'),\
     patch.object(pp.subprocess,'run',return_value=type('Done',(),{'returncode':0,'stdout':'0.5.0~preview24'})()):
    app=pp.Centre()
root=app.root
try:
    root.update_idletasks()
    assert len(app.tabs.tabs())==5
    assert [app.tabs.tab(x,'text') for x in app.tabs.tabs()] == [
        'Home','Updates','Games & Media','Security','Help']
    assert app.updates.embedded and app.games.embedded
    assert app.updates.root.winfo_toplevel() == root
    assert app.games.root.winfo_toplevel() == root
    assert app.security.frame.winfo_toplevel() == root
    assert not app.security.busy
    for page in app.tabs.tabs():
        app.tabs.select(page)
        root.update_idletasks()
    assert app.security.action_button.winfo_exists()
    assert app.games.install_btn.winfo_exists()
    assert app.updates.install_button.winfo_exists()
    app.security.tabs.select(0)
    app.tabs.select(3)
    root.update_idletasks()
    assert app.security.action_button.winfo_ismapped(), 'Security action hidden'
    assert app.security.action_button.cget('text') == 'Change parent PIN'
    app.security.tabs.select(1)
    app.security.sync_action()
    root.update_idletasks()
    assert app.security.action_button.winfo_ismapped(), 'Child password action hidden'
    assert app.security.action_button.cget('text') == 'Change child password'
    assert (app.security.action_button.winfo_rooty() +
            app.security.action_button.winfo_height() <=
            root.winfo_rooty()+root.winfo_height()), 'Security button clipped'
    # Simulate a running operation without performing privileged work.
    app.games.running=True
    with patch.object(pp.messagebox,'showwarning') as warned:
        app.close()
        warned.assert_called_once()
    app.games.running=False
    print('PASS: five embedded adult tabs, password actions and close guards at '
          f'{root.winfo_screenwidth()}x{root.winfo_screenheight()}')
finally:
    root.destroy()
