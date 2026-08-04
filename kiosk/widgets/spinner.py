"""
spinner.py — Yuklanish indikatori (aylanuvchi yoy) + StatusLabel.

"Yuklanmoqda..." oddiy matn o'rniga harakatdagi spinner — foydalanuvchi ilova
qotib qolmaganini ko'radi. QSS'da animatsiya yo'q, shuning uchun
QVariantAnimation + paintEvent ishlatiladi.

Spinner faqat ko'rinib turganda aylanadi (hide bo'lsa animatsiya to'xtaydi) —
kioskda 5 ta bekor spinner CPU yemasin.
"""
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt, QVariantAnimation, QRectF
from PyQt6.QtGui import QPainter, QPen, QColor

from core import theme as T


class Spinner(QWidget):
    """Aylanuvchi yoy. color berilsa o'sha rang (masalan pleyerda oq),
    bo'lmasa joriy mavzu accent rangi."""

    def __init__(self, size=None, line=None, theme="light", color=None):
        super().__init__()
        self._size = size or T.s(36)
        self._line = line or T.s(4)
        self._theme = theme
        self._color = color          # None = mavzu accenti
        self._angle = 0
        self.setFixedSize(self._size, self._size)

        self._anim = QVariantAnimation(self)
        self._anim.setStartValue(0)
        self._anim.setEndValue(360)
        self._anim.setDuration(900)
        self._anim.setLoopCount(-1)
        self._anim.valueChanged.connect(self._on_tick)

    def _on_tick(self, v):
        self._angle = int(v)
        self.update()

    def start(self):
        self.show()
        if self._anim.state() != QVariantAnimation.State.Running:
            self._anim.start()

    def stop(self):
        self._anim.stop()
        self.hide()

    # Ko'rinmas spinner aylanmasin (CPU tejash)
    def hideEvent(self, e):
        self._anim.pause() if self._anim.state() == \
            QVariantAnimation.State.Running else None
        super().hideEvent(e)

    def showEvent(self, e):
        if self._anim.state() == QVariantAnimation.State.Paused:
            self._anim.resume()
        super().showEvent(e)

    def apply_theme(self, name):
        self._theme = name
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(self._color or T.THEMES[self._theme]["accent"])
        pen = QPen(color, self._line)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        m = self._line
        rect = QRectF(m, m, self._size - 2 * m, self._size - 2 * m)
        # Qt'da burchaklar 1/16 gradus birligida; yoy uzunligi ~100°
        p.drawArc(rect, -self._angle * 16, 100 * 16)
        p.end()


class StatusLabel(QWidget):
    """Spinner + matn (yuklanish) yoki faqat matn (xato/bo'sh).

    Eski oddiy `self.status` QLabel o'rnini bosadi:
        self.status.loading(tr("common.loading"))
        self.status.text(tr("common.load_failed"))
        self.status.clear()
    """

    def __init__(self, theme="light"):
        super().__init__()
        self._theme = theme
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, T.s(8), 0, T.s(8))
        lay.setSpacing(T.s(14))
        lay.addStretch(1)
        self.spinner = Spinner(size=T.s(30), line=T.s(3), theme=theme)
        self.spinner.hide()
        self.label = QLabel("")
        lay.addWidget(self.spinner, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(self.label, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addStretch(1)
        self.hide()
        self.apply_theme(theme)

    def loading(self, text):
        self.label.setText(text)
        self.spinner.start()
        self.show()

    def text(self, text):
        self.spinner.stop()
        self.label.setText(text)
        self.show()

    def clear(self):
        self.spinner.stop()
        self.label.setText("")
        self.hide()

    def apply_theme(self, name):
        self._theme = name
        c = T.THEMES[name]
        self.label.setStyleSheet(
            f"color: {c['text_secondary']}; font-size: {T.FONT['h2']}px;"
            f" background: transparent;")
        self.spinner.apply_theme(name)
