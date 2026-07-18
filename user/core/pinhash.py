"""
pinhash.py — PIN xeshini tekshirish (server db.hash_secret formati bilan mos).

Server admin oynasida o'rnatilgan chiqish PIN'i `pbkdf2$iter$salt$hash`
ko'rinishida /api/settings orqali keladi va kiosk keshida saqlanadi —
ochiq matnli PIN hech qayerda yotmaydi, oflaynda ham tekshirish ishlaydi.
"""
import hashlib
import hmac
import os


def hash_secret(plain):
    """PIN/parolni tuzlangan PBKDF2 xeshiga aylantiradi (server db.hash_secret
    bilan bir xil format). Vendor master PIN xeshini tayyorlashda ishlatiladi:
      python -c "from core import pinhash; print(pinhash.hash_secret('PIN'))"
    Natija KIOSK_DEV_PIN_HASH muhit o'zgaruvchisiga qo'yiladi."""
    iterations = 100_000
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt, iterations)
    return f"pbkdf2${iterations}${salt.hex()}${dk.hex()}"


def verify_secret(plain, stored):
    """Kiritilgan PIN'ni saqlangan xesh bilan timing-safe solishtiradi."""
    try:
        algo, iterations, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"),
                                 bytes.fromhex(salt_hex), int(iterations))
        return hmac.compare_digest(dk.hex(), hash_hex)
    except (AttributeError, ValueError):
        return False
