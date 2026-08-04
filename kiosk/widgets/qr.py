"""
qr.py — URL'dan QR kod chizadigan widget (TZ 8.13).

qrcode kutubxonasidan modul matritsasini olib, QPainter bilan to'g'ridan-to'g'ri
chizadi — Pillow yoki rasm fayli kerak emas (to'liq offline).
"""
import qrcode
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QColor


class QRWidget(QWidget):
    def __init__(self, size=220):
        super().__init__()
        self._matrix = []
        self.setFixedSize(size, size)

    def set_url(self, url):
        qr = qrcode.QRCode(border=2)
        qr.add_data(url or "")
        qr.make(fit=True)
        self._matrix = qr.get_matrix()
        self.update()

    def paintEvent(self, e):
        if not self._matrix:
            return
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#FFFFFF"))   # QR doim oq-qora (TZ)
        n = len(self._matrix)
        cell = min(self.width(), self.height()) / n
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#000000"))
        for r, row in enumerate(self._matrix):
            for c, on in enumerate(row):
                if on:
                    p.drawRect(int(c * cell), int(r * cell),
                               int(cell + 1), int(cell + 1))
        p.end()
