"""ui/toggle.py — iOS uslubidagi yoqish/o'chirish tugmasi (switch).

QCheckBox'ning o'rnini bosadi: isChecked()/setChecked()/toggled signali bir
xil ishlaydi, faqat ko'rinishi kvadrat indikator emas, sirpanuvchi switch.
"""
from PyQt6.QtCore import Qt, QRectF, QSize
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QCheckBox

from ui.styles import C_ACCENT


class ToggleSwitch(QCheckBox):
    """Matnsiz switch — yorliq va holat yozuvi yonida alohida turadi."""

    _W, _H, _PAD = 48, 28, 3

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(self._W, self._H)

    def sizeHint(self):
        return QSize(self._W, self._H)

    def hitButton(self, pos):
        return self.rect().contains(pos)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        on = self.isChecked()
        if not self.isEnabled():
            track = QColor("#E2E8F0")
        elif on:
            track = QColor(C_ACCENT)
        else:
            track = QColor("#CBD5E1")
        r = self._H / 2
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(QRectF(0, 0, self._W, self._H), r, r)
        d = self._H - 2 * self._PAD
        x = self._W - d - self._PAD if on else self._PAD
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(QRectF(x, self._PAD, d, d))
        p.end()
