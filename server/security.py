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


def _restrict_key_file(path):
    """Maxfiy kalit fayliga OS ruxsatlarini cheklaydi (faqat egasi + tizim
    o'qiy olsin). Windows'da icacls bilan merosni o'chirib, joriy foydalanuvchi,
    SYSTEM va Administrators'ga cheklaymiz. POSIX'da chmod 600.

    Eng yaxshi-harakat: muvaffaqiyatsiz bo'lsa faqat ogohlantiramiz (kalitlar
    baribir BASE_DIR'da, git'ga tushmaydi — bu qo'shimcha himoya qatlami)."""
    if not os.path.isfile(path):
        return
    try:
        if os.name == "nt":
            import subprocess
            user = os.environ.get("USERNAME") or ""
            # Merosni o'chir (/inheritance:r), so'ng faqat kerakli egalarga ruxsat
            grants = ["/grant:r", "*S-1-5-18:F",      # SYSTEM
                      "/grant:r", "*S-1-5-32-544:F"]  # Administrators
            if user:
                grants += ["/grant:r", f"{user}:F"]
            subprocess.run(["icacls", path, "/inheritance:r", *grants],
                           check=False, capture_output=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        else:
            os.chmod(path, 0o600)
    except Exception as e:                              # noqa: BLE001
        log.warning("Kalit fayli ruxsatini cheklab bo'lmadi (%s): %s", path, e)


def _write_private(path, data: bytes):
    """Maxfiy kalitni YOZISH paytidan boshlab cheklangan ruxsat bilan yaratadi
    (POSIX'da 0o600 — yozilgandan keyin cheklash oynasini yopadi). Windows'da
    rejim e'tiborga olinmaydi, _restrict_key_file (icacls) ketidan ishlaydi."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    fd = os.open(path, flags, 0o600)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)


def _local_ipv4s():
    """Serverning LAN IPv4 manzillari (sertifikat SAN + discovery beacon + admin
    ekrani). helpers.local_ips ham shuni ishlatadi (PyQt'siz).

    HAQIQIY lokal tarmoq manzilini afzal ko'radi: agar private LAN (192.168/10/
    172.16) topilsa — FAQAT shularni qaytaradi. CGNAT/Tailscale (100.64/10),
    APIPA (169.254) va loopback chiqarib tashlanadi — boshqa kompyuterlar
    ulardan serverga ULANOLMAYDI (faqat real LAN orqali ulanishadi)."""
    import ipaddress
    # ASOSIY manzil: internetga/gateway'ga marshrutlangan interfeys IP'si. Bu
    # AYNAN boshqa kompyuterlar ko'radigan real LAN manzili (WSL/Hyper-V/Docker
    # virtual adapterlari emas). UDP "ulanish" paket yubormaydi, faqat manbani
    # aniqlaydi.
    primary = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        primary = s.getsockname()[0]
        s.close()
    except OSError:
        pass

    cands = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None,
                                       socket.AF_INET):
            cands.add(info[4][0])
    except socket.gaierror:
        pass
    if primary:
        cands.add(primary)

    _CGNAT = ipaddress.ip_network("100.64.0.0/10")   # Tailscale/CGNAT

    def _rank(ip):
        try:
            a = ipaddress.ip_address(ip)
        except ValueError:
            return None
        if a.is_loopback or a.is_link_local:          # 127.*, 169.254.*
            return None
        lan = a.is_private and a not in _CGNAT
        is_primary = (ip == primary)
        # 0 = asosiy real LAN (eng afzal); 1 = boshqa private (virtual adapter
        # bo'lishi mumkin); 3/4 = CGNAT/public. Pastroq daraja — afzalroq.
        if lan:
            return (0 if is_primary else 1, ip)
        return (3 if is_primary else 4, ip)

    ranked = sorted(filter(None, (_rank(ip) for ip in cands)))
    if not ranked:
        return []
    # Faqat ENG YAXSHI darajadagilarni qaytaramiz — asosiy real LAN topilsa,
    # virtual/CGNAT/public manzillar (boshqa PC ko'rolmaydigan) tashlanadi.
    best = ranked[0][0]
    return [ip for tier, ip in ranked if tier == best]


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
    _write_private(SIGNING_KEY_PATH, pem)
    _restrict_key_file(SIGNING_KEY_PATH)
    log.info("Yangi Ed25519 imzo kaliti yaratildi: %s", SIGNING_KEY_PATH)
    return key


# --- Self-signed TLS sertifikat ---------------------------------------------
def _create_tls_cert():
    """LAN IP'lari SAN'ga yozilgan self-signed sertifikat yaratadi (CA:TRUE —
    kioskда Trusted Root'ga qo'shilganda va pin sifatida ishlatilganda mos)."""
    import ipaddress
    from cryptography import x509
    from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
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
        # CA:TRUE — self-signed cert kioskда Trusted Root sifatida ishlaydi
        # (VLC/ws ishonch o'chog'i). Lekin key_cert_sign=False: kalit sizib
        # chiqsa ham BOSHQA domenlarga ishonchli cert yasab bo'lmaydi (faqat
        # shu serverni tasdiqlaydi). EKU=serverAuth — faqat server sifatida.
        .add_extension(x509.BasicConstraints(ca=True, path_length=0),
                       critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=True, key_encipherment=True,
            key_cert_sign=False, crl_sign=False, content_commitment=False,
            data_encipherment=False, key_agreement=False,
            encipher_only=False, decipher_only=False), critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),
                       critical=False)
        .sign(key, hashes.SHA256()))

    _write_private(TLS_KEY_PATH, key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption()))
    _restrict_key_file(TLS_KEY_PATH)
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
