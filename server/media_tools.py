"""Media fayllar bilan ishlash yordamchilari.

`ensure_faststart` — MP4/MOV videoni progressive HTTP striming uchun optimallaydi:
`moov` atomini fayl BOSHIGA ko'chiradi (faststart). Busiz mobil brauzerlar
katta faylni o'ynatishдан oldin uzoq buferlaydi va qotadi (moov oxirда bo'lsa
pleyer indeksni topish uchun faylning oxirигача so'rov yuboradi).

Ishlashi: `-c copy` (qayta kodlash EMAS — sifat yo'qolmaydi, tez), faqat
konteyner qayta yoziladi. Allaqachon faststart bo'lsa yoki ffmpeg topilmasa —
hech narsa qilmaydi. Xato yuz bersa asl fayl daxlsiz qoladi (best-effort).
"""
from __future__ import annotations

import os
import shutil
import struct
import subprocess

VIDEO_EXTS = {".mp4", ".m4v", ".mov"}


def _top_atoms(path: str, limit: int = 12) -> list[str]:
    """MP4 yuqori darajali atomlar tartibini (masalan ftyp, moov, mdat) o'qiydi."""
    order: list[str] = []
    try:
        with open(path, "rb") as f:
            total = os.path.getsize(path)
            off = 0
            for _ in range(limit):
                f.seek(off)
                hdr = f.read(8)
                if len(hdr) < 8:
                    break
                size = struct.unpack(">I", hdr[:4])[0]
                typ = hdr[4:8].decode("latin1", "replace")
                order.append(typ)
                if size == 1:                       # 64-bitli o'lcham
                    size = struct.unpack(">Q", f.read(8))[0]
                if size == 0:
                    break
                off += size
                if off >= total or ("moov" in order and "mdat" in order):
                    break
    except OSError:
        pass
    return order


def is_faststart(path: str) -> bool:
    """`moov` atomi `mdat`dan oldin kelsa True (progressive striming uchun tayyor)."""
    a = _top_atoms(path)
    mo = a.index("moov") if "moov" in a else 999
    md = a.index("mdat") if "mdat" in a else 999
    return mo < md


def ensure_faststart(path: str) -> bool:
    """Video faststart bo'lmasa remux qiladi. Tuzatilса True qaytaradi."""
    ext = os.path.splitext(path)[1].lower()
    if ext not in VIDEO_EXTS or not os.path.isfile(path):
        return False
    if is_faststart(path):
        return False
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False
    tmp = path + ".fast.tmp.mp4"
    try:
        r = subprocess.run(
            [ffmpeg, "-y", "-v", "error", "-i", path, "-map", "0",
             "-c", "copy", "-movflags", "+faststart", tmp],
            capture_output=True, text=True,
        )
        if r.returncode != 0 or not os.path.exists(tmp):
            if os.path.exists(tmp):
                os.remove(tmp)
            return False
        # Tekshiruv: hajm oqilona + moov endi haqiqatan oldinda
        if os.path.getsize(tmp) < os.path.getsize(path) * 0.85 or not is_faststart(tmp):
            os.remove(tmp)
            return False
        os.replace(tmp, path)                        # atomik almashtirish
        return True
    except Exception:                                # noqa: BLE001 — best-effort
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        return False
