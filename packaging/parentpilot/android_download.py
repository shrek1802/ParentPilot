#!/usr/bin/python3
"""Adult-only QR for the verified, permanently signed ParentPilot Android APK.

This QR links to an existing official public GitHub Release asset. Drawn with
native Tkinter: no extra Python/QR/Image dependency on older Mint laptops.
Never show private laptop addresses, parent PINs, tokens, or hidden debug APKs.
"""
import base64
import hashlib
import tkinter as tk
import webbrowser
import zlib

DOWNLOAD_URL = (
    'https://github.com/shrek1802/ParentPilot/releases/download/'
    'v0.5.0-preview8/ParentPilot-Android-v7.apk'
)
ANDROID_VERSION = '0.4.2 (permanently signed v7)'
DOWNLOAD_URL_SHA256 = 'ac5f4b4a262e2bac396e5f016ca2130322da852b09bb547733a0221393fd25d9'
QR_MODULES = 49  # Version 6 QR, error correction M, four-module quiet zone
# Matrix for DOWNLOAD_URL; base64-encoded zlib-compressed 49x49 QR pixels.
QR_BITS = (
    'eNpjYMABGP/8WKRdz9CkvX6XQkOs8IX26w56fTVHVi8Qd73zLvUCh26qdhUH+9fQ0NA/DAzK'
    '36IYGHVtsycsYLCc+I7nG0No+gnW7Q3KYa7beA7Ih+7YuW8Dn9QRrwgB1umqeaoxjOKPo2'
    'OuMdxbtttem8Gxon3FhgbmW1MZQh30zSPPiiawvPozTy6As8PNa10Eq0jikvgKxjKm3Ste'
    'MMReuL36MMNVf7tmFobQCuflJQcUPSO3bkngfCX9aYIBu3y32HUJ1vsbLijkMFz5/GtyAG'
    'PoOvvvvxkY5ko862qoN1jlHMKgsGnjn6QD4h6LYuczcK9IXOW3gfVyUFRGDhPHqu/fXBj/'
    'muVq7sIVJAwAkgVpdg=='
)
QR_BITS_SHA256 = 'c1501ad9827672a81ff367bc9de583fdb0b3b4fdecbcf15784b6668c7b45c30d'


def qr_rows():
    """Return integrity-checked immutable 49 x 49 matrix of QR modules."""
    if hashlib.sha256(DOWNLOAD_URL.encode('utf-8')).hexdigest() != DOWNLOAD_URL_SHA256:
        raise ValueError('Signed Android APK URL changed: QR needs regenerating')
    packed = zlib.decompress(base64.b64decode(QR_BITS, validate=True))
    bits = format(int.from_bytes(packed, 'big'), 'b').zfill(QR_MODULES ** 2)
    if len(bits) != QR_MODULES ** 2:
        raise ValueError('Invalid signed Android QR dimensions')
    if hashlib.sha256(bits.encode('ascii')).hexdigest() != QR_BITS_SHA256:
        raise ValueError('Android APK QR matrix integrity check failed')
    return tuple(bits[i:i+QR_MODULES] for i in range(0, len(bits), QR_MODULES))


def open_apk_download(opener=webbrowser.open):
    """Run only on a parent click, never from startup or an auto-refresh."""
    return opener(DOWNLOAD_URL)


def show_download_qr(parent):
    """Show a large, scannable QR without requiring a third-party library."""
    rows = qr_rows()
    win = tk.Toplevel(parent)
    win.title('ParentPilot | Install Android App')
    win.configure(bg='#0f172a')
    win.transient(parent)
    # Keep footer and QR fully visible on older 800x480/1024x600 XFCE screens.
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    width = min(480, max(300, sw - 70))
    height = min(570, max(320, sh - 85))
    win.geometry(f'{width}x{height}+{max(0, (sw-width)//2)}+{max(0, (sh-height)//2)}')
    win.minsize(min(300, width), min(320, height))

    tk.Label(win, text='Install ParentPilot on Android',
             bg='#0f172a', fg='#f8fafc',
             font=('Sans', 15, 'bold')).pack(pady=(10, 0))
    tk.Label(win, text='Scan this code with the phone camera',
             bg='#0f172a', fg='#cbd5e1',
             font=('Sans', 9)).pack(pady=(2, 8))
    # The encoded QR includes a white quiet zone, which must not be cropped.
    step = max(3, min((height-170)//QR_MODULES, (width-30)//QR_MODULES))
    size = step*QR_MODULES
    qr = tk.Canvas(win, width=size, height=size,
                   bg='white', borderwidth=0, highlightthickness=0)
    qr.pack(pady=(0, 7))
    for y, row in enumerate(rows):
        for x, bit in enumerate(row):
            if bit == '1':
                qr.create_rectangle(x*step, y*step,
                                    (x+1)*step, (y+1)*step,
                                    fill='black', outline='black')
    status = tk.StringVar(value='Official signed APK · Android 8 or newer')
    tk.Label(win, textvariable=status, bg='#0f172a', fg='#cbd5e1',
             font=('Sans', 9), wraplength=width-25).pack(pady=(0, 6))

    footer = tk.Frame(win, bg='#0f172a')
    footer.pack()
    def copy_link():
        win.clipboard_clear()
        win.clipboard_append(DOWNLOAD_URL)
        win.update_idletasks()
        status.set('Download link copied to clipboard.')

    def button(label, command, primary=False):
        tk.Button(footer, text=label, command=command, borderwidth=0,
                  bg='#38bdf8' if primary else '#334155',
                  fg='#082f49' if primary else '#f8fafc',
                  activebackground='#7dd3fc' if primary else '#475569',
                  font=('Sans', 10, 'bold'), padx=9, pady=6,
                  cursor='hand2').pack(side='left', padx=4)

    button('Open APK download', open_apk_download, primary=True)
    button('Copy download link', copy_link)
    return win
