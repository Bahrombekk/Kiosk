"""
screensaver.py — Logotipli to'liq ekran zastavka (splash + attract loop).

Ikki vazifada ishlatiladi:
  1. Dastur ishga tushganda bir necha soniya ko'rinadigan splash;
  2. Foydalanuvchi uzoq vaqt (config.SCREENSAVER_IDLE_MIN) hech narsa
     bosmasa/ko'rmasa chiqadigan zastavka.

Zastavka PASSIV emas — "attract loop": soat va aylanib turuvchi "Bilasizmi?"
faktlari (admin Sozlamalar -> "Zastavka faktlari"dan boshqariladi, oflayn
keshda ham bor). O'tib ketayotgan odamni to'xtatish — kioskning asosiy
marketing nuqtasi.

Mustaqil to'liq-ekran oyna (frameless + StaysOnTop) — shuning uchun video
pleyer (u ham StaysOnTop) ustida ham ishonchli ko'rinadi va ota-oyna
geometriyasiga bog'liq emas (splash siljib qolmaydi). Ostidagi holatga
TEGMAYDI: yopilganda ilova aynan qolgan joyidan davom etadi.
"""
import os
from datetime import datetime

from PyQt6.QtWidgets import QWidget, QLabel
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QPainter, QColor

from core import cache
from core import theme as T

IMAGE = os.path.join(os.path.dirname(__file__), "..", "assets", "design",
                     "screensaver.png")

ROTATE_MS = 6000   # faktlar almashinish oralig'i


class ScreenSaver(QWidget):
    def __init__(self, parent=None):
        # parent=None — mustaqil top-level oyna (ota geometriyasiga bog'lanmaymiz).
        # Main (kiosk) oyna kabi: frameless + StaysOnTop. `Tool` bayrog'i va qo'lda
        # setGeometry ISHLATILMAYDI — ular Windows'da fullscreen'ni siljitib
        # qo'yardi; showFullScreen() o'zi to'g'ri qoplaydi.
        super().__init__(None)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.WindowStaysOnTopHint)
        self._pm = QPixmap(IMAGE)
        self._facts = []
        self._fact_i = 0

        # Soat (yuqori o'ng burchak) — zastavka "o'lik rasm" bo'lib ko'rinmasin
        self.clock = QLabel("", self)
        self.clock.setStyleSheet(
            f"color: #1C2230; font-size: {T.s(56)}px; font-weight: 700;"
            f" background: transparent;")

        # "Bilasizmi?" fakti — pastda, yarim shaffof to'q pill ustida
        self.fact = QLabel("", self)
        self.fact.setWordWrap(True)
        self.fact.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.fact.setStyleSheet(
            f"color: #FFFFFF; background: rgba(15,20,30,0.62);"
            f" border-radius: {T.s(20)}px; font-size: {T.s(26)}px;"
            f" font-weight: 500; padding: {T.s(18)}px {T.s(30)}px;")
        self.fact.hide()

        self._clock_timer = QTimer(self)
        self._clock_timer.setInterval(1000)
        self._clock_timer.timeout.connect(self._tick_clock)
        self._rotate_timer = QTimer(self)
        self._rotate_timer.setInterval(ROTATE_MS)
        self._rotate_timer.timeout.connect(self._rotate)

        self.hide()

    # ---- Ko'rsatish / yashirish ----
    def show_over(self):
        """Ekranni to'liq qoplab, eng ustki qatlamda ko'rsatadi."""
        self._load_facts()
        self._fact_i = 0
        self._apply_texts()
        self.showFullScreen()
        self.raise_()
        self.activateWindow()

    def showEvent(self, e):
        self._tick_clock()
        self._clock_timer.start()
        self._rotate_timer.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self._clock_timer.stop()
        self._rotate_timer.stop()
        super().hideEvent(e)

    # ---- Attract loop tarkibi ----
    def _load_facts(self):
        """Server sozlamasidagi faktlar (har qatorda bittadan). Oflayn keshda
        ham bor (settings.json); sozlanmagan bo'lsa fakt ko'rsatilmaydi."""
        facts = []
        hit = cache.load_json("settings")
        if hit:
            raw = (hit[0] or {}).get("saver_facts") or ""
            facts = [ln.strip() for ln in str(raw).splitlines() if ln.strip()]
        self._facts = facts

    def _rotate(self):
        if self._facts:
            self._fact_i = (self._fact_i + 1) % len(self._facts)
        self._apply_texts()

    def _apply_texts(self):
        if self._facts:
            self.fact.setText(self._facts[self._fact_i])
            self.fact.show()
        else:
            self.fact.hide()
        self._place()

    def _tick_clock(self):
        self.clock.setText(datetime.now().strftime("%H:%M"))
        self.clock.adjustSize()
        self.clock.move(self.width() - self.clock.width() - T.s(48), T.s(36))

    # ---- Joylashtirish ----
    def _place(self):
        w, h = self.width(), self.height()
        if w < 2:
            return
        if self.fact.isVisible():
            fw = min(int(w * 0.7), T.s(1100))
            self.fact.setFixedWidth(fw)
            self.fact.adjustSize()
            self.fact.move((w - fw) // 2,
                           h - self.fact.height() - T.s(70))

    def resizeEvent(self, e):
        self._place()
        self._tick_clock()
        super().resizeEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        # Rasm chetidagi satin-oq rangga mos fon (monitor nisbati boshqacha
        # bo'lsa, kesilmasin deb fit qilamiz — chetlari shu rang bilan to'ladi)
        p.fillRect(self.rect(), QColor("#F4F4F6"))
        if self._pm.isNull():
            return
        scaled = self._pm.scaled(
            self.size(), Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation)
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        p.drawPixmap(x, y, scaled)
