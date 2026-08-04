"""
config.py — Bulut (markaziy admin) sozlamalari bir joyda.

Bulut poyezd serverlaridan farqli — u INTERNETDA turadi (VPS), oq IP bilan.
Poyezd serverlari o'zi ulanadi (outbound WSS), shuning uchun bulutda hech
qanday port-forward yoki discovery kerak emas.
"""
import os
import sys


def _base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = _base_dir()

# SQLite baza (serverlar, kutubxona, navbat, statistika, loglar)
DB_PATH = os.environ.get("CLOUD_DB") or os.path.join(BASE_DIR, "cloud.db")

# Kontent fayllari ombori — sha256 bo'yicha manzillanadi (storage.py).
STORAGE_DIR = os.environ.get("CLOUD_STORAGE") or os.path.join(BASE_DIR, "storage")

# Yuklash paytidagi vaqtinchalik fayllar (tugallanmasa tozalanadi)
TMP_DIR = os.path.join(STORAGE_DIR, "_tmp")

HOST = os.environ.get("CLOUD_HOST", "0.0.0.0")
PORT = int(os.environ.get("CLOUD_PORT", "9000"))

# Serverlar (agentlar) shu manzilga ulanadi va fayllarni shundan tortadi.
# Reverse-proxy ortida turganда TASHQI manzilni shu yerda bering, aks holda
# yuklab olish havolalari ichki manzil bilan yasaladi va agent ulanmaydi.
#   masalan: CLOUD_PUBLIC_URL=https://cloud.kiosk.uz
PUBLIC_URL = (os.environ.get("CLOUD_PUBLIC_URL") or "").rstrip("/")

# TLS: ishlab chiqarishda reverse-proxy (nginx/caddy) TLS'ni o'ziga oladi va
# bulut oddiy HTTP'da ishlaydi. To'g'ridan-to'g'ri HTTPS kerak bo'lsa
# sertifikat yo'llarini bering.
TLS_CERT = os.environ.get("CLOUD_TLS_CERT") or ""
TLS_KEY = os.environ.get("CLOUD_TLS_KEY") or ""
USE_TLS = bool(TLS_CERT and TLS_KEY)

# Birinchi ishga tushishda admin paroli shu env'dan olinadi (xeshlanib bazaga
# yoziladi, ochiq matn saqlanmaydi). Berilmasa — tasodifiy parol yaratiladi va
# konsolga BIR MARTA chiqariladi.
ADMIN_PASS_ENV = os.environ.get("CLOUD_ADMIN_PASS") or ""

# Admin sessiyasi (cookie) qancha yashaydi
SESSION_TTL_S = int(os.environ.get("CLOUD_SESSION_TTL", str(12 * 3600)))

# Fayl yuklab olish havolasi (imzolangan) qancha amal qiladi. Katta kino
# SIM-internetda uzoq tortiladi — muddat saxiy bo'lishi kerak.
DL_TOKEN_TTL_S = int(os.environ.get("CLOUD_DL_TTL", str(24 * 3600)))

# Shu vaqtdan beri heartbeat bo'lmasa server "offlayn" hisoblanadi
OFFLINE_AFTER_S = int(os.environ.get("CLOUD_OFFLINE_AFTER", "90"))

# Agent heartbeat oralig'i (agentga register javobida aytiladi)
HEARTBEAT_INTERVAL_S = int(os.environ.get("CLOUD_HEARTBEAT_S", "30"))

# Bitta yuklashda ruxsat etilgan maksimal fayl hajmi (bayt) — 8 GB
MAX_UPLOAD_BYTES = int(os.environ.get("CLOUD_MAX_UPLOAD", str(8 * 1024 ** 3)))

# Log fayli (aylanuvchi) — main.py sozlaydi
LOG_PATH = os.path.join(BASE_DIR, "logs", "cloud.log")
