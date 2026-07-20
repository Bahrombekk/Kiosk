# -*- mode: python ; coding: utf-8 -*-
"""
kiosk_server.spec - Server/admin ilovasini PyInstaller bilan yig'ish.

Yig'ish:  py -m PyInstaller kiosk_server.spec --noconfirm
Natija:   dist/KioskServer/KioskServer.exe

Eslatma: data.db build ichiga qo'shilmaydi. Birinchi ishga tushishda
exe yonida yangi SQLite baza avtomatik yaratiladi.
"""

import os

datas = [
    ("assets", "assets"),
]

# Veb (Nuxt) build'ini exe yonidagi `web/` papkaga qo'shamiz. web_server.py
# frozen rejimda `<exe>/web/.output/server/index.mjs` ni qidiradi (node bilan
# ishga tushiradi). Avval `kiosk/` da `npm run build` bajarilgan bo'lishi kerak.
# DIQQAT: ishga tushiriladigan mashinada Node.js (node.exe PATH'da) o'rnatilgan
# bo'lishi shart — .output node runtime bilan ishlaydi (bundle qilinmaydi).
_web_output = os.path.join("..", "kiosk", ".output")
if os.path.isdir(_web_output):
    datas.append((_web_output, os.path.join("web", ".output")))
else:
    print("OGOHLANTIRISH: kiosk/.output topilmadi — veb bundle QILINMAYDI. "
          "Avval `kiosk/` papkada `npm run build` bajaring.")

a = Analysis(
    ["admin.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "uvicorn.loops.auto",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan.on",
        # Discovery imzosi + TLS sertifikat (security.py / discovery.py).
        # Lazy importlar PyInstaller tahliliga ko'rinmasligi mumkin — aniq beramiz.
        "cryptography",
        "cryptography.hazmat.bindings._rust",
        "cryptography.hazmat.primitives.asymmetric.ed25519",
        "cryptography.x509",
        # Bekat dialogidagi oflayn xarita (ixtiyoriy). O'rnatilmagan bo'lsa
        # PyInstaller ogohlantirib o'tib ketadi — ilova xaritasiz ishlayveradi.
        "PyQt6.QtWebEngineWidgets",
    ],
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
    name="KioskServer",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon="../user/assets/design/app.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="KioskServer",
)
