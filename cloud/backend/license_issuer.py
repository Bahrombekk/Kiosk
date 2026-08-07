"""
license_issuer.py — bulut qurilmani TASDIQLAGANDA unga VENDOR imzoli
litsenziya yasaydi (Ed25519). Qurilma (bus/server) exe'sidagi
`licensing.py` shu formatni va shu VENDOR OCHIQ KALITINI tekshiradi.

Ish oqimi (avtomatik):
  1. Qurilma o'rnatiladi -> bulutga ulanadi (enroll), HARDWARE ID sini yuboradi.
  2. Litsenziya bo'lmagani uchun qurilma BLOKLANGAN turadi.
  3. Super-admin panelда "Tasdiqlash" bosiladi -> bu modul o'sha qurilma hw_id
     siga litsenziya imzolaydi -> `set_license` bilan yuboriladi -> qurilma
     `licensing.install_file` bilan o'rnatadi -> OCHILADI.

VENDOR MAXFIY KALITI (`vendor_private.pem`):
  - Shu papkada yoki `AVTOBUS_VENDOR_KEY` env yo'lida bo'lishi kerak.
  - Repoga KIRMAYDI (.gitignore). Qurilma exe'laridagi ochiq kalitning JUFTI —
    yo'qolsa yangi litsenziya bera olmaysiz, sizib chiqsa soxta litsenziya
    yasash mumkin bo'ladi. XAVFSIZ SAQLANG + zaxira oling.
  - Yo'q bo'lsa auto-litsenziya O'CHIQ bo'ladi (`available()` False) — u holda
    panelдан qo'lда license.key matnini joylashtirish kerak.
"""
import base64
import json
import logging
import os
from datetime import date, timedelta

log = logging.getLogger("cloud.license")

_KEY_PATH = (os.environ.get("AVTOBUS_VENDOR_KEY")
             or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "vendor_private.pem"))

# Standart litsenziya sozlamalari (env bilan o'zgartiriladi):
#   AVTOBUS_LICENSE_DAYS=365   -> muddatli; berilmasa MUDDATSIZ
#   AVTOBUS_LICENSE_KIOSKS=0   -> kiosk soni chegarasi (0 = cheksiz; avtobusда
#                                 kiosk yo'q, shuning uchun 0 mantiqiy)
_DEFAULT_DAYS = os.environ.get("AVTOBUS_LICENSE_DAYS")   # None = forever
_DEFAULT_KIOSKS = int(os.environ.get("AVTOBUS_LICENSE_KIOSKS") or 0)


def available():
    """Vendor maxfiy kaliti mavjudmi (auto-litsenziya yoqilganmi)."""
    return os.path.isfile(_KEY_PATH)


def _b64e(b):
    return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")


def _load_key():
    from cryptography.hazmat.primitives import serialization
    with open(_KEY_PATH, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)


def issue(hw_id, customer="", days=None, forever=None, max_kiosks=None):
    """hw_id ga bog'langan imzolangan litsenziya SATRINI qaytaradi
    (`base64(payload).base64(imzo)`), aynan license.key mazmuni.

    days berilса muddatli; forever=True yoki days yo'q bo'lsa muddatsiz."""
    hw = str(hw_id or "").strip().lower()
    if not hw:
        raise ValueError("hw_id bo'sh — litsenziya yasab bo'lmaydi")
    if days is None and forever is None:
        days = _DEFAULT_DAYS               # env yoki None (forever)
    expires = None
    if not forever and days:
        expires = (date.today() + timedelta(days=int(days))).isoformat()
    if max_kiosks is None:
        max_kiosks = _DEFAULT_KIOSKS
    payload = {
        "v": 1,
        "hw": hw,
        "customer": (customer or "")[:120],
        "issued": date.today().isoformat(),
        "expires": expires,
        "max_kiosks": max(0, int(max_kiosks or 0)),
    }
    pb = json.dumps(payload, separators=(",", ":"),
                    ensure_ascii=False).encode("utf-8")
    sig = _load_key().sign(pb)
    return _b64e(pb) + "." + _b64e(sig)
