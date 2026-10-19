#!/usr/bin/python3
"""Virtual-XFCE check: optional games remain usable on a small Dell laptop."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / 'parentpilot'))

import games_gui
games_gui.is_installed = lambda _package: False
app = games_gui.GamesGUI()
root = app.root
try:
    root.update_idletasks()
    assert len(app.checks) == 8
    assert not any(v.get() for v in app.checks.values()), 'No surprise installs'
    assert app.install_btn.winfo_ismapped()
    button_bottom = app.install_btn.winfo_rooty() + app.install_btn.winfo_height()
    window_bottom = root.winfo_rooty() + root.winfo_height()
    assert button_bottom <= window_bottom, (
        root.winfo_screenwidth(), root.winfo_screenheight(), button_bottom, window_bottom,
    )
    assert app.install_btn.winfo_width() > 100
    print('PASS: 8 optional checkboxes, footer visible at ' +
          f'{root.winfo_screenwidth()}x{root.winfo_screenheight()}')
finally:
    root.destroy()
