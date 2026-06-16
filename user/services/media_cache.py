"""
media_cache.py — Kontent medialarini kiosk lokal diskiga sinxlash.

Xotirasi yetarli kioskda video/audio fayllar FONDA (kiosk onlayn payti)
lokal keshga yuklab qo'yiladi va server bilan sinxron turadi:

  - ijro lokal fayldan bo'ladi (api.play_url) — serverga/tarmoqqa yuk
    tushmaydi, oflaynda ham tomosha qilinadi;
  - admin kontentni O'CHIRSA — keyingi sinxda lokal nusxa ham o'chadi;
  - YANGI kontent yuklansa — fonda kioskka tortib olinadi;
  - fayl ALMASHTIRILSA (nomi o'zgaradi) — eskisi o'chib, yangisi yuklanadi.

Joy siyosati: har fayldan oldin diskda kamida MIN_FREE bo'sh joy qolishi
tekshiriladi — sig'magani shunchaki o'tkazib yuboriladi (striming ishlayveradi).
Butunlay o'chirish: server.txt'da `cache=0`.

Fayl nomi sxemasi: cache/media/<content_id>__<asl_fayl_nomi> — id bo'yicha
sinxlash va fayl almashganini aniqlash uchun.
"""
import logging
import os
import shutil

import requests
from PyQt6.QtCore import QThread

from core import config
from core import netpin

log = logging.getLogger(__name__)

MEDIA_DIR = os.path.join(config.APP_DIR, "cache", "media")
MIN_FREE = 2 * 1024 ** 3        # diskda kamida 2 GB bo'sh joy qolsin
SYNC_INTERVAL_S = 10 * 60       # to'liq sinx oralig'i (kick bilan tezlashadi)
CHUNK = 256 * 1024
AV_TYPES = ("movie", "cartoon", "music", "audiobook", "book")  # kitob audiosi ham


def _name(item):
    return f"{item['id']}__{os.path.basename(item.get('file_path') or '')}"


def local_path(content_id):
    """Lokal keshdagi TAYYOR fayl yo'li yoki None (.part — tugallanmagan)."""
    try:
        pref = f"{content_id}__"
        for fn in os.listdir(MEDIA_DIR):
            if fn.startswith(pref) and not fn.endswith(".part"):
                return os.path.join(MEDIA_DIR, fn)
    except OSError:
        pass
    return None


def count():
    """Keshlangan media soni (heartbeat orqali admin jadvalida ko'rinadi)."""
    try:
        return sum(1 for f in os.listdir(MEDIA_DIR)
                   if not f.endswith(".part"))
    except OSError:
        return 0


def cached_ids():
    """Keshlangan kontent id'lari — admin har kioskda nima yuklanganini
    ko'rishi uchun heartbeat bilan yuboriladi."""
    ids = []
    try:
        for fn in os.listdir(MEDIA_DIR):
            if fn.endswith(".part"):
                continue
            pre = fn.split("__", 1)[0]
            if pre.isdigit():
                ids.append(int(pre))
    except OSError:
        pass
    return sorted(ids)


def server_enabled():
    """Admin sozlamasi (Sozlamalar -> "Lokal media kesh"): '0' — yuklash
    to'xtaydi (mavjud fayllar qoladi, ijro lokal nusxadan davom etadi)."""
    from core import cache
    hit = cache.load_json("settings")
    if hit:
        return str((hit[0] or {}).get("media_cache") or "1") != "0"
    return True


def _dir_size():
    """Lokal keshdagi barcha fayllar hajmi (bayt) — hajm cheklovini hisoblash."""
    total = 0
    try:
        for fn in os.listdir(MEDIA_DIR):
            try:
                total += os.path.getsize(os.path.join(MEDIA_DIR, fn))
            except OSError:
                pass
    except OSError:
        pass
    return total


def cache_limit_bytes():
    """Admin «Kesh hajmi cheklovi» (GB) bayt ko'rinishida; 0 — cheklov yo'q
    (faqat MIN_FREE bo'sh joy siyosati ishlaydi)."""
    from core import cache
    hit = cache.load_json("settings")
    if hit:
        try:
            gb = float((hit[0] or {}).get("cache_limit_gb") or 0)
        except (TypeError, ValueError):
            gb = 0
        if gb > 0:
            return int(gb * 1024 ** 3)
    return 0


class MediaCacheSync(QThread):
    """Fonda ishlaydigan sinx oqimi: davriy (yoki kick() bilan darhol)
    serverdagi ro'yxat bilan lokal keshni tenglashtiradi."""

    def __init__(self, api):
        super().__init__()
        self.api = api
        self._stop = False
        self._clear_req = False
        import threading
        self._wake = threading.Event()

    # --- boshqaruv ---
    def kick(self):
        """Darhol sinx (reconnect bo'lganda main.py chaqiradi)."""
        self._wake.set()

    def clear(self):
        """Lokal keshni tozalashni so'raydi (admin masofadan buyrug'i).
        Fayllar bilan ishlash bitta oqimda qolsin — o'chirish sinx oqimida
        bajariladi (bu yer faqat bayroq qo'yib uyg'otadi)."""
        self._clear_req = True
        self._wake.set()

    def stop(self):
        self._stop = True
        self._wake.set()

    # --- asosiy sikl ---
    def run(self):
        if config.MEDIA_CACHE_DISABLED:
            log.info("Lokal media kesh o'chirilgan (cache=0)")
            return
        os.makedirs(MEDIA_DIR, exist_ok=True)
        while not self._stop:
            try:
                # Admin «keshni tozalash» buyrug'i — avval o'chiramiz
                if self._clear_req:
                    self._clear_req = False
                    self._clear_all()
                # Admin sozlamasi: kesh o'chirilgan bo'lsa yuklamaymiz
                # (sozlama yoqilishini kutib tekshirib turamiz)
                if server_enabled():
                    self._sync_once()
            except Exception:
                log.exception("Media sinxda kutilmagan xato")
            self._wake.wait(SYNC_INTERVAL_S)
            self._wake.clear()

    def _clear_all(self):
        """Keshdagi barcha fayllarni o'chiradi (admin buyrug'i bo'yicha)."""
        removed = 0
        try:
            for fn in os.listdir(MEDIA_DIR):
                try:
                    os.remove(os.path.join(MEDIA_DIR, fn))
                    removed += 1
                except OSError:
                    pass   # ijroda band fayl (Windows) — o'tkazib yuboramiz
        except OSError:
            pass
        log.info("Lokal kesh tozalandi (admin buyrug'i): %d fayl o'chirildi",
                 removed)

    def _sync_once(self):
        items = self.api.get_content()
        if self.api.offline:
            # Oflaynda yuklab bo'lmaydi; o'chirish ham xavfli (ro'yxat eski
            # keshdan kelgan bo'lishi mumkin) — serverni kutamiz.
            return
        # Admin har kontentga alohida belgi qo'yadi (cache_enabled) —
        # belgilanmaganlari yuklanmaydi; belgisi olib tashlansa keyingi
        # sinxda lokal nusxasi ham o'chadi (want'dan chiqib qoladi).
        want = {_name(it): it for it in items
                if it.get("type") in AV_TYPES and it.get("file_path")
                and (it.get("cache_enabled") is None or it.get("cache_enabled"))}
        # 1) Serverda yo'q (o'chirilgan/almashtirilgan) fayllarni o'chiramiz
        for fn in os.listdir(MEDIA_DIR):
            base = fn[:-5] if fn.endswith(".part") else fn
            if base not in want:
                try:
                    os.remove(os.path.join(MEDIA_DIR, fn))
                    log.info("Media kesh: o'chirildi %s (serverda yo'q)", fn)
                except OSError:
                    pass
        # 2) Yetishmayotganlarini KETMA-KET yuklaymiz (tarmoqni band qilmaslik
        #    uchun bittadan; har faylda joy tekshiriladi)
        for fn, it in want.items():
            if self._stop:
                return
            dst = os.path.join(MEDIA_DIR, fn)
            if not os.path.exists(dst):
                self._download(it, dst)

    def _download(self, it, dst):
        tmp = dst + ".part"
        try:
            url = self.api.stream_url(it["id"])
            # stream=True — javob o'qilgunicha session ochiq tursin (pin bilan)
            with netpin.session() as _s, _s.get(url, stream=True, timeout=15) as r:
                r.raise_for_status()
                size = int(r.headers.get("content-length") or 0)
                free = shutil.disk_usage(MEDIA_DIR).free
                if free - size < MIN_FREE:
                    log.info("Media kesh: joy yetmaydi — #%s o'tkazildi "
                             "(%.0f MB kerak, %.0f MB bo'sh)",
                             it["id"], size / 1e6, (free - MIN_FREE) / 1e6)
                    return
                # Admin «Kesh hajmi cheklovi» — joriy kesh + yangi fayl chegaradan
                # oshmasin (0 = cheklov yo'q). used yuklashdan oldin o'lchanadi.
                limit = cache_limit_bytes()
                used = _dir_size() if limit else 0
                if limit and used + size > limit:
                    log.info("Media kesh: hajm chegarasi (%.1f GB) — #%s "
                             "o'tkazildi", limit / 1024 ** 3, it["id"])
                    return
                written = 0
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(CHUNK):
                        if self._stop:
                            raise InterruptedError
                        f.write(chunk)
                        written += len(chunk)
                        # Davomiyligi noma'lum (chunked) fayl diskni/chegarani
                        # to'ldirib yubormasin — vaqti-vaqti bilan tekshiramiz
                        if written % (CHUNK * 64) < CHUNK:
                            if shutil.disk_usage(MEDIA_DIR).free < MIN_FREE:
                                raise OSError("bo'sh joy tugadi")
                            if limit and used + written > limit:
                                raise OSError("kesh hajmi chegarasi")
            os.replace(tmp, dst)
            log.info("Media kesh: yuklandi %s (%.0f MB)",
                     os.path.basename(dst), written / 1e6)
        except InterruptedError:
            self._rm(tmp)
        except Exception as e:                       # noqa: BLE001
            log.warning("Media kesh: #%s yuklab bo'lmadi (%s)",
                        it.get("id"), e)
            self._rm(tmp)

    @staticmethod
    def _rm(path):
        try:
            os.remove(path)
        except OSError:
            pass
