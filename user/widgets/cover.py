"""
cover.py — Muqova rasmini serverdan yuklab ko'rsatadigan QLabel.

Server muqovani fayl (jpg/png) yoki dinamik SVG sifatida qaytaradi.
Yuklash tarmoq orqali bo'lgani uchun alohida oqimda (UI qotmaydi);
rasm baytlari kelgach, asosiy oqimda QPixmap'ga aylantiriladi.
"""
import requests
from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QByteArray, QRectF, QSize
from PyQt6.QtGui import QPixmap, QPainter, QColor
from PyQt6.QtSvg import QSvgRenderer
import theme as T
from threads import track


class _Fetcher(QThread):
    done = pyqtSignal(bytes, str)   # (data, content_type)
    fail = pyqtSignal()

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            r = requests.get(self.url, timeout=8)
            r.raise_for_status()
            self.done.emit(r.content, r.headers.get("content-type", ""))
        except requests.RequestException:
            self.fail.emit()


class CoverLabel(QLabel):
    """Belgilangan o'lchamdagi muqova; manzil berilsa serverdan yuklaydi."""

    def __init__(self, width=200, height=280, radius=None):
        super().__init__()
        self._w, self._h = width, height
        self._radius = T.RADIUS["card"] if radius is None else radius
        self.setFixedSize(width, height)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._fetcher = None
        self._show_placeholder("...")

    def sizeHint(self):
        return QSize(self._w, self._h)

    def load(self, url):
        # Eski fetcher hali ishlayotgan bo'lsa, uni majburan to'xtatmaymiz
        # (terminate xavfli) — track() uni tugagunicha tirik saqlaydi; oxirgi
        # boshlangan so'rov natijasi ko'rsatiladi.
        self._fetcher = track(_Fetcher(url))
        self._fetcher.done.connect(self._on_data)
        self._fetcher.fail.connect(lambda: self._show_placeholder("?"))
        self._fetcher.start()

    def _on_data(self, data, ctype):
        pm = QPixmap(self._w, self._h)
        pm.fill(Qt.GlobalColor.transparent)
        if "svg" in ctype or data[:5] == b"<svg " or data[:6] == b"<?xml ":
            painter = QPainter(pm)
            QSvgRenderer(QByteArray(data)).render(painter, QRectF(0, 0, self._w, self._h))
            painter.end()
        else:
            raw = QPixmap()
            raw.loadFromData(data)
            if raw.isNull():
                self._show_placeholder("?")
                return
            pm = raw.scaled(self._w, self._h,
                            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                            Qt.TransformationMode.SmoothTransformation)
        self.setPixmap(self._rounded(pm))

    def _rounded(self, pm):
        """Burchaklarni yumaloqlaydi."""
        out = QPixmap(self._w, self._h)
        out.fill(Qt.GlobalColor.transparent)
        p = QPainter(out)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path_pm = pm
        from PyQt6.QtGui import QPainterPath
        path = QPainterPath()
        path.addRoundedRect(0, 0, self._w, self._h, self._radius, self._radius)
        p.setClipPath(path)
        p.drawPixmap(0, 0, path_pm)
        p.end()
        return out

    def _show_placeholder(self, text):
        pm = QPixmap(self._w, self._h)
        pm.fill(QColor("#475569"))
        p = QPainter(pm)
        p.setPen(QColor("#FFFFFF"))
        p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, text)
        p.end()
        self.setPixmap(self._rounded(pm))
