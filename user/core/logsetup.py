"""
logsetup.py — Markaziy log tizimi (aylanuvchi fayl + dev konsol).

Kiosk poyezdda nazoratsiz ishlaydi — muammo bo'lganda operator `logs/kiosk.log`
faylini ochib nima bo'lganini ko'ra olishi kerak. Loglar 1MB ga yetganda
aylanadi (3 ta zaxira), disk to'lib ketmaydi.

Ishlatish:
    from core import logsetup
    logsetup.setup()                 # main() boshida bir marta
    log = logsetup.get_logger(__name__)
    log.warning("Server javob bermadi: %s", e)
"""
import logging
import logging.handlers
import os
import sys

_initialized = False


def base_dir():
    """Exe (frozen) yoki loyiha papkasi — server.txt bilan bir xil mantiq."""
    from core.config import APP_DIR
    return APP_DIR


def setup():
    """Root logger'ga aylanuvchi fayl (logs/kiosk.log) ulaydi. Idempotent."""
    global _initialized
    if _initialized:
        return
    _initialized = True

    log_dir = os.path.join(base_dir(), "logs")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s %(message)s")

    try:
        os.makedirs(log_dir, exist_ok=True)
        fh = logging.handlers.RotatingFileHandler(
            os.path.join(log_dir, "kiosk.log"),
            maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except OSError:
        pass  # disk muammosi log tufayli kioskni yiqitmasin

    if not getattr(sys, "frozen", False):
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        root.addHandler(sh)

    logging.getLogger(__name__).info("Log tizimi ishga tushdi: %s", log_dir)


def get_logger(name):
    return logging.getLogger(name)
