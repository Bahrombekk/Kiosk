# -*- mode: python ; coding: utf-8 -*-
"""
kiosk.spec — Foydalanuvchi (kiosk) ilovasini PyInstaller bilan yig'ish.

Yig'ish:  py -m PyInstaller kiosk.spec --noconfirm
Natija:   dist/Kiosk/Kiosk.exe  (+ _internal: kutubxonalar, assets, VLC)

VLC ham birga olinadi — qurilmada VLC o'rnatilgan bo'lishi SHART EMAS.
"""
import os

VLC_DIR = r"C:\Program Files\VideoLAN\VLC"

datas = [
    ("assets", "assets"),
    ("map_tiles", "map_tiles"),
    # VLC plaginlari (dekoderlar) — video/audio o'ynatish uchun
    (os.path.join(VLC_DIR, "plugins"), os.path.join("vlc", "plugins")),
]

binaries = [
    (os.path.join(VLC_DIR, "libvlc.dll"), "vlc"),
    (os.path.join(VLC_DIR, "libvlccore.dll"), "vlc"),
    # Plagin keshini o'rnatish paytida qayta generatsiya qilish uchun
    # (installer chaqiradi — VLC startupida 'stale cache' xatosi bo'lmasin)
    (os.path.join(VLC_DIR, "vlc-cache-gen.exe"), "vlc"),
]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Kiosk",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon="assets/design/app.ico",
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Kiosk",
)
