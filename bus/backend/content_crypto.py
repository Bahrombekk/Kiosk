"""
content_crypto.py — kontent fayllarни diskда AES-256-CTR bilan SHIFRLAB saqlaydi.

Maqsad: `C:\\Avtobus\\content\\` dagi media/muqova/kitob fayllari nusxa qilinса
KALITSIZ FOYDASIZ bo'lsin. Dastur oqim (stream) paytida deshifrlaydi.

Nega CTR: video seek / HTTP Range uchun istalgan bayt oralig'ini mustaqil
deshifrlash kerak. CTR rejimida blok indeksi bo'yicha kalit-oqim hisoblanadi —
faylni boshidan o'qimasdan o'rtasidan deshifrlab bo'ladi.

Fayl formati:  MAGIC(8) + nonce(16) + AES-256-CTR(plaintext)

Kalit (_MASTER_KEY): build.ps1 buni Nuitka bilan `.pyd` (mashina kodi) ga
kompilyatsiya qiladi ($Secret ro'yxatida) — manba ko'rinmaydi. Bu CASUAL
nusxalashни (operator, texnik) to'sadi. HALOL: fizik/reverse-engineer kirишли
odam baribir topishi mumkin — mutlaq himoya yo'q, lekin darajани keskin oshiradi.

⚠ ISHLAB CHIQARISHДА _MASTER_KEY ni BIR MARTA o'zgartiring va build mashinasida
xavfsiz saqlang. Kalit almashса — eski shifrlangan fayllar OCHILMAYDI
(qurilma bulutdan qayta yuklab, yangi kalit bilan shifrlaydi).
"""
import os
import logging
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

log = logging.getLogger("kiosk.crypto")

MAGIC = b"AVBENC01"
_HEADER = len(MAGIC) + 16                      # 8 + 16 nonce = 24 bayt
_CHUNK = 1024 * 1024

# 32 bayt (256-bit) master kalit. NUITKA .pyd ga kiradi.
_MASTER_KEY = bytes.fromhex(
    "2fbf66f4538ab2eaf31a002c7ebbc37e1ee187401e36607ab6a9f48b7fb60893")


def _ctr(nonce: bytes, block_index: int) -> bytes:
    """`block_index`-blokdan boshlash uchun CTR hisoblagichi (nonce + index)."""
    val = (int.from_bytes(nonce, "big") + block_index) & ((1 << 128) - 1)
    return val.to_bytes(16, "big")


def is_encrypted(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            return f.read(len(MAGIC)) == MAGIC
    except OSError:
        return False


def plaintext_size(path: str) -> int:
    """Deshifrlanган (asl) o'lcham — Range hisoblari uchun."""
    try:
        sz = os.path.getsize(path)
    except OSError:
        return 0
    return max(0, sz - _HEADER) if is_encrypted(path) else sz


def encrypt_file(src: str, dst: str) -> None:
    """`src` (ochiq) ni shifrlab `dst` ga yozadi (MAGIC+nonce+ciphertext)."""
    nonce = os.urandom(16)
    enc = Cipher(algorithms.AES(_MASTER_KEY), modes.CTR(nonce)).encryptor()
    with open(src, "rb") as fi, open(dst, "wb") as fo:
        fo.write(MAGIC)
        fo.write(nonce)
        while True:
            chunk = fi.read(_CHUNK)
            if not chunk:
                break
            fo.write(enc.update(chunk))
        fo.write(enc.finalize())


def encrypt_inplace(path: str) -> bool:
    """Ochiq faylni O'RNIDA shifrlaydi (atomik: .enctmp -> replace). Allaqachon
    shifrlangан bo'lsa hech nima qilmaydi. True = shifrlandi."""
    if is_encrypted(path):
        return False
    tmp = path + ".enctmp"
    try:
        encrypt_file(path, tmp)
        os.replace(tmp, path)
        return True
    except OSError:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass
        raise


def decrypt_range(path: str, start: int, length: int, chunk: int = _CHUNK):
    """[start, start+length) ASL (plaintext) oralig'ini yield qiladi. Fayl
    shifrlanmagan (legacy) bo'lsa — oddiy o'qiydi. Video seek shu orqali ishlaydi."""
    with open(path, "rb") as f:
        if f.read(len(MAGIC)) != MAGIC:
            # legacy ochiq fayl
            f.seek(start)
            rem = length
            while rem > 0:
                d = f.read(min(chunk, rem))
                if not d:
                    break
                rem -= len(d)
                yield d
            return
        nonce = f.read(16)
        block = start // 16
        skip = start - block * 16
        dec = Cipher(algorithms.AES(_MASTER_KEY),
                     modes.CTR(_ctr(nonce, block))).decryptor()
        f.seek(_HEADER + block * 16)
        need = skip + length          # o'qib-deshifrlanadigan shifrli baytlar
        produced = 0
        while need > 0:
            data = f.read(min(chunk, need))
            if not data:
                break
            need -= len(data)
            out = dec.update(data)
            if skip:
                if len(out) <= skip:
                    skip -= len(out)
                    continue
                out = out[skip:]
                skip = 0
            if produced + len(out) > length:
                out = out[:length - produced]
            produced += len(out)
            if out:
                yield out
            if produced >= length:
                break


def read_all(path: str) -> bytes:
    """To'liq ASL mazmun (kichik fayllar: muqova, kitob matni)."""
    with open(path, "rb") as f:
        head = f.read(len(MAGIC))
        if head != MAGIC:
            f.seek(0)
            return f.read()
        nonce = f.read(16)
        dec = Cipher(algorithms.AES(_MASTER_KEY),
                     modes.CTR(nonce)).decryptor()
        return dec.update(f.read()) + dec.finalize()


def migrate_dirs(dirs) -> int:
    """Berilган papkalardagi BARCHA ochiq fayllarni o'rniga shifrlaydi (bir
    martalik migratsiya — avval o'rnatilган ochiq kontent uchun). Shifrlanганlarni
    o'tkazib yuboradi. Nechta shifrlanganini qaytaradi. Fonда chaqiriladi."""
    n = 0
    for d in dirs:
        if not d or not os.path.isdir(d):
            continue
        for root, _, files in os.walk(d):
            for name in files:
                if name.endswith((".enctmp", ".part", ".svg")):
                    continue
                p = os.path.join(root, name)
                try:
                    if encrypt_inplace(p):
                        n += 1
                except OSError as e:
                    log.warning("shifrlash xatosi %s: %s", name, e)
    if n:
        log.info("Kontent shifrlash: %d fayl shifrlandi", n)
    return n
