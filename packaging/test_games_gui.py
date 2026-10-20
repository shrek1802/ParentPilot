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
    assert app.progress.winfo_ismapped(), 'Live progress bar must always be visible'
    assert not app.activity_bar.winfo_ismapped(), 'Busy indicator is initially stopped'
    app.media_checks['kodi'].set(True)
    assert app.selection.get() == '1 app selected'
    app.start_progress(2)
    root.update_idletasks()
    assert app.running and app.total == 2
    assert app.activity_bar.winfo_ismapped()
    assert app.install_btn.cget('state') == 'disabled'
    assert float(app.progress['value']) == 0
    app.process_line(games_gui.EVENT_PREFIX + '{"event":"checking","id":"supertux","name":"SuperTux"}')
    assert app.status.get() == 'Checking SuperTux'
    app.process_line(games_gui.EVENT_PREFIX + '{"event":"installing","id":"supertux","name":"SuperTux"}')
    assert 'Installing SuperTux' in app.status.get()
    app.process_line(games_gui.EVENT_PREFIX + '{"event":"installed","id":"supertux","name":"SuperTux"}')
    assert float(app.progress['value']) == 1
    assert '1 of 2' in app.progress_info.get()
    app.process_line(games_gui.EVENT_PREFIX + '{"event":"failed","id":"kodi","name":"Kodi Media Centre"}')
    assert float(app.progress['value']) == 2
    with patch.object(games_gui.messagebox, 'showwarning'):
        app.finish(1)
    assert not app.running
    assert app.install_btn.cget('state') == 'normal'
    assert 'partially failed' in app.status.get()
    app.root.update_idletasks()
    # Optional details appear when errors occur. All controls still fit.
    assert app.detail.winfo_ismapped()
    print('PASS: visible progress, live per-app milestones, failure recovery')
    print('PASS: 8 optional checkboxes, footer visible at ' +
          f'{root.winfo_screenwidth()}x{root.winfo_screenheight()}')
finally:
    root.destroy()
