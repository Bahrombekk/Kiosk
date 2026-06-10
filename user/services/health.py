"""
health.py — Server bilan aloqani fonda tekshiruvchi oqimlar (main.py dan
ajratilgan). UI oqimini bloklamaslik uchun QThread ishlatiladi.
"""
from PyQt6.QtCore import QThread, pyqtSignal


class HealthChecker(QThread):
    """Serverga ulanishni alohida oqimda tekshiradi (UI qotib qolmasligi uchun)."""
    result = pyqtSignal(bool)

    def __init__(self, api):
        super().__init__()
        self.api = api

    def run(self):
        self.result.emit(self.api.health())


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
