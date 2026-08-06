"""
storage.py — Kontent fayllari ombori (content-addressed).

Fayl **sha256 bo'yicha** saqlanadi: `storage/ab/cd/<sha256>`. Shundan kelib
chiqadigan foydalar:
  - **dedup:** bir xil kino ikki marta yuklansa diskda bitta nusxa bo'ladi;
  - **tekshirish:** poyezd serveri faylni tortib olgach sha256'ni solishtiradi,
    ya'ni yarim yuklangan/buzilgan fayl darhol aniqlanadi;
  - **qayta yuborishni tejash:** serverда shu sha bor bo'lsa SIM-trafik
    behuda ketmaydi (agent tekshiradi).

Kengaytma faylga qo'shilmaydi — asl nom va MIME bazada (`content.media_name`).
"""
import hashlib
import logging
import mimetypes
import os
import shutil
from email.utils import formatdate

from fastapi import Request
from fastapi.responses import Response, StreamingResponse

import config

log = logging.getLogger("cloud.storage")

CHUNK = 1024 * 1024


def init():
    os.makedirs(config.STORAGE_DIR, exist_ok=True)
    os.makedirs(config.TMP_DIR, exist_ok=True)
    _clean_tmp()


def _clean_tmp():
    """Tugallanmagan yuklashlardan qolgan vaqtinchalik fayllarni tozalaydi."""
    try:
        for n in os.listdir(config.TMP_DIR):
            p = os.path.join(config.TMP_DIR, n)
            if os.path.isfile(p):
                os.remove(p)
    except OSError:
        pass


def blob_path(sha):
    """sha256 -> diskdagi to'liq yo'l (papkalar yaratilmaydi)."""
    if not sha or len(sha) != 64 or not all(c in "0123456789abcdef" for c in sha):
        return None
    return os.path.join(config.STORAGE_DIR, sha[:2], sha[2:4], sha)


def exists(sha):
    p = blob_path(sha)
    return bool(p) and os.path.isfile(p)


def size_of(sha):
    p = blob_path(sha)
    try:
        return os.path.getsize(p) if p else 0
    except OSError:
        return 0


async def save_upload(request: Request, max_bytes=None):
    """So'rov tanasini (raw body) oqim qilib diskka yozadi va sha256 hisoblaydi.

    Multipart ISHLATILMAYDI — 8 GB kino uchun oddiy `PUT` tanasi ancha arzon
    (xotirada bufer yo'q, `python-multipart` ham kerak emas). Brauzer tomonida
    XHR `send(file)` bilan yuboriladi (progress hodisalari bor).

    Qaytaradi: (sha256, size, dedup) — `dedup=True` bo'lsa fayl omborda
    allaqachon bor edi va diskka qaytadan yozilmadi (panel shuni ko'rsatadi).
    """
    max_bytes = max_bytes or config.MAX_UPLOAD_BYTES
    init()
    tmp = os.path.join(config.TMP_DIR, os.urandom(8).hex())
    h = hashlib.sha256()
    total = 0
    try:
        with open(tmp, "wb") as f:
            async for chunk in request.stream():
                if not chunk:
                    continue
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError("fayl juda katta")
                h.update(chunk)
                f.write(chunk)
        if total == 0:
            raise ValueError("bo'sh fayl")
        sha = h.hexdigest()
        dest = blob_path(sha)
        if os.path.isfile(dest):
            os.remove(tmp)                     # dedup — nusxa saqlanmaydi
            log.info("Yuklash: dedup %s (%d bayt)", sha[:12], total)
            return sha, total, True
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        os.replace(tmp, dest)                  # atomik: yarim fayl ko'rinmaydi
        log.info("Yuklash: yangi blob %s (%d bayt)", sha[:12], total)
        return sha, total, False
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def gc(used_shas):
    """Bazada ishlatilmayotgan bloblarni o'chiradi. (o'chirilgan_soni, bayt)."""
    removed, freed = 0, 0
    for root, _dirs, files in os.walk(config.STORAGE_DIR):
        if os.path.abspath(root).startswith(os.path.abspath(config.TMP_DIR)):
            continue
        for name in files:
            if len(name) != 64:
                continue
            if name in used_shas:
                continue
            p = os.path.join(root, name)
            try:
                sz = os.path.getsize(p)
                os.remove(p)
                removed += 1
                freed += sz
            except OSError:
                pass
    if removed:
        log.info("Ombor tozalandi: %d yetim blob, %.1f MB", removed, freed / 1e6)
    return removed, freed


def usage():
    """Ombor holati: (fayl soni, band bayt, diskda bo'sh bayt)."""
    n, total = 0, 0
    for root, _dirs, files in os.walk(config.STORAGE_DIR):
        for name in files:
            if len(name) != 64:
                continue
            n += 1
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    try:
        free = shutil.disk_usage(config.STORAGE_DIR).free
    except OSError:
        free = 0
    return n, total, free


# ------------------------------------------------------------ Range berish
def _file_tag(path, file_size):
    raw = f"{file_size}-{os.path.getmtime(path)}".encode()
    return '"' + hashlib.md5(raw).hexdigest() + '"'


def _parse_range(range_header, file_size):
    """'bytes=START-END' -> (start, end). Noto'g'ri bo'lsa ValueError (-> 416).
    Poyezd serveri uzilgan yuklashni `bytes=<davom>-` bilan davom ettiradi."""
    units, _, rng = range_header.partition("=")
    if units.strip() != "bytes" or "," in rng:
        raise ValueError("qo'llab-quvvatlanmaydigan range")
    s, _, e = rng.partition("-")
    s, e = s.strip(), e.strip()
    if s == "" and e == "":
        raise ValueError("bo'sh range")
    if s == "":
        length = int(e)
        if length <= 0:
            raise ValueError("noto'g'ri suffix")
        start, end = max(0, file_size - length), file_size - 1
    else:
        start = int(s)
        end = min(int(e), file_size - 1) if e else file_size - 1
    if start > end or start >= file_size:
        raise ValueError("chegaradan tashqari")
    return start, end


def range_response(path, request: Request, filename=None, chunk=CHUNK):
    """Faylni HTTP Range (206) bilan oqim qilib beradi — server/main.py dagi
    striming bilan bir xil semantika (ETag, Last-Modified, 416)."""
    file_size = os.path.getsize(path)
    media_type = (mimetypes.guess_type(filename or path)[0]
                  or "application/octet-stream")
    etag = _file_tag(path, file_size)
    base = {
        "Accept-Ranges": "bytes",
        "ETag": etag,
        "Last-Modified": formatdate(os.path.getmtime(path), usegmt=True),
        "Cache-Control": "private, max-age=3600",
    }
    if filename:
        base["Content-Disposition"] = f'inline; filename="{_ascii(filename)}"'

    start, end, status = 0, file_size - 1, 200
    rh = request.headers.get("range")
    if rh:
        try:
            start, end = _parse_range(rh, file_size)
            status = 206
        except ValueError:
            return Response(status_code=416,
                            headers={**base,
                                     "Content-Range": f"bytes */{file_size}"})
    length = end - start + 1

    def body():
        with open(path, "rb") as f:
            f.seek(start)
            left = length
            while left > 0:
                data = f.read(min(chunk, left))
                if not data:
                    break
                left -= len(data)
                yield data

    headers = {**base, "Content-Length": str(length)}
    if status == 206:
        headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
    return StreamingResponse(body(), status_code=status,
                             media_type=media_type, headers=headers)


def _ascii(name):
    """Content-Disposition sarlavhasi uchun xavfsiz nom (kirill/bo'shliq)."""
    return "".join(ch if 32 < ord(ch) < 127 and ch != '"' else "_" for ch in name)
