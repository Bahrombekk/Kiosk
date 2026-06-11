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
