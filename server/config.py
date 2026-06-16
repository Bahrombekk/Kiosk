"""
config.py — Server sozlamalari (bir joyda).
"""
import os
import sys


def _base_dir():
    """Source rejimida server/ papkasi, exe rejimida exe yonidagi papka."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = _base_dir()

# Ma'lumotlar bazasi fayli (SQLite)
DB_PATH = os.path.join(BASE_DIR, "data.db")

# Kontent papkasi (kino, audio, kitob, muqovalar, reklama)
CONTENT_DIR = os.path.join(BASE_DIR, "content")
MEDIA_DIR = os.path.join(CONTENT_DIR, "media")
COVERS_DIR = os.path.join(CONTENT_DIR, "covers")
BOOKS_DIR = os.path.join(CONTENT_DIR, "books")
ADS_DIR = os.path.join(CONTENT_DIR, "ads")

# Server manzili
HOST = os.environ.get("KIOSK_HOST", "0.0.0.0")
PORT = int(os.environ.get("KIOSK_PORT", "8765"))

# --- Xavfsizlik / topish (discovery) ---
# TLS (HTTPS/WSS): yoqilganda server self-signed sertifikat bilan ishlaydi va
# kiosklar uni "pin" qiladi. Faqat dev/diagnostika uchun KIOSK_TLS=0 bilan
# o'chirsa bo'ladi (u holda kanal ochiq HTTP bo'ladi — ishlab chiqarishda EMAS).
USE_TLS = os.environ.get("KIOSK_TLS", "1") != "0"

# Discovery: server LAN'ga imzolangan UDP "beacon" tarqatadi, kiosklar uni
# tutib serverni avtomatik topadi (qo'lda IP yozish shart emas).
DISCOVERY_PORT = int(os.environ.get("KIOSK_DISCOVERY_PORT", "8766"))
DISCOVERY_INTERVAL_S = 3        # beacon yuborish oralig'i
DISCOVERY_ENABLED = os.environ.get("KIOSK_DISCOVERY", "1") != "0"

# Serverning ko'rinadigan nomi (bir nechta server bo'lsa kioskда tanlovda
# shu ko'rinadi). Bo'sh bo'lsa hostname ishlatiladi.
import socket as _socket
SERVER_NAME = os.environ.get("KIOSK_NAME") or _socket.gethostname() or "Server"
