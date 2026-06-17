"""
api.py — Server bilan HTTP aloqa (REST API mijozi).

Foydalanuvchi ilovasi server bilan ikki kanal orqali ishlaydi (TZ 11):
  1) REST API — katalog va kontent (shu fayl).
  2) WebSocket — real vaqt buyruqlar (keyingi bosqichda: ws_client.py).

Hozircha (3-bosqich poydevori) faqat ulanishni tekshirish (health) kerak.
Qolgan metodlar tayyor turibdi — Videolar/Kitoblar bosqichlarida ishlatiladi.
"""
import logging
import time
from urllib.parse import quote

import requests

from core import cache
from core import config
from core import netpin

log = logging.getLogger(__name__)


class ApiClient:
    """Server REST API'siga so'rovlar yuboradigan oddiy mijoz.

    Oflayn rejim: katalog metodlari muvaffaqiyatda javobni lokal keshga
    yozadi; tarmoq xatosida keshdan qaytaradi (`self.offline = True`).
    Shunda server o'chsa ham kiosk oxirgi ko'rgan ro'yxatlarini ko'rsatadi
    (faqat striming ishlamaydi)."""

    def __init__(self, base_url=None, timeout=None):
        self.base_url = (base_url or config.SERVER_URL).rstrip("/")
        self.timeout = timeout or config.REQUEST_TIMEOUT
        self.offline = False   # oxirgi katalog so'rovi keshdan keldimi?
        self.last_sync = None  # oxirgi muvaffaqiyatli server aloqasi (epoch sek)
        self._net_down = False # ulanish xatosi log'i bir marta yozilsin (spam yo'q)
        # API kalit: REST'da header orqali, VLC/rasm URL'larida ?k= orqali
        self._headers = ({"X-API-Key": config.API_KEY}
                         if config.API_KEY else {})
        self._url_key = (f"?k={quote(config.API_KEY)}"
                         if config.API_KEY else "")

    def _cached(self, name, fetch):
        """fetch() natijasini keshlaydi; tarmoq xatosida keshdan qaytaradi.

        Ulanish uzilgani ANIQ bo'lsa (`_net_down` — health doimiy tekshiradi)
        tarmoqni kutib o'tirmaymiz: keshdan DARHOL qaytaramiz (oflayn UI tez
        bo'lsin). Ulanish tiklanganda health `_net_down`ni tozalaydi va keyingi
        chaqiruv yana tarmoqdan oladi."""
        if self._net_down:
            hit = cache.load_json(name)
            if hit is not None:
                self.offline = True
                return hit[0]
        try:
            data = fetch()
            cache.save_json(name, data)
            self.offline = False
            return data
        except requests.RequestException:
            hit = cache.load_json(name)
            if hit is not None:
                data, age = hit
                self.offline = True
                log.info("Oflayn: %s keshdan o'qildi (%d daqiqa eski)",
                         name, age // 60)
                return data
            raise

    def _get(self, path, retries=2, **kwargs):
        """GET + qisqa retry (tarmoq "hiqildoqlari" sahifani yiqitmasin).

        Faqat ulanish/timeout xatolarida qayta urinadi — HTTP 404/500 kabi
        javoblar retry qilinmaydi (raise_for_status keyin tashlaydi).
        MUHIM: requests.Session ishlatilmaydi — bitta ApiClient bir nechta
        worker-QThread'dan chaqiriladi, Session esa thread-safe emas. netpin
        har chaqiruvда yangi (qisqa umrli) Session yaratadi — pin bilan ham
        thread-safe qoladi.
        """
        url = f"{self.base_url}{path}"
        delay = 0.4
        for attempt in range(retries + 1):
            try:
                r = netpin.get(url, timeout=self.timeout,
                               headers=self._headers, **kwargs)
                if r.status_code == 401:
                    # Aniq sabab logga — operator darhol tushunsin
                    log.error(
                        "Server API kalitni rad etdi (401). server.txt'da "
                        "`key=...` qatori bormi / kalit to'g'rimi tekshiring "
                        "(admin oynasi -> Boshqaruv -> Nusxalash).")
                r.raise_for_status()
                # Muvaffaqiyatli aloqa — vaqtni belgilaymiz; uzilgan bo'lsa
                # "tiklandi" deb BIR marta yozamiz (log spam'iga yo'l qo'ymaymiz)
                self.last_sync = time.time()
                if self._net_down:
                    log.info("Server bilan aloqa tiklandi")
                    self._net_down = False
                return r
            except (requests.ConnectionError, requests.Timeout) as e:
                if attempt >= retries:
                    # Faqat BIRINCHI uzilishda warning; keyingilari debug
                    # (server o'chiq turganda log to'lib ketmasin)
                    if not self._net_down:
                        log.warning("Server bilan aloqa uzildi (%s): %s", path, e)
                        self._net_down = True
                    else:
                        log.debug("So'rov muvaffaqiyatsiz (%s): %s", path, e)
                    raise
                time.sleep(delay)
                delay *= 2

    def last_sync_text(self):
        """Oxirgi muvaffaqiyatli server aloqasi 'HH:MM' (yoki '' — noma'lum).
        Sessiyada hali ulanmagan bo'lsa — kontent keshi yoshidan chamalaydi."""
        ts = self.last_sync
        if ts is None:
            hit = cache.load_json("content")
            if hit is not None:
                ts = time.time() - hit[1]
        if ts is None:
            return ""
        return time.strftime("%H:%M", time.localtime(ts))

    # --- Ulanish ---
    def health(self):
        """Server tirikmi? True/False qaytaradi (xato bo'lsa False).

        retries=0 — bu har 5 soniyada chaqiriladi, retry qilinsa
        HealthChecker oqimlari to'planib qoladi."""
        try:
            self._get("/api/health", retries=0)
            return True
        except requests.RequestException:
            return False

    # --- Katalog (4+ bosqichlarda ishlatiladi) ---
    def get_content(self, content_type=None):
        """Kontent ro'yxati. content_type: 'movie'|'book'|... yoki None (barchasi)."""
        params = {"type": content_type} if content_type else None
        name = "content" + (f"_{content_type}" if content_type else "")
        return self._cached(
            name, lambda: self._get("/api/content", params=params).json())

    def get_content_detail(self, content_id):
        """Bitta kontent haqida batafsil."""
        return self._get(f"/api/content/{content_id}").json()

    def cover_url(self, content_id):
        """Muqova rasm manzili (to'g'ridan-to'g'ri yuklash uchun)."""
        return f"{self.base_url}/api/content/{content_id}/cover{self._url_key}"

    def stream_url(self, content_id):
        """Video/audio striming manzili (LibVLC pleyerga beriladi)."""
        return f"{self.base_url}/api/stream/{content_id}{self._url_key}"

    def play_url(self, content_id):
        """Pleyer (LibVLC/Qt) uchun ijro manzili:
          1) lokal keshda tayyor fayl bo'lsa — fayl yo'li (tarmoqsiz);
          2) TLS (https) bo'lsa — LOKAL PROXY URL: LibVLC self-signed
             sertifikatni rad etadi, shuning uchun pleyerga 127.0.0.1 dagi
             oddiy http beriladi (proxy serverdan pinned HTTPS bilan oladi);
          3) aks holda (http) — to'g'ridan-to'g'ri striming."""
        from services import media_cache
        local = media_cache.local_path(content_id)
        if local:
            return local
        from core import config
        if config.is_tls():
            from services import stream_proxy
            url = stream_proxy.play_proxy_url(content_id)
            if url:
                return url
        return self.stream_url(content_id)

    def heartbeat(self, info):
        """Kiosk o'zini serverga tanitadi (admin "Kiosklar" jadvali uchun).
        Server javobi qaytariladi (masalan {"cache": 0/1} — shu qurilmada
        lokal kesh ruxsati)."""
        r = netpin.post(f"{self.base_url}/api/heartbeat", json=info,
                        headers=self._headers, timeout=self.timeout)
        try:
            return r.json()
        except (ValueError, AttributeError):
            return {}

    def get_book_text(self, content_id):
        """Kitob matni (boblar bilan) — o'qilgan kitoblar oflaynda ham ochiladi."""
        return self._cached(
            f"book_{content_id}",
            lambda: self._get(f"/api/book/{content_id}/text").json())

    def get_ads(self):
        """Faol reklama bannerlari (media_type, duration, vaqt oralig'i bilan)."""
        return self._cached("ads", lambda: self._get("/api/ads").json())

    def ad_media_url(self, ad_id):
        """Reklama media manzili (rasm uchun — _Fetcher netpin bilan oladi)."""
        return f"{self.base_url}/api/ads/{ad_id}/media{self._url_key}"

    def ad_media_play_url(self, ad_id):
        """Video reklama pleyeri (Qt Multimedia) uchun:
          1) lokal keshda tayyor fayl bo'lsa — fayl yo'li (oflaynда ham);
          2) TLS bo'lsa — lokal proxy (self-signed sertifikat muammosi);
          3) aks holda — to'g'ridan-to'g'ri URL."""
        from services import media_cache
        local = media_cache.ad_local_path(ad_id)
        if local:
            return local
        from core import config
        if config.is_tls():
            from services import stream_proxy
            url = stream_proxy.ad_proxy_url(ad_id)
            if url:
                return url
        return self.ad_media_url(ad_id)

    def get_sites(self):
        """Saytlar ro'yxati."""
        return self._cached("sites", lambda: self._get("/api/sites").json())

    def get_route(self):
        """Yo'nalish bekatlari va joylashuv."""
        return self._cached("route", lambda: self._get("/api/route").json())

    def get_status(self):
        """Poyezd holati: tezlik, harorat, vagon, joriy bekat."""
        return self._cached("status", lambda: self._get("/api/status").json())

    def get_settings(self):
        """Server sozlamalari (vagon, poyezd, yo'nalish)."""
        return self._cached("settings",
                            lambda: self._get("/api/settings").json())
