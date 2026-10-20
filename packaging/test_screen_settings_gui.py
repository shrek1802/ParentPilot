#!/usr/bin/python3
"""Xvfb smoke test: adult settings UI does not touch child accounts/services."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent / 'parentpilot'))
import screen_settings_gui as gui

app=gui.ScreenSettings()
root=app.root
try:
    root.update_idletasks()
    for button in (app.enable_button,app.disable_button,app.check_button):
        assert button.winfo_ismapped(), 'Screen permission button hidden'
        assert button.winfo_rooty()+button.winfo_height() <= root.winfo_rooty()+root.winfo_height(), 'Footer clipped'
    assert not app.busy and app.enabled is None
    app.update_busy(True)
    assert app.enable_button.cget('state') == 'disabled'
    app.events.put((0,'SCREEN_PICTURES:enabled\n',''))
    app.poll()
    assert app.enabled is True and app.status.get()=='Enabled'
    assert app.enable_button.cget('state')=='normal'
    app.events.put((0,'SCREEN_PICTURES:disabled\n',''))
    app.poll()
    assert app.enabled is False and app.status.get()=='Disabled'
    print('PASS: adult screen settings actions and state at '
          f'{root.winfo_screenwidth()}x{root.winfo_screenheight()}')
finally:
    root.destroy()
