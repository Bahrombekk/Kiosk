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
_sessions = {}               # token -> muddati tugash vaqti (monotonik)


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
    """Admin parolini tayyorlaydi. CLOUD_ADMIN_PASS berilса shundan, aks holda
    tasodifiy parol yaratiladi va konsolga BIR MARTA chiqariladi."""
    if db.get_setting("admin_pass_hash"):
        # Env berilgan bo'lsa — parolni MAJBURIY yangilaymiz (operator env'ni
        # o'zgartirib qayta ishga tushirса parol almashsin).
        if config.ADMIN_PASS_ENV:
            db.set_setting("admin_pass_hash",
                           db.hash_secret(config.ADMIN_PASS_ENV))
        return None
    plain = config.ADMIN_PASS_ENV or secrets.token_urlsafe(9)
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


def check_password(plain):
    stored = db.get_setting("admin_pass_hash") or ""
    return bool(stored) and db.verify_secret(plain, stored)


def new_session():
    token = secrets.token_urlsafe(32)
    _sessions[token] = time.monotonic() + config.SESSION_TTL_S
    _gc_sessions()
    return token


def valid_session(token):
    if not token:
        return False
    exp = _sessions.get(token)
    if not exp:
        return False
    if exp < time.monotonic():
        _sessions.pop(token, None)
        return False
    return True


def drop_session(token):
    _sessions.pop(token, None)


def _gc_sessions():
    now = time.monotonic()
    for t in [t for t, e in _sessions.items() if e < now]:
        _sessions.pop(t, None)
