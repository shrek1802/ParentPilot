#!/usr/bin/python3
"""Offline test of the pinned, scannable ParentPilot signed Android APK QR."""
import hashlib
from pathlib import Path
import sys
import tkinter as tk

sys.path.insert(0, str(Path(__file__).resolve().parent / 'parentpilot'))
from android_download import (
    ANDROID_VERSION, DOWNLOAD_URL, DOWNLOAD_URL_SHA256, QR_MODULES,
    open_apk_download, qr_rows, show_download_qr,
)

assert DOWNLOAD_URL == (
    'https://github.com/shrek1802/ParentPilot/releases/download/'
    'v0.5.0-preview8/ParentPilot-Android-v7.apk'
)
assert 'DEBUG' not in DOWNLOAD_URL.upper()
assert hashlib.sha256(DOWNLOAD_URL.encode()).hexdigest() == DOWNLOAD_URL_SHA256
assert 'signed' in ANDROID_VERSION
rows = qr_rows()
assert len(rows) == QR_MODULES == 49
assert all(len(row) == 49 and set(row) <= {'0', '1'} for row in rows)
# Confirm all four QR quiet zones are present for normal Android cameras.
assert all(bit == '0' for row in rows[:4] + rows[-4:] for bit in row)
assert all(row[:4] == '0000' and row[-4:] == '0000' for row in rows)
# Check finder patterns are QR format, not decorative/random pixels.
assert rows[4][4:11] == '1111111'
assert rows[4][-11:-4] == '1111111'
assert rows[-11][4:11] == '1111111'

visited = []
assert open_apk_download(opener=lambda url: visited.append(url)) is None
assert visited == [DOWNLOAD_URL]

root = tk.Tk()
# A transient Tk dialog must have a mapped adult parent window on X11.
root.geometry('320x220')
root.update()
win = None
try:
    win = show_download_qr(root)
    root.update()
    assert win.winfo_exists()
    assert win.winfo_width() <= win.winfo_screenwidth()
    assert win.winfo_height() <= win.winfo_screenheight()
    canvases = []
    buttons = []
    def visit(widget):
        if isinstance(widget, tk.Canvas):
            canvases.append(widget)
        if isinstance(widget, tk.Button):
            buttons.append(widget)
        for child in widget.winfo_children():
            visit(child)
    visit(win)
    assert len(canvases) == 1
    canvas = canvases[0]
    assert canvas.winfo_width() >= 3 * QR_MODULES
    assert len(canvas.find_all()) > 600  # actual black QR modules rendered
    assert len(buttons) == 2
    labels = [x.cget('text') for x in buttons]
    assert labels == ['Open APK download', 'Copy download link'], labels
    buttons[1].invoke()
    assert win.clipboard_get() == DOWNLOAD_URL
    assert win.winfo_rooty() + win.winfo_height() <= win.winfo_screenheight()
    print('PASS: pinned signed APK QR, native Tk scan popup and buttons at '
          f'{win.winfo_screenwidth()}x{win.winfo_screenheight()}')
finally:
    if win and win.winfo_exists():
        win.destroy()
    root.destroy()
