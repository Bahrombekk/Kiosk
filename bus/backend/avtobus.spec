# -*- mode: python ; coding: utf-8 -*-
"""
avtobus.spec — Avtobus backend'ini (headless FastAPI) PyInstaller bilan yig'ish.

DIQQAT: bu spec TO'G'RIDAN-TO'G'RI backend/ da emas, `build.ps1` tayyorlagan
VAQTINCHALIK NUSXADA (build\\app\\) ishga tushiriladi. build.ps1:
  1) maxfiy modullarni (licensing, security, cloud_client) Nuitka bilan
     `.pyd` (mashina kodi) ga aylantiradi va ularning `.py` manbasini
     build\\app\\ dan O'CHIRADI — shu sababli exe ichида ularning manbasi
     (hatto .pyc ham) BO'LMAYDI, faqat kompilyatsiya qilingan .pyd qoladi;
  2) shu spec bilan `pyinstaller` ni build\\app\\ ичiда ishga tushiradi.

Natija: dist\\Avtobus\\Avtobus.exe (+ _internal\\). node.exe, ffmpeg.exe va
web\\.output ni build.ps1 exe YONIGA (release\\Avtobus\\) qo'shadi — kod
ularni aynan shu joydan (sys.executable yonidan) qidiradi.

Manba data.db / content bundle QILINMAYDI — birinchi ishga tushishда yaratiladi,
kontent esa bulutdan keladi.
"""
import os
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# .pyd (Nuitka) modullar PyInstaller tahliliga "shaffof emas" — ularning
# ichki importlarini qo'lда e'lon qilamiz, aks holда exe'да yetishmaydi.
# cryptography / websockets — TO'LIQ yig'iladi (lazy importlar .pyd ичiga
# yashiringan, statik tahlил ko'rmaydi).
hidden = [
    # uvicorn dinamik yuklaydigan loop/protokol/lifespan modullari
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.lifespan.on",
    # cloud_client / security lazy ishlatadigan stdlib (opaque .pyd ичida)
    "urllib.request",
    "urllib.error",
    "ipaddress",
    "hashlib",
    "collections",
    # Nuitka'ga o'tган maxfiy modullar — .py o'chirilгani uchun PyInstaller
    # ularni faqat .pyd sifatида ko'radi; aniq kiritishni kafolatlaymiz.
    "licensing",
    "security",
    "cloud_client",
]
hidden += collect_submodules("cryptography")
hidden += collect_submodules("websockets")

# Ixtiyoriy ikonka (build.ps1 build\app\ ga app.ico nusxalasa ishlatiladi).
_icon = "app.ico" if os.path.isfile("app.ico") else None

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=[],
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    # PyQt/tkinter avtobusда umuman kerak emas — bundle'ni shishirmasin.
    excludes=["PyQt6", "PyQt6.QtWebEngineWidgets", "PyQt5", "tkinter",
              "matplotlib", "numpy.tests"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Avtobus",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # console=True: xizmat sifatida NSSM ostида oyna KO'RINMAYDI (session 0),
    # loglar faylга tushadi. Lekin operator terminalда `Avtobus.exe --hwid`
    # kabi CLI ni ishlata oladi (windowed exe'da stdout hech qayerга bormasди).
    console=True,
    disable_windowed_traceback=False,
    icon=_icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="Avtobus",
)
