"""
screensaver.py — Logotipli to'liq ekran zastavka (splash + screensaver).

Ikki vazifada ishlatiladi:
  1. Dastur ishga tushganda bir necha soniya ko'rinadigan splash;
  2. Foydalanuvchi uzoq vaqt (config.SCREENSAVER_IDLE_MIN) hech narsa
     bosmasa/ko'rmasa chiqadigan zastavka.

Mustaqil to'liq-ekran oyna (frameless + StaysOnTop) — shuning uchun video
pleyer (u ham StaysOnTop) ustida ham ishonchli ko'rinadi va ota-oyna
geometriyasiga bog'liq emas (splash siljib qolmaydi). Ostidagi holatga
TEGMAYDI: yopilganda ilova aynan qolgan joyidan davom etadi.
"""
import os
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QPainter, QColor

IMAGE = os.path.join(os.path.dirname(__file__), "..", "assets", "design",
                     "screensaver.png")


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
        self.hide()

    def show_over(self):
        """Ekranni to'liq qoplab, eng ustki qatlamda ko'rsatadi."""
        self.showFullScreen()
        self.raise_()
        self.activateWindow()

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
