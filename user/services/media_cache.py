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
import threading

import requests
from PyQt6.QtCore import QThread

from core import config
from core import netpin

log = logging.getLogger(__name__)

# Hozir yuklanayotgan media holati — heartbeat orqali admin jonli ko'radi.
# {"id":int, "pct":int(-1 noma'lum), "title":str} yoki bo'sh {} (yuklash yo'q).
_cache_lock = threading.Lock()
_caching = {}


def caching_status():
    """Hozir yuklanayotgan media (id/pct/title) yoki {} — health heartbeat
    shuni yuboradi, admin dialogi jonli foizni shundan oladi."""
    with _cache_lock:
        return dict(_caching)


def _set_caching(item, pct):
    with _cache_lock:
        _caching.clear()
        _caching.update({"id": item.get("id"),
                         "title": item.get("title") or "",
                         "pct": int(pct)})


def _clear_caching():
    with _cache_lock:
        _caching.clear()

MEDIA_DIR = os.path.join(config.APP_DIR, "cache", "media")
# Diskda DOIM bo'sh qoldiriladigan zaxira (kiosk/Windows qotmasin). Mutlaq
# floor 3 GB; katta disklarда 8% gacha; lekin 12 GB dan oshmaydi (joy isrofi).
MIN_FREE = 3 * 1024 ** 3
RESERVE_PCT = 0.08
RESERVE_MAX = 12 * 1024 ** 3
SYNC_INTERVAL_S = 10 * 60       # to'liq sinx oralig'i (kick bilan tezlashadi)
CHUNK = 256 * 1024


def _reserve(total):
    """Shu disk uchun doim bo'sh qoldiriladigan joy (baytda)."""
    return min(RESERVE_MAX, max(MIN_FREE, int((total or 0) * RESERVE_PCT)))
AV_TYPES = ("movie", "cartoon", "music", "audiobook", "book")  # kitob audiosi ham


def _name(item):
    return f"{item['id']}__{os.path.basename(item.get('file_path') or '')}"


def _ad_name(ad):
    """Reklama fayli nomi — 'ad_' prefiksi bilan (kontentdan ajralib tursin)."""
    return f"ad_{ad['id']}__{os.path.basename(ad.get('media_path') or '')}"


def ad_local_path(ad_id):
    """Reklamaning lokal keshdagi TAYYOR fayli yoki None (oflaynда ham ko'rsatish)."""
    try:
        pref = f"ad_{ad_id}__"
        for fn in os.listdir(MEDIA_DIR):
            if fn.startswith(pref) and not fn.endswith(".part"):
                return os.path.join(MEDIA_DIR, fn)
    except OSError:
        pass
    return None


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


# Shu QURILMA uchun lokal kesh ruxsati (server heartbeat javobidan keladi —
# admin xotirasiz kioskда o'chirib qo'yishi mumkin). True — yoqiq.
_device_allowed = True


def set_device_allowed(v):
    """Server bu kioskда keshni yoqdi/o'chirdi (heartbeat javobi)."""
    global _device_allowed
    _device_allowed = bool(v)


def server_enabled():
    """Lokal kesh yoqilganmi? Ikki shart: (1) GLOBAL sozlama (Sozlamalar ->
    "Lokal media kesh"); (2) SHU QURILMA uchun ruxsat (admin xotirasiz
    kioskда o'chirsa). Biri o'chiq bo'lsa — yuklanmaydi."""
    if not _device_allowed:
        return False
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
                # Reklamalar DOIM keshlanadi (kontent keshi o'chiq bo'lsa ham —
                # oflaynда ham ko'rsatish uchun; ular kichik, joy ham tekshiriladi)
                if not self.api.offline:
                    self._sync_ads()
                # Kontent — faqat sozlama/qurilma ruxsati bo'lsa
                if server_enabled():
                    self._sync_content()
                _clear_caching()
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

    def _sync_ads(self):
        """Reklama media fayllarini keshlaydi (HAMMASI, doim) — oflaynда ham
        ko'rsatish uchun. Kontent keshidan mustaqil ishlaydi."""
        try:
            ads = self.api.get_ads()
        except Exception:
            return
        if self.api.offline:
            return
        want = {_ad_name(a): a for a in ads if a.get("media_path")}
        # Serverda yo'q reklama fayllarini o'chiramiz (faqat ad_ fayllari)
        for fn in os.listdir(MEDIA_DIR):
            if not fn.startswith("ad_"):
                continue
            base = fn[:-5] if fn.endswith(".part") else fn
            if base not in want:
                try:
                    os.remove(os.path.join(MEDIA_DIR, fn))
                except OSError:
                    pass
        for fn, a in want.items():
            if self._stop:
                return
            dst = os.path.join(MEDIA_DIR, fn)
            if not os.path.exists(dst):
                self._download(a, dst, url=self.api.ad_media_url(a["id"]))

    def _sync_content(self):
        items = self.api.get_content()
        if self.api.offline:
            # Oflaynda yuklab bo'lmaydi; o'chirish ham xavfli (ro'yxat eski
            # keshdan kelgan bo'lishi mumkin) — serverni kutamiz.
            log.info("Media sinx: OFLAYN — server bilan aloqa yo'q, "
                     "yuklash o'tkazildi")
            return
        # Admin har kontentga alohida belgi qo'yadi (cache_enabled) —
        # belgilanmaganlari yuklanmaydi; belgisi olib tashlansa keyingi
        # sinxda lokal nusxasi ham o'chadi (want'dan chiqib qoladi).
        want = {_name(it): it for it in items
                if it.get("type") in AV_TYPES and it.get("file_path")
                and (it.get("cache_enabled") is None or it.get("cache_enabled"))}
        todo = [fn for fn in want
                if not os.path.exists(os.path.join(MEDIA_DIR, fn))]
        log.info("Media sinx: %d ta belgilangan media, %d yuklanishi kerak",
                 len(want), len(todo))
        # Serverda yo'q kontent fayllarini o'chiramiz (reklama — ad_ — tegmaymiz)
        for fn in os.listdir(MEDIA_DIR):
            if fn.startswith("ad_"):
                continue
            base = fn[:-5] if fn.endswith(".part") else fn
            if base not in want:
                try:
                    os.remove(os.path.join(MEDIA_DIR, fn))
                    log.info("Media kesh: o'chirildi %s (serverda yo'q)", fn)
                except OSError:
                    pass
        # Yetishmayotganlarini KETMA-KET (har faylda joy tekshiriladi)
        for fn, it in want.items():
            if self._stop:
                return
            dst = os.path.join(MEDIA_DIR, fn)
            if not os.path.exists(dst):
                self._download(it, dst)

    def _download(self, it, dst, url=None):
        tmp = dst + ".part"
        try:
            if url is None:
                url = self.api.stream_url(it["id"])
            # stream=True — javob o'qilgunicha session ochiq tursin (pin bilan)
            with netpin.session() as _s, _s.get(url, stream=True, timeout=15) as r:
                r.raise_for_status()
                size = int(r.headers.get("content-length") or 0)
                du = shutil.disk_usage(MEDIA_DIR)
                free = du.free
                reserve = _reserve(du.total)   # doim shuncha bo'sh qolsin
                if free - size < reserve:
                    log.info("Media kesh: joy yetmaydi — #%s o'tkazildi "
                             "(%.0f MB kerak, %.0f MB ishlatsa bo'ladi, "
                             "%.1f GB zaxira qoladi)",
                             it["id"], size / 1e6,
                             max(0, free - reserve) / 1e6, reserve / 1024 ** 3)
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
                last_pct = -2
                _set_caching(it, 0 if size > 0 else -1)   # admin jonli ko'rsin
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(CHUNK):
                        if self._stop:
                            raise InterruptedError
                        f.write(chunk)
                        written += len(chunk)
                        # Yuklash foizi — har 1% o'zgarganda holatni yangilaymiz
                        # (heartbeat keyingi safar shuni admin'ga yetkazadi)
                        if size > 0:
                            pct = min(100, int(written * 100 / size))
                            if pct != last_pct:
                                last_pct = pct
                                _set_caching(it, pct)
                        # Davomiyligi noma'lum (chunked) fayl diskni/chegarani
                        # to'ldirib yubormasin — vaqti-vaqti bilan tekshiramiz
                        if written % (CHUNK * 64) < CHUNK:
                            if shutil.disk_usage(MEDIA_DIR).free < reserve:
                                raise OSError("bo'sh joy tugadi")
                            if limit and used + written > limit:
                                raise OSError("kesh hajmi chegarasi")
            # Yuklab olingan hajm e'lon qilingan content-length'ga teng emasmi —
            # uzilgan/qisman yuklash. Bunday faylni "tayyor" deb saqlamaymiz
            # (aks holda buzilgan media abadiy lokal keshda qolib ketardi).
            if size > 0 and written != size:
                raise OSError(f"to'liq yuklanmadi ({written}/{size} bayt)")
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
