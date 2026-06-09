"""
base.py — Barcha bo'lim sahifalari uchun umumiy asos.

3-bosqich poydevorida har bo'lim hozircha "vaqtinchalik" (placeholder) ko'rinishda.
Keyingi bosqichlarda har biri o'z faylida (home.py, videos.py...) haqiqiy
ekranga to'ldiriladi, lekin shu umumiy interfeys (api, apply_theme, on_show)
saqlanib qoladi — shuning uchun main.py o'zgartirilmaydi.
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
import theme as T


class BaseScreen(QWidget):
    """Har bir bo'lim sahifasi shu klassdan meros oladi."""

    def __init__(self, api, title="", subtitle=""):
        super().__init__()
        self.api = api            # ApiClient — serverdan ma'lumot olish uchun
        self.theme_name = "light"
        self._title = title
        self._subtitle = subtitle
        self._build_placeholder()

    def _build_placeholder(self):
        """Vaqtinchalik markazlashtirilgan matn (keyin haqiqiy ekran bilan almashtiriladi)."""
        lay = QVBoxLayout(self)
        lay.setContentsMargins(T.SPACE["page"], 0, T.SPACE["page"], T.SPACE["page"])
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(8)

        self._h1 = QLabel(self._title)
        self._h1.setObjectName("phTitle")
        self._h1.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._p = QLabel(self._subtitle)
        self._p.setObjectName("phText")
        self._p.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lay.addWidget(self._h1)
        lay.addWidget(self._p)

    def apply_theme(self, name):
        """Mavzu o'zgarganda chaqiriladi. Sahifalar o'zining ranglarini yangilaydi."""
        self.theme_name = name
        c = T.THEMES[name]
        self._h1.setStyleSheet(
            f"#phTitle {{ color: {c['text']}; font-size: {T.FONT['title']}px;"
            f" font-weight: 700; }}")
        self._p.setStyleSheet(
            f"#phText {{ color: {c['text_secondary']}; font-size: {T.FONT['h2']}px; }}")

    def on_show(self):
        """Bu sahifaga o'tilganda chaqiriladi (kerakli ma'lumotni shu yerda yuklash mumkin)."""
        pass
