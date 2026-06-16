"""
trust.py — Kioskning ishonch lavhasi (trust bundle) bilan ishlash.

O'rnatishda kioskka `trust.json` qo'yiladi (server admin oynasidan eksport
qilinadi). U serverning OCHIQ ma'lumotini saqlaydi — bularning sirligi shart
emas, lekin haqiqiyligi muhim:

  {
    "v": 1,
    "name": "...",                # serverning ko'rinadigan nomi
    "url": "https://IP:8765",     # (ixtiyoriy) — bo'lmasa discovery topadi
    "api_key": "...",             # kiosk -> server autentifikatsiyasi (sir)
    "public_key": "<b64>",        # Ed25519 ochiq kalit — beacon imzosini tekshirish
    "cert_fingerprint": "<hex>",  # TLS sertifikat SHA-256 — requests pinning
    "cert_pem": "-----BEGIN..."   # TLS sertifikat PEM — websockets CA pin
  }

Xavfsizlik mantig'i:
  * Beacon (discovery signali) shu `public_key` bilan tekshiriladi — soxta
    server yasab bo'lmaydi (maxfiy imzo kaliti faqat serverda).
  * TLS ulanish `cert_fingerprint`/`cert_pem` bilan PIN qilinadi — boshqa
    sertifikatga (MITM) ulanmaydi.
  * Beacon ichidagi `fp` shu `cert_fingerprint` bilan mos kelishi ham
    tekshiriladi (qo'shimcha qatlam).
"""
import os
import json
import base64
import logging

from core import config

log = logging.getLogger(__name__)

TRUST_PATH = os.path.join(config.APP_DIR, "trust.json")

_cache = None
_loaded = False


def load():
    """trust.json'ni o'qiydi (dict) yoki yo'q/buzuq bo'lsa None qaytaradi."""
    global _cache, _loaded
    if _loaded:
        return _cache
    _loaded = True
    try:
        with open(TRUST_PATH, encoding="utf-8") as f:
            _cache = json.load(f)
    except (OSError, ValueError):
        _cache = None
    return _cache


def has_trust():
    return load() is not None


def url():
    t = load() or {}
    return (t.get("url") or "").strip() or None


def api_key():
    t = load() or {}
    return t.get("api_key") or ""


def cert_fingerprint():
    """TLS sertifikat SHA-256 fingerprint'i (hex, ikki nuqtasiz, kichik harf)."""
    t = load() or {}
    fp = (t.get("cert_fingerprint") or "").replace(":", "").lower().strip()
    return fp or None


def cert_pem():
    t = load() or {}
    return t.get("cert_pem") or None


def _public_key():
    """Ed25519 ochiq kalit obyekti (yoki None)."""
    t = load() or {}
    raw_b64 = t.get("public_key")
    if not raw_b64:
        return None
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PublicKey)
        return Ed25519PublicKey.from_public_bytes(base64.b64decode(raw_b64))
    except Exception:
        log.warning("trust.json public_key o'qilmadi", exc_info=True)
        return None


def verify_beacon(payload_bytes, sig_bytes):
    """Beacon imzosini server ochiq kaliti bilan tekshiradi. True/False.
    Kalit yo'q bo'lsa False (imzosiz hech narsaga ishonmaymiz)."""
    pk = _public_key()
    if pk is None:
        return False
    try:
        from cryptography.exceptions import InvalidSignature
        pk.verify(sig_bytes, payload_bytes)
        return True
    except InvalidSignature:
        return False
    except Exception:
        log.warning("Beacon imzosini tekshirishda xato", exc_info=True)
        return False
