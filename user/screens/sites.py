"""
sites.py — Saytlar (Websites) bo'limi (TZ 8.12-8.13).

Kiosk internetga ulanmaydi — saytlar QR kod orqali yo'lovchining telefonida
ochiladi. 3 ustunli kartochkalar; bosilganda detal modal: tavsif,
imkoniyatlar ro'yxati va QR kod + 3 qadamli yo'riqnoma.
"""
import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QFrame, QLabel, QScrollArea)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

import theme as T
from widgets.modal import Modal
from widgets.qr import QRWidget
from widgets.navbar import colored_icon, ICON_DIR


class _Loader(QThread):
    done = pyqtSignal(list)
    fail = pyqtSignal()

    def __init__(self, api):
        super().__init__()
        self.api = api

    def run(self):
        try:
            self.done.emit(self.api.get_sites())
        except Exception:
            self.fail.emit()


def _features(item):
    """features matnini ro'yxatga ajratadi (';' yoki yangi qator bo'yicha)."""
    raw = item.get("features") or ""
    parts = [p.strip() for p in raw.replace("\n", ";").split(";")]
    return [p for p in parts if p]


class SiteCard(QFrame):
    clicked = pyqtSignal(dict)

    def __init__(self, item, theme_name="light"):
        super().__init__()
        self.item = item
        self.theme_name = theme_name
        self.setObjectName("siteCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(8)

        top = QHBoxLayout()
        self.icon = QLabel()
        path = os.path.join(ICON_DIR, "globe.svg")
        self.icon.setPixmap(colored_icon(path, T.THEMES[theme_name]["accent"]).pixmap(32, 32))
        self.name = QLabel(item.get("name", ""))
        self.name.setObjectName("siteName")
        top.addWidget(self.icon)
        top.addWidget(self.name, 1)
        lay.addLayout(top)

        self.url = QLabel(item.get("url", ""))
        self.url.setObjectName("siteUrl")
        self.desc = QLabel(item.get("description") or "")
        self.desc.setObjectName("siteDesc")
        self.desc.setWordWrap(True)
        lay.addWidget(self.url)
        lay.addWidget(self.desc)
        lay.addStretch(1)

        arrow = QLabel("→")
        arrow.setObjectName("siteArrow")
        arrow.setAlignment(Qt.AlignmentFlag.AlignRight)
        lay.addWidget(arrow)
        self.apply_theme(theme_name)

    def apply_theme(self, name):
        self.theme_name = name
        c = T.THEMES[name]
        path = os.path.join(ICON_DIR, "globe.svg")
        self.icon.setPixmap(colored_icon(path, c["accent"]).pixmap(32, 32))
        self.setStyleSheet(
            f"#siteCard {{ background: {c['surface']};"
            f" border-radius: {T.RADIUS['card']}px; }}"
            f"#siteCard:hover {{ background: {c['surface2']}; }}"
            f"#siteName {{ color: {c['text']}; font-size: {T.FONT['card_title']}px; font-weight: 600; }}"
            f"#siteUrl {{ color: {c['accent']}; font-size: {T.FONT['body']}px; }}"
            f"#siteDesc {{ color: {c['text_secondary']}; font-size: {T.FONT['small']}px; }}"
            f"#siteArrow {{ color: {c['text_secondary']}; font-size: 22px; }}")

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.item)


class SitesScreen(QWidget):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self.theme_name = "light"
        self.sites = []
        self.cards = []
        self._loader = None
        self._modal = None
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(T.SPACE["page"], 0, T.SPACE["page"], T.SPACE["page"])
        root.setSpacing(T.SPACE["gap"])

        self.status = QLabel("")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.status)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.grid_host = QWidget()
        self.grid = QGridLayout(self.grid_host)
        self.grid.setSpacing(T.SPACE["page"])
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.grid_host)
        root.addWidget(self.scroll, 1)

    def on_show(self):
        if not self.sites:
            self.reload()

    def reload(self):
        self.status.setText("Yuklanmoqda...")
        self._loader = _Loader(self.api)
        self._loader.done.connect(self._on_loaded)
        self._loader.fail.connect(lambda: self.status.setText("Yuklab bo'lmadi"))
        self._loader.start()

    def _on_loaded(self, sites):
        self.sites = sites
        self._render()

    def _render(self):
        while self.grid.count():
            w = self.grid.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.cards = []
        if not self.sites:
            self.status.setText("Saytlar yo'q")
            return
        self.status.setText("")
        cols = 3
        for i, s in enumerate(self.sites):
            card = SiteCard(s, self.theme_name)
            card.clicked.connect(self._open_detail)
            self.cards.append(card)
            self.grid.addWidget(card, i // cols, i % cols)

    def _open_detail(self, item):
        self._modal = _SiteDetail(self.window(), item)
        self._modal.show_over(self.theme_name)

    def apply_theme(self, name):
        self.theme_name = name
        c = T.THEMES[name]
        self.status.setStyleSheet(
            f"color: {c['text_secondary']}; font-size: {T.FONT['h2']}px;")
        for card in self.cards:
            card.apply_theme(name)


class _SiteDetail(Modal):
    """Sayt detali va QR kod (TZ 8.13)."""

    def __init__(self, parent, item):
        super().__init__(parent, width=820, height=480)
        self.item = item

        row = QHBoxLayout()
        row.setSpacing(28)

        # Chap: nom, URL, tavsif, imkoniyatlar
        left = QVBoxLayout()
        left.setSpacing(10)
        name = QLabel(item.get("name", ""))
        name.setStyleSheet(f"font-size:{T.FONT['title']}px; font-weight:700;")
        url = QLabel(item.get("url", ""))
        url.setObjectName("sdUrl")
        desc = QLabel(item.get("description") or "")
        desc.setObjectName("sdDesc")
        desc.setWordWrap(True)
        left.addWidget(name)
        left.addWidget(url)
        left.addWidget(desc)

        feats = _features(item)
        if feats:
            cap = QLabel("Imkoniyatlar:")
            cap.setObjectName("sdCap")
            left.addWidget(cap)
            for f in feats:
                left.addWidget(QLabel(f"•  {f}"))
        left.addStretch(1)
        row.addLayout(left, 1)

        # O'ng: QR + 3 qadamli yo'riqnoma
        right = QVBoxLayout()
        right.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.qr = QRWidget(220)
        self.qr.set_url(item.get("url", ""))
        right.addWidget(self.qr, alignment=Qt.AlignmentFlag.AlignHCenter)
        guide = QLabel(
            "Telefoningizda oching:\n"
            "1) Telefon kamerasini QR kodga yo'llang\n"
            "2) Chiqqan havolaga bosing — brauzerda ochiladi\n"
            "3) Xizmatdan uyda ham foydalanishingiz mumkin")
        guide.setObjectName("sdGuide")
        guide.setWordWrap(True)
        right.addWidget(guide)
        row.addLayout(right)

        self.content.addLayout(row)

    def show_over(self, name="light"):
        super().show_over(name)
        c = T.THEMES[name]
        self.panel.setStyleSheet(self.panel.styleSheet() + (
            f"QLabel {{ color: {c['text']}; font-size: {T.FONT['body']}px; }}"
            f"#sdUrl {{ color: {c['accent']}; font-size: {T.FONT['card_title']}px; }}"
            f"#sdDesc {{ color: {c['text_secondary']}; }}"
            f"#sdCap {{ color: {c['text']}; font-weight: 600; }}"
            f"#sdGuide {{ color: {c['text_secondary']}; font-size: {T.FONT['small']}px; }}"))
