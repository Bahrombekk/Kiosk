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
import cache
import config

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
        # API kalit: REST'da header orqali, VLC/rasm URL'larida ?k= orqali
        self._headers = ({"X-API-Key": config.API_KEY}
                         if config.API_KEY else {})
        self._url_key = (f"?k={quote(config.API_KEY)}"
                         if config.API_KEY else "")

    def _cached(self, name, fetch):
        """fetch() natijasini keshlaydi; tarmoq xatosida keshdan qaytaradi."""
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
        worker-QThread'dan chaqiriladi, Session esa thread-safe emas.
        """
        url = f"{self.base_url}{path}"
        delay = 0.4
        for attempt in range(retries + 1):
            try:
                r = requests.get(url, timeout=self.timeout,
                                 headers=self._headers, **kwargs)
                r.raise_for_status()
                return r
            except (requests.ConnectionError, requests.Timeout) as e:
                if attempt >= retries:
                    log.warning("So'rov muvaffaqiyatsiz (%s): %s", path, e)
                    raise
                time.sleep(delay)
                delay *= 2

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

    def get_book_text(self, content_id):
        """Kitob matni (boblar bilan) — o'qilgan kitoblar oflaynda ham ochiladi."""
        return self._cached(
            f"book_{content_id}",
            lambda: self._get(f"/api/book/{content_id}/text").json())

    def get_ads(self):
        """Faol reklama bannerlari."""
        return self._cached("ads", lambda: self._get("/api/ads").json())

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
