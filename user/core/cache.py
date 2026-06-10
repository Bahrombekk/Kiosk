"""
cache.py — Oflayn rejim uchun lokal kesh.

Server o'chsa kiosk butunlay "ko'r" bo'lib qolmasin: oxirgi muvaffaqiyatli
yuklangan katalog (kontent, reklama, saytlar, yo'nalish, sozlamalar) JSON
fayllarga saqlanadi va tarmoq xatosida shulardan o'qiladi. Muqova rasmlari
ham diskka keshlanadi (covers/ — fayl nomi URL'ning sha1 xeshi).

Yozish atomik (*.tmp + os.replace) — yozish o'rtasida tok o'chsa ham eski
nusxa buzilmaydi.
"""
import hashlib
import json
import logging
import os
import time

from core.config import APP_DIR

log = logging.getLogger(__name__)

CACHE_DIR = os.path.join(APP_DIR, "cache")
COVERS_DIR = os.path.join(CACHE_DIR, "covers")


def save_json(name, data):
    """data'ni cache/<name>.json ga atomik yozadi (xato jim loglanadi)."""
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        path = os.path.join(CACHE_DIR, name + ".json")
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, path)
    except OSError:
        log.warning("Keshga yozib bo'lmadi: %s", name, exc_info=True)


def load_json(name):
    """(data, yoshi_soniyada) yoki None (kesh yo'q/buzilgan)."""
    path = os.path.join(CACHE_DIR, name + ".json")
    try:
        age = time.time() - os.path.getmtime(path)
        with open(path, encoding="utf-8") as f:
            return json.load(f), age
    except (OSError, ValueError):
        return None


def has_catalog():
    """Asosiy katalog keshi bormi? (birinchi ishga tushishni farqlash uchun)."""
    return os.path.isfile(os.path.join(CACHE_DIR, "content.json"))


def cover_path(url):
    """Muqova URL'i uchun diskdagi kesh fayl yo'li."""
    h = hashlib.sha1(url.encode("utf-8")).hexdigest()
    return os.path.join(COVERS_DIR, h)


def save_cover(url, data):
    """Muqova baytlarini diskka atomik yozadi."""
    try:
        os.makedirs(COVERS_DIR, exist_ok=True)
        path = cover_path(url)
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except OSError:
        log.debug("Muqova keshlanmadi: %s", url)


def load_cover(url):
    """Diskdan muqova baytlari yoki None."""
    try:
        with open(cover_path(url), "rb") as f:
            return f.read()
    except OSError:
        return None
