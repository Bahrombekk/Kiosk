"""
admin.py — Server (admin) DESKTOP oynasi (PyQt6).

Bu — server qismining yuzi. Ishga tushganda:
  - ichida FastAPI backendni (uvicorn) alohida oqimda ishga tushiradi,
  - admin'ga kontentni boshqarish (qo'shish/o'chirish), sozlamalar va
    server holatini ko'rsatadi.

Ya'ni `server.exe` = shu fayl. Foydalanuvchiga faqat desktop oyna ko'rinadi,
backend ichkarida ishlaydi (TZ 4.2 — admin interfeysi PyQt6 oyna).

Dizayn: chap tomonda doimiy sidebar (bo'limlar, ikonkalar bilan), o'ng tomonda
sahifalar (QStackedWidget). Hamma belgilar — haqiqiy SVG ikonkalar (Lucide).

UI kodi `ui/` paketiga bo'lingan (styles, dialoglar, sahifalar, oyna) —
bu fayl faqat ishga tushirish nuqtasi.

Ishga tushirish:
  pip install -r requirements.txt
  python admin.py
"""
import os
import sys
import logging
import logging.handlers

from PyQt6.QtWidgets import QApplication, QMessageBox

import config
import db
from ui.styles import STYLE
from ui.helpers import port_in_use
from ui.login import LoginDialog
from ui.server_thread import ServerThread
from ui.window import AdminWindow


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
        datefmt="%H:%M:%S")
    # Konsoldan tashqari aylanuvchi faylga ham yozamiz — admin exe konsolsiz
    # ishlaganda ham muammolarni keyin logs/server.log dan ko'rish mumkin.
    try:
        _base = (os.path.dirname(sys.executable)
                 if getattr(sys, "frozen", False)
                 else os.path.dirname(os.path.abspath(__file__)))
        _log_dir = os.path.join(_base, "logs")
        os.makedirs(_log_dir, exist_ok=True)
        _fh = logging.handlers.RotatingFileHandler(
            os.path.join(_log_dir, "server.log"),
            maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        _fh.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)-7s %(name)s %(message)s"))
        logging.getLogger().addHandler(_fh)
    except OSError:
        pass
    db.init_db()
    # Bekat dialogidagi oflayn xarita QtWebEngine'da ishlaydi. QtWebEngine
    # AA_ShareOpenGLContexts'ni QApplication'dan OLDIN talab qiladi va
    # QtWebEngineWidgets shu yerda (app'dan oldin) import qilinishi kerak.
    # O'rnatilmagan bo'lsa jim o'tamiz — xarita bo'lmaydi, qolgani ishlaydi.
    try:
        from PyQt6.QtCore import Qt
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
        import PyQt6.QtWebEngineWidgets  # noqa: F401 — app'dan oldin yuklansin
    except Exception:                                # noqa: BLE001
        pass

    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)

    # Port band bo'lsa (oldingi nusxa hali ishlayapti) — tushunarli ogohlantirish
    if port_in_use(config.PORT):
        QMessageBox.critical(
            None, "Server allaqachon ishlayapti",
            f"{config.PORT}-port band.\n\nEhtimol Kiosk serverining boshqa nusxasi "
            f"hali ochiq. Avval uni yoping (yoki Vazifalar menejeridan python.exe "
            f"jarayonini to'xtating), so'ng qaytadan oching.")
        sys.exit(1)

    # Backend'ni LOGIN'DAN OLDIN ishga tushiramiz — kiosklar (userlar) admin
    # parol kiritmasdan ham darhol onlayn bo'lib ishlayversin. Parol faqat
    # admin OYNASIGA (o'zgartirish/yuklash) kirish uchun darvoza.
    server = ServerThread()
    server.start()

    # Admin parol darvozasi — login oynasi ko'rinib turganda ham backend
    # ishlaydi (kiosklar onlayn). Parol kiritilsa — admin oynasi ochiladi.
    login = LoginDialog()
    if not login.exec():
        # Admin kirmadi/bekor qildi — backendni to'xtatib chiqamiz.
        server.stop()
        server.wait(3000)
        sys.exit(1)

    win = AdminWindow(server=server)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
