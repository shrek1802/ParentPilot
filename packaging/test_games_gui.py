#!/usr/bin/python3
"""Virtual-XFCE check: optional games remain usable on a small Dell laptop."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / 'parentpilot'))

import games_gui
from unittest.mock import patch
from types import SimpleNamespace

# Preview 15 would silently return here: /etc/max-family-control is 0750
# root:maxfamily and the non-root administrator cannot stat the config
# or managed-install marker. The GUI must not read either protected file.
assert 'parentpilot_configured' not in games_gui.main.__code__.co_names
called = []
with patch.object(games_gui, 'adult_account', return_value=True), \
     patch.object(games_gui, 'GamesGUI',
                  return_value=SimpleNamespace(
                      root=SimpleNamespace(mainloop=lambda: called.append('open')))):
    games_gui.main()
assert called == ['open'], 'Adult user must be able to launch the GUI'

# The child may use installed games but must not change software.
with patch.object(games_gui, 'adult_account', return_value=False), \
     patch.object(games_gui.messagebox, 'showinfo') as info:
    games_gui.main()
    assert info.call_count == 1
    assert 'adult administrator' in info.call_args.args[1]
games_gui.is_installed = lambda _package: False
app = games_gui.GamesGUI()
root = app.root
try:
    root.update_idletasks()
    assert len(app.checks) == 8
    assert list(app.media_checks) == ['kodi']
    assert not app.media_checks['kodi'].get()
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
