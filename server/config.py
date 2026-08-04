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

# Ma'lumotlar bazasi fayli (SQLite). KIOSK_DB / KIOSK_CONTENT bilan boshqa
# joyga ko'chirish mumkin — sinov va diagnostika uchun (ishlab chiqarishda
# berilmaydi, u holda exe yonidagi standart joy ishlatiladi).
DB_PATH = os.environ.get("KIOSK_DB") or os.path.join(BASE_DIR, "data.db")

# Kontent papkasi (kino, audio, kitob, muqovalar, reklama)
CONTENT_DIR = os.environ.get("KIOSK_CONTENT") or os.path.join(BASE_DIR, "content")
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

# Ilova versiyasi (bulut panelida ko'rinadi)
APP_VERSION = "1.0.0"


# --- Markaziy bulut (masofadan boshqarish) ---
# Server bulutga O'ZI ulanadi (outbound WSS) — poyezdda oq IP kerak emas.
# Sozlash ikki usulda: muhit o'zgaruvchisi yoki exe yonidagi `cloud.txt`:
#     url=https://cloud.kiosk.uz
#     enroll=<bir martalik token>       (bir marta ishlatilgach kerak emas)
def _cloud_txt():
    path = os.path.join(BASE_DIR, "cloud.txt")
    out = {}
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                k, _, v = line.partition("=")
                if v:
                    out[k.strip().lower()] = v.strip()
                elif line.startswith("http"):
                    out.setdefault("url", line)     # faqat manzil yozilgan holat
    except OSError:
        pass
    return out


_CLOUD = _cloud_txt()

# Build vaqtida shu yerga o'z bulut domeningizni yozib qo'yish mumkin — u holda
# o'rnatuvchi HECH NARSA kiritmaydi, server o'zi ulanadi (tasdiqlash bulut
# panelida bir marta bosiladi). cloud.txt / env berilsa ular ustun turadi.
CLOUD_URL_DEFAULT = ""


def _norm_cloud_url(u):
    """Manzilni normallashtiradi: `cloud.poyezd.uz` -> `https://cloud.poyezd.uz`.

    Operator odatda faqat DOMENNI yozadi — sxemani o'zimiz qo'shamiz. Lokal
    manzillar (localhost/127.*) uchun http, qolganlari uchun https."""
    u = (u or "").strip().rstrip("/")
    if not u:
        return ""
    if "://" in u:
        return u
    host = u.split("/")[0].split(":")[0].lower()
    local = host in ("localhost", "127.0.0.1", "::1") or host.startswith("192.168.") \
        or host.startswith("10.") or host.endswith(".local")
    return ("http://" if local else "https://") + u


CLOUD_URL = _norm_cloud_url(os.environ.get("KIOSK_CLOUD_URL")
                            or _CLOUD.get("url") or CLOUD_URL_DEFAULT)
CLOUD_ENROLL = os.environ.get("KIOSK_CLOUD_ENROLL") or _CLOUD.get("enroll") or ""
CLOUD_HEARTBEAT_S = int(os.environ.get("KIOSK_CLOUD_HEARTBEAT", "30"))
# Kiosk statistikasi bulutga qancha vaqtda bir yuboriladi (batch)
CLOUD_STATS_S = int(os.environ.get("KIOSK_CLOUD_STATS", "300"))
