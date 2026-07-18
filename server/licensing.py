"""
licensing.py — VENDOR tomonidan imzolangan litsenziya tekshiruvi.

Nima uchun kerak: avvalgi "sinov muddati" tizimi data.db ichidagi oddiy
qiymatlar edi — SQLite'ni ochib o'zgartirsa bo'lardi, serverni boshqa
kompyuterga ko'chirsa ham ishlayverardi, kiosk soni cheklanmasdi. Endi:

  - Litsenziya `license.key` fayli: JSON payload + Ed25519 imzo.
  - Imzo VENDOR maxfiy kaliti bilan qo'yiladi (server/tools/license_tool.py,
    kalit MIJOZGA BERILMAYDI, bu serverda ham yo'q). Bu yerda faqat OCHIQ
    kalit bor — soxta litsenziya yasab bo'lmaydi, DB'ni tahrirlash foydasiz.
  - Payload serverning HARDWARE ID'siga (Windows MachineGuid) bog'lanadi —
    o'rnatilgan papkani boshqa kompyuterga ko'chirsa litsenziya ishlamaydi.
  - `max_kiosks` — bir vaqtda ro'yxatdan o'tgan kiosk qurilmalar soni
    chegarasi (birinchi ulanish tartibida). 51-qurilma bloklanadi.

Rejimlar:
  - Frozen (production, KioskServer.exe): litsenziya MAJBURIY. Yo'q/yaroqsiz/
    muddati o'tgan/boshqa mashina -> barcha kiosklar qulf ekraniga tushadi
    (blocked=True), admin oynasida esa HW ID + sabab ko'rinadi.
  - Manba rejimi (dev): fayl yo'q bo'lsa ogohlantirish bilan ishlayveradi
    (cheksiz), lekin YAROQSIZ fayl dev'da ham bloklaydi (real sinov uchun).

Fayl formati (license.key, bitta qator):
  base64url(payload_json) + "." + base64url(ed25519_signature)
  payload: {"v":1, "hw":"<machine-guid>", "customer":"...", "issued":"YYYY-MM-DD",
            "expires":"YYYY-MM-DD"|null, "max_kiosks":50}
"""
import base64
import json
import logging
import os
import sys
from datetime import date, datetime

import config

log = logging.getLogger("kiosk.license")

# VENDOR OCHIQ KALITI (Ed25519, base64 raw 32 bayt). Juftlik
# server/tools/license/vendor_private.pem da (repo'ga KIRMAYDI, faqat
# vendor kompyuterida) — license_tool.py shu bilan imzolaydi.
VENDOR_PUBLIC_KEY_B64 = "MF1e45Vz/x651Hk6tdciGDUgx54F4zq1LbHX5XqVQr0="

LICENSE_PATH = os.path.join(config.BASE_DIR, "license.key")

_FROZEN = getattr(sys, "frozen", False)

# mtime-kesh: har status so'rovida faylni qayta o'qib-tekshirmaslik uchun
_cache = {"mtime": None, "state": None}


def hardware_id():
    """Serverning barqaror qurilma identifikatori.

    Windows MachineGuid — OS o'rnatilganda yaratiladi; dastur papkasini
    nusxalash bilan o'zgarmaydi, lekin BOSHQA kompyuterda albatta boshqacha.
    O'qib bo'lmasa MAC-asosli fallback (kamdan-kam)."""
    if os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r"SOFTWARE\Microsoft\Cryptography",
                                0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as k:
                guid, _ = winreg.QueryValueEx(k, "MachineGuid")
                guid = str(guid).strip().lower()
                if guid:
                    return guid
        except OSError:
            log.warning("MachineGuid o'qilmadi — MAC fallback ishlatiladi")
    import uuid
    return f"mac-{uuid.getnode():012x}"


def _b64d(s):
    s = s.strip()
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _verify(raw_text):
    """`payload.signature` satrini tekshiradi -> payload dict yoki xato sabab.

    Qaytaradi: (payload|None, reason|None)."""
    try:
        payload_b64, sig_b64 = raw_text.strip().split(".", 1)
        payload_bytes = _b64d(payload_b64)
        signature = _b64d(sig_b64)
    except (ValueError, TypeError):
        return None, "format buzilgan"
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PublicKey)
        pub = Ed25519PublicKey.from_public_bytes(
            base64.b64decode(VENDOR_PUBLIC_KEY_B64))
        pub.verify(signature, payload_bytes)
    except Exception:                                # noqa: BLE001
        return None, "imzo yaroqsiz"
    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None, "payload o'qilmadi"
    if not isinstance(payload, dict) or payload.get("v") != 1:
        return None, "versiya noma'lum"
    return payload, None


def _evaluate():
    """license.key ni o'qib to'liq holat dict'ini quradi (keshsiz)."""
    hw = hardware_id()
    state = {
        "present": False,       # fayl bormi
        "valid": False,         # imzo + hw + muddat hammasi joyida
        "reason": None,         # yaroqsizlik sababi (odam o'qiydigan)
        "customer": None,
        "issued": None,
        "expires": None,        # None = muddatsiz
        "days_left": None,
        "max_kiosks": 0,        # 0 = cheksiz
        "hw_id": hw,
        "blocked": False,       # kiosklar qulflanadimi
    }
    if not os.path.isfile(LICENSE_PATH):
        if _FROZEN:
            state["reason"] = "litsenziya fayli yo'q (license.key)"
            state["blocked"] = True
        else:
            state["reason"] = "dev rejimi — litsenziyasiz (cheksiz)"
        return state
    state["present"] = True
    try:
        with open(LICENSE_PATH, "r", encoding="ascii") as f:
            raw = f.read()
    except OSError as e:
        state["reason"] = f"faylni o'qib bo'lmadi: {e}"
        state["blocked"] = True
        return state
    payload, err = _verify(raw)
    if payload is None:
        state["reason"] = err
        state["blocked"] = True
        return state
    state["customer"] = str(payload.get("customer") or "")[:120]
    state["issued"] = payload.get("issued")
    state["expires"] = payload.get("expires")
    try:
        state["max_kiosks"] = max(0, int(payload.get("max_kiosks") or 0))
    except (TypeError, ValueError):
        state["max_kiosks"] = 0
    lic_hw = str(payload.get("hw") or "").strip().lower()
    if lic_hw != hw:
        state["reason"] = "litsenziya BOSHQA kompyuterga berilgan"
        state["blocked"] = True
        return state
    if state["expires"]:
        try:
            end = datetime.strptime(state["expires"], "%Y-%m-%d").date()
            state["days_left"] = (end - date.today()).days
            if date.today() > end:
                state["reason"] = "litsenziya muddati tugagan"
                state["blocked"] = True
                return state
        except ValueError:
            state["reason"] = "muddat formati buzilgan"
            state["blocked"] = True
            return state
    state["valid"] = True
    return state


def state():
    """Joriy litsenziya holati (mtime-kesh bilan — fayl almashsa restartsiz
    qayta o'qiladi; masalan admin yangi license.key yuklaganda)."""
    try:
        mtime = os.path.getmtime(LICENSE_PATH)
    except OSError:
        mtime = None
    if _cache["state"] is not None and _cache["mtime"] == mtime:
        return _cache["state"]
    st = _evaluate()
    _cache["mtime"] = mtime
    _cache["state"] = st
    if not st["valid"]:
        log.warning("Litsenziya: %s (hw=%s)", st["reason"], st["hw_id"])
    else:
        log.info("Litsenziya OK: %s, muddat=%s, kiosk limiti=%s",
                 st["customer"] or "-", st["expires"] or "muddatsiz",
                 st["max_kiosks"] or "cheksiz")
    return st


def install_file(src_path):
    """Admin tanlagan litsenziya faylini joyiga ko'chiradi va tekshiradi.
    Qaytaradi: yangi holat dict. Yaroqsiz fayl ham ko'chiriladi (holatda sabab
    ko'rinadi) — lekin avvalgi YAROQLI faylni yaroqsiz bilan almashtirmaymiz."""
    with open(src_path, "r", encoding="ascii") as f:
        raw = f.read()
    payload, err = _verify(raw)
    cur = state()
    if payload is None and cur.get("valid"):
        raise ValueError(f"Yangi fayl yaroqsiz ({err}) — mavjud litsenziya saqlanadi")
    tmp = LICENSE_PATH + ".tmp"
    with open(tmp, "w", encoding="ascii") as f:
        f.write(raw.strip() + "\n")
    os.replace(tmp, LICENSE_PATH)
    _cache["mtime"] = None   # keshni majburan yangilaymiz
    return state()


# --- Kiosk soni cheklovi -----------------------------------------------------
def allowed_device_ids():
    """Litsenziya limitiga sig'adigan device_id'lar to'plami (birinchi ulanish
    tartibida) yoki None = cheksiz. Admin eski kiosk yozuvini o'chirsa, bo'sh
    o'ringa yangi qurilma kiradi."""
    st = state()
    max_k = st["max_kiosks"]
    if not st["valid"] or max_k <= 0:
        return None   # litsenziya yaroqsiz bo'lsa baribir hammasi blocked
    import db
    ids = db.kiosk_ids_ordered()
    return set(ids[:max_k])


def device_allowed(device_id):
    """Shu qurilma litsenziya limitiga sig'adimi?"""
    allowed = allowed_device_ids()
    return True if allowed is None else device_id in allowed


def over_limit_devices():
    """Limitdan ORTIB ketgan qurilmalar to'plami (per-device bloklash uchun)."""
    allowed = allowed_device_ids()
    if allowed is None:
        return frozenset()
    import db
    return frozenset(d for d in db.kiosk_ids_ordered() if d not in allowed)
