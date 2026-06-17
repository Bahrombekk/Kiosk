"""
health.py — Server bilan aloqani fonda tekshiruvchi oqimlar (main.py dan
ajratilgan). UI oqimini bloklamaslik uchun QThread ishlatiladi.
"""
import platform as _platform
import shutil
import socket

from PyQt6.QtCore import QThread, pyqtSignal

from core import config


class HealthChecker(QThread):
    """Serverga ulanishni alohida oqimda tekshiradi (UI qotib qolmasligi uchun).
    Server tirik bo'lsa heartbeat ham yuboriladi — admin "Kiosklar" jadvali
    shu orqali to'ladi (kiosk raqami/xonasi server.txt'dan)."""
    result = pyqtSignal(bool)

    def __init__(self, api):
        super().__init__()
        self.api = api

    def run(self):
        ok = self.api.health()
        if ok:
            try:
                from services import media_cache
                du = shutil.disk_usage(config.APP_DIR)
                resp = self.api.heartbeat({
                    "device_id": socket.gethostname(),
                    "kiosk_no": config.KIOSK_NO,
                    "room": config.ROOM_NO,
                    "platform": f"{_platform.system()} "
                                f"{_platform.release()}".strip(),
                    "cached": media_cache.count(),
                    "cached_ids": media_cache.cached_ids(),
                    "caching": media_cache.caching_status(),
                    "disk_total": du.total,
                    "disk_free": du.free,
                })
                # Server shu qurilma uchun lokal keshni o'chirib qo'ygan bo'lsa
                # (xotirasiz kiosk) — yuklashni to'xtatamiz
                if isinstance(resp, dict) and "cache" in resp:
                    media_cache.set_device_allowed(bool(resp.get("cache")))
            except Exception:                       # noqa: BLE001
                pass   # heartbeat yetmasa ham health natijasi muhimroq
        self.result.emit(ok)


class _SettingsPrefetch(QThread):
    """Sozlamalarni oldindan yuklab keshlaydi (chiqish PIN xeshi yangilansin)."""

    def __init__(self, api):
        super().__init__()
        self.api = api

    def run(self):
        try:
            self.api.get_settings()   # _cached() o'zi diskka yozadi
        except Exception:
            pass  # tarmoq xatosi — keyingi ulanishda yana uriniladi
