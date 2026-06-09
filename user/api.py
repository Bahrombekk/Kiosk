"""
api.py — Server bilan HTTP aloqa (REST API mijozi).

Foydalanuvchi ilovasi server bilan ikki kanal orqali ishlaydi (TZ 11):
  1) REST API — katalog va kontent (shu fayl).
  2) WebSocket — real vaqt buyruqlar (keyingi bosqichda: ws_client.py).

Hozircha (3-bosqich poydevori) faqat ulanishni tekshirish (health) kerak.
Qolgan metodlar tayyor turibdi — Videolar/Kitoblar bosqichlarida ishlatiladi.
"""
import requests
import config


class ApiClient:
    """Server REST API'siga so'rovlar yuboradigan oddiy mijoz."""

    def __init__(self, base_url=None, timeout=None):
        self.base_url = (base_url or config.SERVER_URL).rstrip("/")
        self.timeout = timeout or config.REQUEST_TIMEOUT

    def _get(self, path, **kwargs):
        url = f"{self.base_url}{path}"
        r = requests.get(url, timeout=self.timeout, **kwargs)
        r.raise_for_status()
        return r

    # --- Ulanish ---
    def health(self):
        """Server tirikmi? True/False qaytaradi (xato bo'lsa False)."""
        try:
            self._get("/api/health")
            return True
        except requests.RequestException:
            return False

    # --- Katalog (4+ bosqichlarda ishlatiladi) ---
    def get_content(self, content_type=None):
        """Kontent ro'yxati. content_type: 'movie'|'book'|... yoki None (barchasi)."""
        params = {"type": content_type} if content_type else None
        return self._get("/api/content", params=params).json()

    def get_content_detail(self, content_id):
        """Bitta kontent haqida batafsil."""
        return self._get(f"/api/content/{content_id}").json()

    def cover_url(self, content_id):
        """Muqova rasm manzili (to'g'ridan-to'g'ri yuklash uchun)."""
        return f"{self.base_url}/api/content/{content_id}/cover"

    def stream_url(self, content_id):
        """Video/audio striming manzili (LibVLC pleyerga beriladi)."""
        return f"{self.base_url}/api/stream/{content_id}"

    def get_book_text(self, content_id):
        """Kitob matni (boblar bilan)."""
        return self._get(f"/api/book/{content_id}/text").json()

    def get_ads(self):
        """Faol reklama bannerlari."""
        return self._get("/api/ads").json()

    def get_sites(self):
        """Saytlar ro'yxati."""
        return self._get("/api/sites").json()

    def get_route(self):
        """Yo'nalish bekatlari va joylashuv."""
        return self._get("/api/route").json()

    def get_status(self):
        """Poyezd holati: tezlik, harorat, vagon, joriy bekat."""
        return self._get("/api/status").json()

    def get_settings(self):
        """Server sozlamalari (vagon, poyezd, yo'nalish)."""
        return self._get("/api/settings").json()
