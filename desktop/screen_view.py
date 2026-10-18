#!/usr/bin/env python3
"""Capture one consented X11 desktop image in the child's *own* graphical session.

No daemon, no saved files, no camera or microphone, no recording, and no
automatic/periodic capture. This module is imported only after the child
clicks "Share one picture" in the visible ParentPilot dialog.
"""
from __future__ import annotations


def capture_jpeg(max_width=1280, quality=65):
    import gi
    gi.require_version('Gdk', '3.0')
    gi.require_version('GdkPixbuf', '2.0')
    from gi.repository import Gdk, GdkPixbuf

    display = Gdk.Display.get_default()
    if display is None or display.get_name().lower().startswith('wayland'):
        raise RuntimeError('Screen preview needs the child to be logged into XFCE on X11.')
    window = Gdk.get_default_root_window()
    if window is None:
        raise RuntimeError('Could not locate the child desktop.')
    width, height = window.get_width(), window.get_height()
    if not (0 < width <= 16384 and 0 < height <= 16384):
        raise RuntimeError('Invalid child display size.')
    picture = Gdk.pixbuf_get_from_window(window, 0, 0, width, height)
    if picture is None:
        raise RuntimeError('Screen capture was refused by the display.')
    if width > max_width:
        new_height = max(1, round(height * max_width / width))
        picture = picture.scale_simple(max_width, new_height, GdkPixbuf.InterpType.BILINEAR)
    ok, data = picture.save_to_bufferv('jpeg', ['quality'], [str(quality)])
    if not ok:
        raise RuntimeError('Could not encode the one-time screen preview.')
    return bytes(data)
