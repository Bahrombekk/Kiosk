"""
lockscreen.py — Dastur bloklanganda ko'rinadigan to'liq ekran qulf.

Server sinov muddati (litsenziya) tugaganда yoki admin qo'lda bloklaganда
status'da `blocked=True` keladi. Shunda bu ekran butun interfeysни qoplaydi
va foydalanuvchi hech narsa qila olmaydi. Ma'mur (admin) serverdan blokni
ochsa — 3 soniya ichida o'zi yo'qoladi.

Yuqori-o'ng burchakda SOAT ko'rinadi — ham ekran "o'lik" emas, ham dasturchi
maxfiy chiqish zonasini (aynan o'sha burchak) ko'rib turadi: soat ustiga
10 marta teginib, master PIN bilan chiqish mumkin (bloklangan bo'lsa ham).

Mustaqil top-level oyna (frameless + StaysOnTop) — screensaver/pleyer ustida
ham ishonchli ko'rinadi. Maxfiy chiqish QApplication event-filtrida —
dasturchi qulflanib qolmaydi.
"""
from datetime import datetime

from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt, QTimer

from core import theme as T
from widgets.icons import svg_pixmap


class LockScreen(QWidget):
    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.WindowStaysOnTopHint)
        # To'q fon — ostidagi interfeys umuman ko'rinmasin
        self.setStyleSheet("background: #0B1120;")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # Soat — yuqori-o'ng burchak (maxfiy chiqish zonasi shu yerda). Layoutda
        # emas, qo'lda joylashtiriladi (resizeEvent) — har doim burchakda tursin.
        self.clock = QLabel("", self)
        self.clock.setAlignment(Qt.AlignmentFlag.AlignRight
                                | Qt.AlignmentFlag.AlignVCenter)
        self.clock.setStyleSheet(
            f"color: #E2E8F0; font-size: {T.s(40)}px; font-weight: 700;"
            f" background: transparent;")
        self._clock_timer = QTimer(self)
        self._clock_timer.setInterval(1000)
        self._clock_timer.timeout.connect(self._tick)

        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(T.s(18))

        icon = QLabel()
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setPixmap(svg_pixmap("lock", "#EF4444", T.s(88)))
        icon.setStyleSheet("background: transparent;")

        title = QLabel("Dastur vaqtincha ishlamayapti")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"color: #FFFFFF; font-size: {T.s(40)}px; font-weight: 800;"
            f" background: transparent;")

        sub = QLabel("Iltimos, ma'muriyat bilan bog'laning.")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(
            f"color: #94A3B8; font-size: {T.s(22)}px; background: transparent;")

        lay.addStretch(1)
        lay.addWidget(icon)
        lay.addWidget(title)
        lay.addWidget(sub)
        lay.addStretch(1)
        self.hide()

    def _tick(self):
        self.clock.setText(datetime.now().strftime("%H:%M"))

    def _place_clock(self):
        m = T.s(40)
        w = T.s(240)
        h = T.s(64)            # katta shrift kesilmasin uchun yetarli balandlik
        self.clock.setFixedSize(w, h)
        self.clock.move(self.width() - w - m, m)

    def show_over(self):
        """Ekranni to'liq qoplab, eng ustki qatlamda ko'rsatadi."""
        self._tick()
        self.showFullScreen()
        self._place_clock()
        self.clock.raise_()
        self._clock_timer.start()
        self.raise_()
        self.activateWindow()

    def hideEvent(self, e):
        self._clock_timer.stop()
        super().hideEvent(e)

    def resizeEvent(self, e):
        self._place_clock()
        super().resizeEvent(e)

    # Ostidagi interfeysga teginish o'tib ketmasin (qulf hamma narsani yutadi).
    def mousePressEvent(self, e):
        e.accept()

    def mouseReleaseEvent(self, e):
        e.accept()

    def keyPressEvent(self, e):
        e.accept()
