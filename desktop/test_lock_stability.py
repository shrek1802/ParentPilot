#!/usr/bin/env python3
"""Headless lock-stability regression: no real desktop, timer, PIN or users touched."""
import max_desktop as desktop
from parentpilot_lock_media import LockGuard

class Field:
    def __init__(self):
        self.changes = []
    def configure(self, **kwargs):
        self.changes.append(kwargs)

class Guard:
    def __init__(self):
        self.calls = []
    def enforce(self, overlay):
        self.calls.append(('enforce', overlay))
    def release(self):
        self.calls.append(('release', None))

class Root:
    def after(self, delay, callback):
        pass

def fake_ui(previous, overlay):
    ui = object.__new__(desktop.MaxUI)
    ui.root = Root()
    ui.overlay = overlay
    ui.widget = None
    ui.last_state = previous
    ui.offline = False
    ui.guard = Guard()
    ui.connection_warning = Field()
    ui.title_label = Field()
    ui.description = Field()
    ui.indicator = Field()
    calls = []
    ui.hide_widget = lambda: calls.append('hide_widget')
    ui.hide_overlay = lambda: calls.append('hide_overlay')
    ui.create_overlay = lambda: calls.append('create_overlay')
    ui.create_widget = lambda: calls.append('create_widget')
    return ui, calls

def offline():
    raise ConnectionError('test service unavailable')

saved_request = desktop.request_state
try:
    desktop.request_state = offline
    locked = object()
    ui, calls = fake_ui({'allowed': False, 'paused': True}, locked)
    ui.refresh()
    assert 'hide_overlay' not in calls and ui.overlay is locked
    assert ui.last_state == {'allowed': False, 'paused': True}
    assert ui.guard.calls[0] == ('enforce', locked)
    assert 'Screen stays paused' in ui.connection_warning.changes[-1]['text']
    ui.refresh()
    assert 'hide_overlay' not in calls
    print('PASS: transient server failures never destroy an established lock')

    ui, calls = fake_ui({'allowed': True, 'paused': False}, None)
    ui.refresh()
    assert 'hide_overlay' in calls and 'create_widget' in calls
    print('PASS: an already unlocked desktop retains service-loss recovery path')

    desktop.request_state = lambda: {
        'allowed': True, 'remaining_seconds': 500,
        'unlimited': False, 'paused': False, 'screen_enabled': False
    }
    ui, calls = fake_ui({'allowed': False, 'paused': True}, locked)
    ui.refresh()
    assert 'hide_overlay' in calls and ui.last_state['allowed']
    print('PASS: normal parent-approved resume still works')

    class Overlay:
        def winfo_exists(self): return True
        def winfo_id(self): return 42
        def lift(self): raise AssertionError('Do not repeatedly Tk-lift')

    class X11:
        def __init__(self): self.calls = []
        def XRaiseWindow(self, *args): self.calls.append('raise')
        def XFlush(self, *args): self.calls.append('flush')

    guard = object.__new__(LockGuard)
    guard._x11 = X11()
    guard._display = object()
    guard._raise_without_focus(Overlay())
    assert guard._x11.calls == ['raise', 'flush']
    print('PASS: X11 overlay raise does not call Tk lift repeatedly')
    # New XFCE lock must be a WM-managed fullscreen window. Older
    # override-redirect popup could only accept PIN input after Alt+Tab.
    import inspect
    create_source = inspect.getsource(desktop.MaxUI.create_overlay)
    assert "overrideredirect(True)" not in create_source
    assert "attributes('-fullscreen', True)" in create_source

    class FocusWindow:
        def __init__(self):
            self.actions = []
            self.callbacks = []
        def after(self, delay, callback):
            self.callbacks.append((delay, callback))
        def winfo_exists(self): return True
        def lift(self): self.actions.append('lift')
        def focus_force(self): self.actions.append('focus')

    class PinField:
        def __init__(self, window):
            self.window = window
            self.focused = False
        def focus_get(self): return self if self.focused else None
        def focus_force(self):
            self.focused = True
            self.window.actions.append('pin-focus')
        def icursor(self, where): pass

    ui = object.__new__(desktop.MaxUI)
    ui.overlay = FocusWindow()
    ui.password = PinField(ui.overlay)
    ui._focus_parent_pin()
    assert [delay for delay, _ in ui.overlay.callbacks] == [30, 180, 600]
    for _, callback in ui.overlay.callbacks:
        callback()
    assert ui.password.focused
    assert ui.overlay.actions == ['lift', 'focus', 'pin-focus']
    print('PASS: managed fullscreen lock requests PIN focus once without repeated steals')

finally:
    desktop.request_state = saved_request
