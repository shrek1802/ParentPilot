#!/usr/bin/env python3
"""Best-effort XFCE/X11 lock-window + audio helper (no timer/PIN changes).

Child-session only. The pause action is intentionally never reversed: the parent
approves screen time; the child decides whether to resume YouTube afterwards.
Audio mute state is remembered through a UI crash/relaunch so it is not lost.
"""
import ctypes
import tkinter as tk
import ctypes.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time

_STATE = Path.home() / '.local' / 'state' / 'parentpilot' / 'audio-before-lock.json'
_MPRIS_NAME = re.compile(r'^org\.mpris\.MediaPlayer2\.[A-Za-z0-9_.-]+$')


def _call(argv, timeout=1.2):
    try:
        return subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None


def _write_json(data):
    _STATE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=_STATE.parent, prefix='.mute-', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(name, 0o600)
        os.replace(name, _STATE)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _read_json():
    try:
        obj = json.loads(_STATE.read_text(encoding='utf8'))
        return obj if isinstance(obj, dict) and obj.get('version') == 1 else None
    except (OSError, ValueError, TypeError):
        return None


def _pulse_sinks():
    if not shutil.which('pactl'):
        return None
    r = _call(['pactl', 'list', 'short', 'sinks'])
    if not r or r.returncode != 0:
        return None
    return [row.split()[1] for row in r.stdout.splitlines()
            if len(row.split()) >= 2 and '/' not in row.split()[1]]


def _pulse_is_muted(sink):
    r = _call(['pactl', 'get-sink-mute', sink])
    if not r or r.returncode != 0:
        return None
    if re.search(r'\bno\b', r.stdout, re.I):
        return False
    if re.search(r'\byes\b', r.stdout, re.I):
        return True
    return None


def _pulse_set_mute(sink, muted):
    r = _call(['pactl', 'set-sink-mute', sink, '1' if muted else '0'])
    return r is not None and r.returncode == 0


def _wireplumber_muted():
    if not shutil.which('wpctl'):
        return None
    r = _call(['wpctl', 'get-volume', '@DEFAULT_AUDIO_SINK@'])
    if r is None or r.returncode != 0:
        return None
    return '[MUTED]' in r.stdout


def _wireplumber_set_mute(muted):
    r = _call(['wpctl', 'set-mute', '@DEFAULT_AUDIO_SINK@', '1' if muted else '0'])
    return r is not None and r.returncode == 0


class LockGuard:
    def __init__(self):
        self._last_pause = 0.0
        self._tick_id = None
        self._locked_overlay = None
        self._x11 = None
        self._display = None
        # ctypes binding is optional: audio protection still works without X11.
        try:
            lib = ctypes.util.find_library('X11')
            if lib:
                self._x11 = ctypes.CDLL(lib)
                self._x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
                self._x11.XOpenDisplay.restype = ctypes.c_void_p
                self._x11.XRaiseWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
                self._x11.XRaiseWindow.restype = ctypes.c_int
                self._x11.XFlush.argtypes = [ctypes.c_void_p]
                self._display = self._x11.XOpenDisplay(None)
        except (OSError, AttributeError, TypeError):
            self._x11 = None
            self._display = None

    def _raise_without_focus(self, overlay):
        # The actual parent PIN window IS the full-screen cover: no separate
        # top-level mask can ever obscure its buttons. Tk lift does not focus.
        try:
            if overlay is not None and overlay.winfo_exists():
                overlay.lift()
        except (tk.TclError, RuntimeError):
            pass

    def _raise_tick(self):
        self._tick_id = None
        overlay = self._locked_overlay
        if overlay is None:
            return
        try:
            if overlay.winfo_exists():
                self._raise_without_focus(overlay)
                self._tick_id = overlay.after(350, self._raise_tick)
        except (tk.TclError, RuntimeError):
            self._tick_id = None

    def _start_raise(self, overlay):
        if self._locked_overlay is overlay and self._tick_id is not None:
            return
        self._stop_raise()
        self._locked_overlay = overlay
        self._raise_tick()

    def _stop_raise(self):
        if self._tick_id is not None and self._locked_overlay is not None:
            try:
                self._locked_overlay.after_cancel(self._tick_id)
            except (tk.TclError, RuntimeError):
                pass
        self._tick_id = None
        self._locked_overlay = None

    def _pause_media(self):
        # No extra packages needed on typical XFCE sessions. Session DBus is
        # scoped to Max, so other logged-in Linux users' media isn't targeted.
        if shutil.which('playerctl'):
            _call(['playerctl', '--all-players', 'pause'])
            return
        if not shutil.which('dbus-send'):
            return
        r = _call(['dbus-send', '--session', '--print-reply',
                   '--dest=org.freedesktop.DBus', '/org/freedesktop/DBus',
                   'org.freedesktop.DBus.ListNames'])
        if r is None or r.returncode != 0:
            return
        for name in re.findall(r'string "([^"]+)"', r.stdout):
            if _MPRIS_NAME.fullmatch(name):
                _call(['dbus-send', '--session', '--type=method_call',
                       '--dest=' + name, '/org/mpris/MediaPlayer2',
                       'org.mpris.MediaPlayer2.Player.Pause'])

    def _mute_audio(self):
        # First call records the original mute states. Repeated calls catch newly
        # plugged-in audio outputs and any user attempt to unmute while locked.
        sinks = _pulse_sinks()
        prior = _read_json()
        if sinks is not None and sinks:
            if prior is not None and prior.get('backend') != 'pactl':
                return  # Avoid clobbering a pending previous-backend restore.
            if prior is None:
                prior = {'version': 1, 'backend': 'pactl', 'sinks': {}}
            changed = False
            for sink in sinks:
                original = _pulse_is_muted(sink)
                if original is None:
                    continue
                if sink not in prior['sinks']:
                    prior['sinks'][sink] = original
                    changed = True
            if changed:
                _write_json(prior)  # Persist BEFORE muting; survives crash.
            for sink in sinks:
                if sink in prior['sinks']:
                    _pulse_set_mute(sink, True)
            return
        original = _wireplumber_muted()
        if original is None:
            return
        if prior is None:
            prior = {'version': 1, 'backend': 'wpctl', 'muted': original}
            _write_json(prior)
        if prior.get('backend') == 'wpctl':
            _wireplumber_set_mute(True)

    def release(self):
        self._stop_raise()
        prior = _read_json()
        if prior is None:
            return
        completed = True
        if prior.get('backend') == 'pactl':
            current = _pulse_sinks()
            if current is None:
                return  # Keep backup if audio service isn't running yet.
            for sink, muted in prior.get('sinks', {}).items():
                if sink in current and not _pulse_set_mute(sink, bool(muted)):
                    completed = False
        elif prior.get('backend') == 'wpctl':
            completed = _wireplumber_set_mute(bool(prior.get('muted')))
        if completed:
            try:
                _STATE.unlink(missing_ok=True)
            except OSError:
                pass

    def enforce(self, overlay):
        # Raise ONLY the UI-owned fullscreen toplevel (not an extra blank mask).
        self._start_raise(overlay)
        self._mute_audio()
        now = time.monotonic()
        if now - self._last_pause >= 6.0:
            self._last_pause = now
            self._pause_media()
