#!/usr/bin/env python3
"""Headless-X11 check that ParentPilot Updates controls fit a short XFCE screen.

Run under xvfb-run on CI. Creates no users, services, releases or installs.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / 'parentpilot'))
import updates_gui

for sw, sh in [(1024, 600), (800, 480), (1366, 768)]:
    w, h = updates_gui.fit_update_window(sw, sh)
    assert 250 <= w <= sw, (sw, w)
    assert 230 <= h <= sh, (sh, h)

# Use actual Tk geometry in virtual X11, no internet check or mainloop required.
updates_gui.installed_version = lambda: '0.5.0~preview9'
root_factory = updates_gui.tk.Tk


def high_dpi_tk():
    root = root_factory()
    root.tk.call('tk', 'scaling', 1.5)
    return root


updates_gui.tk.Tk = high_dpi_tk
ui = updates_gui.UpdatesGUI()
root = ui.root
try:
    root.update_idletasks()
    widgets = [
        ('Check for updates', ui.check_button),
        ('Install update', ui.install_button),
        ('Release notes', ui.notes),
        ('Update channel', ui.channel_select),
    ]
    for name, widget in widgets:
        assert widget.winfo_ismapped(), (name, 'not visible')
        left = widget.winfo_rootx() - root.winfo_rootx()
        top = widget.winfo_rooty() - root.winfo_rooty()
        width = widget.winfo_width()
        height = widget.winfo_height()
        assert left >= 0 and top >= 0, (name, left, top)
        assert left + width <= root.winfo_width(), (name, left, width, root.winfo_width())
        assert top + height <= root.winfo_height(), (name, top, height, root.winfo_height())
    assert ui.progress.winfo_ismapped()
    assert ui.notes_tab in ui.tabs.tabs() or str(ui.notes_tab) in ui.tabs.tabs()
    ui.set_busy(True, installing=True)
    assert ui.installing and ui.busy
    assert str(ui.install_button.cget('state')) == 'disabled'
    ui.events.put(('phase', 'verify', None))
    ui.events.put(('activity', 'Verified release metadata', None))
    ui.process_events()
    assert ui.status.get() == 'Checking release'
    assert 'Step 1 of 7' in ui.phase.get()
    assert 'Verified release metadata' in ui.activity.get('1.0', 'end')
    ui.events.put(('phase', 'health', None))
    ui.process_events()
    assert 'Step 7 of 7' in ui.phase.get()
    assert ui.status.get() == 'Checking everything works'
    # A completed worker must stop the spinner and report the final result.
    ui.events.put((ui.installed, (0, 'SUCCESS'), None))
    ui.process_events()
    assert not ui.busy and not ui.installing
    assert ui.status.get() == 'Update installed successfully'
    assert 'Sign the child back in' in ui.phase.get()
    assert 'installer completed' in ui.activity.get('1.0', 'end')
    ui.events.put(('phase', 'restore', None))
    ui.process_events()
    assert ui.status.get() == 'Restoring from backup'
    assert ui.tabs.select() == str(ui.activity_tab)
    print('PASS: Live milestones, activity log, spinner and final result')
    print('PASS: updater controls remain inside the window on 
          f'{root.winfo_screenwidth()}x{root.winfo_screenheight()} at 1.5x font scaling')
finally:
    root.destroy()
