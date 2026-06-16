"""
security.py — Server kriptografik shaxsi: Ed25519 imzo kaliti + TLS sertifikat.

Maqsad (xavfsizlik poydevori):
  - Server o'zini ISBOTLAYDI — kiosklar faqat shu serverga ishonadi.
  - Birinchi ishga tushishda kalitlar/sertifikat BIR MARTA yaratiladi va
    BASE_DIR'da saqlanadi. Keyingi ishga tushishlarda o'qiladi (fingerprint
    o'zgarmaydi — provisioning qilingan kiosklar pin'i buzilmaydi).

Yaratiladigan fayllar (BASE_DIR ichida):
  - signing_key.pem            : Ed25519 MAXFIY kalit — FAQAT serverda qoladi,
                                 hech qachon tarmoqqa chiqmaydi.
  - server_cert.pem            : self-signed TLS sertifikat (CA:TRUE, SAN=LAN IP)
  - server_key.pem             : TLS sertifikat maxfiy kaliti

Kiosklarga FAQAT ochiq ma'lumot beriladi (trust_bundle()):
  public key (b64) + cert fingerprint + cert PEM. Bularning sirligi shart emas —
  bittasi sizib chiqsa ham soxta server yasab bo'lmaydi (maxfiy imzo kaliti
  serverda qoladi).

Bog'liqlik: cryptography (requirements.txt).
"""
import os
import base64
import socket
import logging
import datetime as _dt

import config

log = logging.getLogger("kiosk.security")

# Sertifikat amal qilish muddati (yillar). Uzoq — kiosk parki uzoq ishlaydi,
# muddati tugab qolib stream uzilib qolmasin.
_CERT_YEARS = 20

# Fayl yo'llari (BASE_DIR — exe yoni yoki server/ manba papkasi).
SIGNING_KEY_PATH = os.path.join(config.BASE_DIR, "signing_key.pem")
TLS_CERT_PATH = os.path.join(config.BASE_DIR, "server_cert.pem")
TLS_KEY_PATH = os.path.join(config.BASE_DIR, "server_key.pem")


def _local_ipv4s():
    """Serverning LAN IPv4 manzillari (sertifikat SAN'iga yoziladi — VLC IP
    orqali ulanganda sertifikatni qabul qilishi uchun). helpers.local_ips bilan
    bir xil mantiq, lekin bu modul PyQt'ga bog'lanmaydi."""
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None,
                                       socket.AF_INET):
            ips.add(info[4][0])
    except socket.gaierror:
        pass
    # Marshrutga qarab aniqlangan asosiy manzil (getaddrinfo ba'zan o'tkazib
    # yuboradi) — UDP "ulanishi" hech narsa yubormaydi, faqat manbani aniqlaydi.
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    ips.discard("127.0.0.1")
    return sorted(ips)


# --- Ed25519 imzo kaliti ----------------------------------------------------
def _load_or_create_signing_key():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey)

    if os.path.isfile(SIGNING_KEY_PATH):
        with open(SIGNING_KEY_PATH, "rb") as f:
            return serialization.load_pem_private_key(f.read(), password=None)
    key = Ed25519PrivateKey.generate()
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption())
    with open(SIGNING_KEY_PATH, "wb") as f:
        f.write(pem)
    log.info("Yangi Ed25519 imzo kaliti yaratildi: %s", SIGNING_KEY_PATH)
    return key


# --- Self-signed TLS sertifikat ---------------------------------------------
def _create_tls_cert():
    """LAN IP'lari SAN'ga yozilgan self-signed sertifikat yaratadi (CA:TRUE —
    kioskда Trusted Root'ga qo'shilganda va pin sifatida ishlatilganda mos)."""
    import ipaddress
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    host = socket.gethostname() or "kiosk-server"
    name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, host),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Kiosk Server"),
    ])
    alt = [x509.DNSName(host), x509.DNSName("localhost"),
           x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
    for ip in _local_ipv4s():
        try:
            alt.append(x509.IPAddress(ipaddress.ip_address(ip)))
        except ValueError:
            pass
    now = _dt.datetime.now(_dt.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - _dt.timedelta(days=1))
        .not_valid_after(now + _dt.timedelta(days=365 * _CERT_YEARS))
        .add_extension(x509.SubjectAlternativeName(alt), critical=False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None),
                       critical=True)
        .sign(key, hashes.SHA256()))

    with open(TLS_KEY_PATH, "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()))
    with open(TLS_CERT_PATH, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    log.info("Yangi TLS sertifikat yaratildi (SAN IP: %s)", _local_ipv4s())


def ensure_identity():
    """Imzo kaliti va TLS sertifikatini tayyorlaydi (yo'q bo'lsa yaratadi).
    Server ishga tushishidan oldin (va trust bundle eksportidan oldin) bir
    marta chaqirilishi kerak. Idempotent."""
    _load_or_create_signing_key()
    if not (os.path.isfile(TLS_CERT_PATH) and os.path.isfile(TLS_KEY_PATH)):
        _create_tls_cert()


def regenerate_identity():
    """Kalit va sertifikatni QAYTA yaratadi (server IP o'zgarganda admin
    chaqiradi). DIQQAT: fingerprint o'zgaradi — barcha kiosklar yangi trust
    fayli bilan qayta provisioning qilinishi kerak."""
    for p in (SIGNING_KEY_PATH, TLS_CERT_PATH, TLS_KEY_PATH):
        try:
            os.remove(p)
        except OSError:
            pass
    ensure_identity()


# --- Ochiq ma'lumot (kiosklarga) --------------------------------------------
def public_key_b64():
    """Ed25519 ochiq kalitining xom 32 baytini base64 ko'rinishida (trust bundle).
    Kiosk beacon imzosini shu kalit bilan tekshiradi."""
    from cryptography.hazmat.primitives import serialization
    key = _load_or_create_signing_key()
    raw = key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw)
    return base64.b64encode(raw).decode("ascii")


def cert_pem_text():
    """TLS sertifikatining PEM matni (trust bundle + Trusted Root o'rnatish)."""
    ensure_identity()
    with open(TLS_CERT_PATH, encoding="ascii") as f:
        return f.read()


def cert_fingerprint():
    """TLS sertifikatining SHA-256 fingerprint'i (hex, ikki nuqtasiz).
    Kiosk requests'da pinning va beacon `fp` mosligini tekshirishda ishlatadi."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    ensure_identity()
    with open(TLS_CERT_PATH, "rb") as f:
        cert = x509.load_pem_x509_certificate(f.read())
    return cert.fingerprint(hashes.SHA256()).hex()


def sign(data: bytes) -> bytes:
    """Berilgan baytlarni Ed25519 maxfiy kalit bilan imzolaydi (beacon uchun)."""
    key = _load_or_create_signing_key()
    return key.sign(data)


def trust_bundle(url, api_key, name):
    """Kioskka beriladigan ishonch to'plami (dict). Sirlardan faqat api_key
    bor (kiosk->server autentifikatsiyasi uchun); qolgani ochiq."""
    return {
        "v": 1,
        "name": name,
        "url": url,
        "api_key": api_key,
        "public_key": public_key_b64(),
        "cert_fingerprint": cert_fingerprint(),
        "cert_pem": cert_pem_text(),
    }
