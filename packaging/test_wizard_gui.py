#!/usr/bin/env python3
"""Virtual XFCE smoke test for the first-time Family Setup UI.

No account creation, authentication, timers, installations or filesystem writes.
"""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent / 'parentpilot'))
import wizard

for width, height in ((1024, 600), (800, 480)):
    # CI runs each screen size separately under Xvfb.
    pass

compatible = {
    'compatible': True, 'os': 'Linux Mint XFCE', 'errors': [],
    'notices': [], 'lightdm': True, 'session': 'x11', 'desktop': 'XFCE',
}
with patch.object(wizard, 'MARKER', Path('/nonexistent-parentpilot-test-marker')), \
     patch.object(wizard.Wizard, 'load_preflight', return_value=compatible), \
     patch.object(wizard.tk.Tk, 'mainloop', return_value=None):
    gui = wizard.Wizard(autostart=False)
root = gui.root
try:
    root.update_idletasks()
    assert gui.step == 0
    assert len(gui.nav_buttons) == 1
    assert gui.nav_buttons[-1].winfo_ismapped()
    gui.step = 1
    gui.draw()
    assert len(gui.nav_buttons) == 2
    gui.v['child_name'].set('Test child')
    gui.v['child_user'].set('testchild')
    gui.step = 2
    gui.draw()
    assert gui.v['screen_view'].get() is True
    assert 'kodi' in gui.v
    assert not gui.v['kodi'].get()
    assert len(gui.game_choices) == 15
    gui.step = 3
    gui.draw()
    root.update_idletasks()
    assert gui.install_progress.winfo_ismapped()
    assert gui.result.winfo_ismapped()
    for button in gui.nav_buttons:
        assert button.winfo_ismapped(), 'Wizard navigation must stay visible'
        assert button.winfo_rooty() + button.winfo_height() <= (
            root.winfo_rooty() + root.winfo_height()), 'Wizard footer is clipped'
    # No installer is invoked in this check.
    assert not gui.installing
    print('PASS: Family Setup header, steps, Kodi, review, progress and footer at '
          f'{root.winfo_screenwidth()}x{root.winfo_screenheight()}')
finally:
    root.destroy()
