"""
security.py — Bulut kriptografik shaxsi va tokenlar.

Uch xil sir bor, uchtasi ham har xil vazifada:

1. **Ed25519 imzo kaliti** (`cloud_signing_key.pem`) — bulut yuborgan har bir
   BUYRUQNI imzolaydi. Poyezd serveri buni enroll paytida olgan ochiq kalit
   bilan tekshiradi: kanal buzilса ham begona "o'chir"/"yukla" buyrug'i
   o'tmaydi. Mexanizm `server/security.py` dagi imzo bilan bir xil, faqat
   tomonlar teskari (endi bulut imzolaydi, server tekshiradi).

2. **Yuklab olish siri** (`dl_secret`) — fayl havolalari HMAC bilan
   imzolanadi va muddatli bo'ladi. Ya'ni havola oshkor bo'lsa ham bir kundan
   keyin ishlamaydi va boshqa server uni ishlatolmaydi.

3. **Admin paroli** (pbkdf2 xesh) + sessiya tokenlari (faqat xotirada —
   bulut qayta ishga tushса hamma tizimdan chiqadi, bu ataylab).
"""
import base64
import hmac
import json
import logging
import os
import secrets
import sys
import time
from hashlib import sha256

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

import config
import db

log = logging.getLogger("cloud.security")

SIGN_KEY_PATH = os.path.join(config.BASE_DIR, "cloud_signing_key.pem")

_signing_key = None          # ed25519 private key
_sessions = {}               # token -> {exp, user_id, username, role, ttl}


# ----------------------------------------------------------- Ed25519 imzo
def _restrict(path):
    """Kalit faylini faqat egasiga o'qiladigan qiladi (POSIX; Windowsда ACL
    meros bo'lib qoladi — bunda fayl dastur papkasida turadi)."""
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def ensure_identity():
    """Imzo kalitini o'qiydi; yo'q bo'lsa YARATADI (bir marta).

    DIQQAT: bu kalit almashsa, allaqachon ro'yxatdan o'tgan serverlar bulut
    buyruqlarini rad etadi (ochiq kalit ularда saqlangan). Shuning uchun
    `cloud_signing_key.pem` — zaxira nusxa olinishi shart bo'lgan fayl.
    """
    global _signing_key
    if _signing_key is not None:
        return _signing_key
    if os.path.isfile(SIGN_KEY_PATH):
        with open(SIGN_KEY_PATH, "rb") as f:
            _signing_key = serialization.load_pem_private_key(f.read(), password=None)
    else:
        _signing_key = ed25519.Ed25519PrivateKey.generate()
        pem = _signing_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption())
        with open(SIGN_KEY_PATH, "wb") as f:
            f.write(pem)
        _restrict(SIGN_KEY_PATH)
        log.info("Bulut imzo kaliti yaratildi: %s", SIGN_KEY_PATH)
    return _signing_key


def public_key_b64():
    """Serverlarga (enroll javobida) beriladigan ochiq kalit."""
    raw = ensure_identity().public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw)
    return base64.b64encode(raw).decode()


def sign_command(cmd: dict) -> dict:
    """Buyruqni imzolaydi: {"payload": <canonical json>, "sig": <b64>}.

    Agent AYNAN `payload` satrini tekshiradi va shundan JSON o'qiydi — shuning
    uchun bu yerda satr bir marta yasaladi va o'zgartirilmaydi (imzo va
    ma'lumot bir-biriga mos bo'lishi kerak)."""
    payload = json.dumps(cmd, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"))
    sig = ensure_identity().sign(payload.encode("utf-8"))
    return {"payload": payload, "sig": base64.b64encode(sig).decode()}


# ------------------------------------------------- yuklab olish tokenlari
def _dl_secret():
    s = db.get_setting("dl_secret")
    if not s:
        s = secrets.token_urlsafe(32)
        db.set_setting("dl_secret", s)
    return s.encode()


def make_dl_token(sha, server_id, name="", ttl=None):
    """Muddatli, imzolangan yuklab olish tokeni.

    Ichida `server_id` ham bor — havola boshqa serverga o'tса ishlamaydi
    (agent tokenni o'z ulanishida ishlatadi)."""
    exp = int(time.time()) + int(ttl or config.DL_TOKEN_TTL_S)
    body = {"s": sha, "v": server_id, "e": exp, "n": name[:120]}
    raw = json.dumps(body, separators=(",", ":")).encode()
    b = base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
    mac = hmac.new(_dl_secret(), b.encode(), sha256).digest()
    return b + "." + base64.urlsafe_b64encode(mac).rstrip(b"=").decode()[:32]


def read_dl_token(token):
    """Tokenni tekshiradi. Yaroqli bo'lsa body dict, aks holda None."""
    try:
        b, _, mac = token.partition(".")
        if not b or not mac:
            return None
        want = hmac.new(_dl_secret(), b.encode(), sha256).digest()
        want_b = base64.urlsafe_b64encode(want).rstrip(b"=").decode()[:32]
        if not hmac.compare_digest(mac, want_b):
            return None
        pad = "=" * (-len(b) % 4)
        body = json.loads(base64.urlsafe_b64decode(b + pad))
        if int(body.get("e", 0)) < time.time():
            return None
        return body
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


# ----------------------------------------------------------- admin kirishi
def ensure_admin_password():
    """Admin hisobini tayyorlaydi. CLOUD_ADMIN_PASS berilса shundan, aks holda
    tasodifiy parol yaratiladi va konsolga BIR MARTA chiqariladi.

    Eski bitta global parol `admin_users` ga ko'chiriladi — ayni parol ishlashda
    davom etadi, faqat endi login maydoni ham bor (`admin`)."""
    db.migrate_legacy_password()
    if db.get_user(db.DEFAULT_USER):
        # Env berilgan bo'lsa — parolni MAJBURIY yangilaymiz (operator env'ni
        # o'zgartirib qayta ishga tushirса parol almashsin).
        if config.ADMIN_PASS_ENV:
            db.upsert_user(db.DEFAULT_USER, config.ADMIN_PASS_ENV)
            db.set_setting("admin_pass_hash",
                           db.hash_secret(config.ADMIN_PASS_ENV))
        return None
    plain = config.ADMIN_PASS_ENV or secrets.token_urlsafe(9)
    db.upsert_user(db.DEFAULT_USER, plain)
    db.set_setting("admin_pass_hash", db.hash_secret(plain))
    if not config.ADMIN_PASS_ENV:
        # DIQQAT: parol logger bilan CHIQARILMAYDI — logger fayl handler'ga ham
        # yozadi (logs/cloud.log), ya'ni parol diskda qolib ketardi va log
        # faylini o'qigan odam admin huquqini olardi. Shuning uchun to'g'ridan
        # konsolga (stderr) chiqaramiz: ekranda ko'rinadi, faylga tushmaydi.
        print("\n" + "=" * 62, file=sys.stderr)
        print(f"  ADMIN PAROLI (faqat shu marta ko'rsatiladi): {plain}",
              file=sys.stderr)
        print("  Hoziroq ko'chirib oling. O'zgartirish uchun:", file=sys.stderr)
        print("  CLOUD_ADMIN_PASS=<yangi-parol> bilan qayta ishga tushiring",
              file=sys.stderr)
        print("=" * 62 + "\n", file=sys.stderr, flush=True)
        log.info("Admin paroli yaratildi (konsolда ko'rsatildi, logда yo'q)")
        return plain
    return None


def check_login(username, plain):
    """Login + parolni tekshiradi. To'g'ri bo'lsa foydalanuvchi dict, aks holda
    None. Login bo'sh berilса `admin` deb qabul qilinadi — eski (faqat parol)
    kirish ham ishlashda davom etadi.

    DIQQAT: chaqiruvchi qaysi maydon xato ekanini AYTMASLIGI kerak — aks holda
    mavjud loginlarni taxmin qilib chiqish osonlashadi."""
    username = (str(username or "").strip() or db.DEFAULT_USER)
    u = db.get_user(username)
    if not u:
        # Vaqtни teng qilish uchun baribir bitta xesh hisoblab ko'ramiz
        db.verify_secret(plain or "", db.hash_secret("x"))
        return None
    if not db.verify_secret(plain or "", u["pass_hash"]):
        return None
    db.touch_user(u["id"])
    return u


def check_password(plain):
    """Eski API (faqat parol) — moslik uchun qoldirilgan."""
    return bool(check_login(db.DEFAULT_USER, plain))


def new_session(user=None, remember=False):
    """Sessiya yaratadi. `user` berilса unда kim ekani ham saqlanadi (loglarда
    «kim» ko'rinishi uchun). `remember` — uzoq sessiya (7 kun)."""
    token = secrets.token_urlsafe(32)
    ttl = (7 * 24 * 3600) if remember else config.SESSION_TTL_S
    _sessions[token] = {
        "exp": time.monotonic() + ttl,
        "user_id": (user or {}).get("id"),
        "username": (user or {}).get("username") or db.DEFAULT_USER,
        "role": (user or {}).get("role") or "super",
        "ttl": ttl,
    }
    _gc_sessions()
    return token


def valid_session(token):
    if not token:
        return False
    s = _sessions.get(token)
    if not s:
        return False
    if s["exp"] < time.monotonic():
        _sessions.pop(token, None)
        return False
    return True


def session_user(token):
    """Sessiyadagi foydalanuvchi (kim kirgan) — panel va loglar uchun."""
    s = _sessions.get(token)
    if not s or s["exp"] < time.monotonic():
        return None
    return {"username": s["username"], "role": s["role"],
            "user_id": s["user_id"], "ttl": s["ttl"]}


def drop_session(token):
    _sessions.pop(token, None)


def _gc_sessions():
    now = time.monotonic()
    for t in [t for t, s in _sessions.items() if s["exp"] < now]:
        _sessions.pop(t, None)
