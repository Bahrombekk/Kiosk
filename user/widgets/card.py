"""
card.py — Kontent kartochkasi (muqova + nom + janr·davomiylik).
Videolar va Kitoblar ro'yxatlarida ishlatiladi. Bosilganda 'clicked' signal
(kontent dict bilan) yuboriladi.
"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QFrame,
                             QGraphicsDropShadowEffect, QSizePolicy)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
import theme as T
from widgets.cover import CoverLabel


def fmt_duration(seconds):
    """Soniyani '1 soat 50 daqiqa' ko'rinishiga keltiradi."""
    if not seconds:
        return ""
    h, m = seconds // 3600, (seconds % 3600) // 60
    if h and m:
        return f"{h} soat {m} daqiqa"
    if h:
        return f"{h} soat"
    return f"{m} daqiqa"


class ContentCard(QFrame):
    """Video kartochkasi (Videolar.html dizayni): oq panel + yumshoq soya,
    16:9 landshaft thumbnail, sarlavha va 'janr • davomiylik'."""
    clicked = pyqtSignal(dict)

    def __init__(self, item, api, theme_name="light", cover_w=None, cover_h=None):
        super().__init__()
        self.item = item
        self.api = api
        self.theme_name = theme_name
        # O'lcham ekran miqyosiga (T.s) moslanadi — kichik/katta monitor.
        cover_w = T.s(360) if cover_w is None else cover_w
        cover_h = T.s(203) if cover_h is None else cover_h
        self.setObjectName("videoCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # Karta ustun kengligini to'ldiradi (grid teng ustunlar), vertikal cho'zilmaydi
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(T.s(18), T.s(18), T.s(18), T.s(20))
        lay.setSpacing(0)

        # Thumbnail — 16:9 moslashuvchan (karta kengligini to'ldiradi), yumaloq burchak
        self.cover = CoverLabel(cover_w, cover_h, radius=T.s(16), aspect=16 / 9)
        self.cover.load(api.cover_url(item["id"]))
        lay.addWidget(self.cover)

        self.title = QLabel(item.get("title", ""))
        self.title.setObjectName("cardTitle")
        self.title.setWordWrap(True)

        sub_parts = [p for p in (item.get("genre"),
                                 fmt_duration(item.get("duration"))) if p]
        self.sub = QLabel(" • ".join(sub_parts))   # dizayndagi '•' ajratuvchi
        self.sub.setObjectName("cardSub")
        self.sub.setWordWrap(True)

        lay.addSpacing(T.s(20))
        lay.addWidget(self.title)
        lay.addSpacing(T.s(8))
        lay.addWidget(self.sub)

        # Yumshoq soya (dizayn: 0 18px 40px -26px rgba(40,55,90,.22))
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(T.s(40))
        shadow.setOffset(0, T.s(14))
        shadow.setColor(QColor(40, 55, 90, 60))
        self.setGraphicsEffect(shadow)

        self.apply_theme(theme_name)

    def apply_theme(self, name):
        self.theme_name = name
        c = T.THEMES[name]
        self.setStyleSheet(
            f"#videoCard {{ background: {c['surface']}; border-radius: {T.s(24)}px; }}"
            f"#cardTitle {{ background: transparent; color: {c['text']};"
            f" font-size: {T.FONT['card_title']}px; font-weight: 700; }}"
            f"#cardSub {{ background: transparent; color: {c['text_secondary']};"
            f" font-size: {T.FONT['small']}px; }}")

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.item)
        super().mouseReleaseEvent(e)


def can_read(item):
    """Kitobni matn ko'rinishida o'qish mumkinmi?"""
    return bool(item.get("text_path"))


def can_listen(item):
    """Kitobni tinglash (audio) mumkinmi?"""
    return item.get("type") == "audiobook" or bool(
        item.get("file_path") and item.get("type") in ("audiobook",))


class BookCard(QWidget):
    """Kitob kartochkasi: muqova, nom, muallif + o'qish/tinglash belgilari."""
    clicked = pyqtSignal(dict)

    def __init__(self, item, api, theme_name="light", cover_w=None, cover_h=None):
        super().__init__()
        self.item = item
        self.theme_name = theme_name
        cover_w = T.s(190) if cover_w is None else cover_w
        cover_h = T.s(260) if cover_h is None else cover_h
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(T.s(6))

        self.cover = CoverLabel(cover_w, cover_h)
        self.cover.load(api.cover_url(item["id"]))
        lay.addWidget(self.cover, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.title = QLabel(item.get("title", ""))
        self.title.setObjectName("cardTitle")
        self.title.setWordWrap(True)
        self.author = QLabel(item.get("author") or "")
        self.author.setObjectName("cardSub")

        badges = []
        if can_read(item):
            badges.append("📖 O'qish")
        if can_listen(item):
            badges.append("🎧 Tinglash")
        self.badges = QLabel("   ".join(badges))
        self.badges.setObjectName("cardBadges")

        lay.addWidget(self.title)
        lay.addWidget(self.author)
        lay.addWidget(self.badges)
        self.apply_theme(theme_name)

    def apply_theme(self, name):
        self.theme_name = name
        c = T.THEMES[name]
        self.title.setStyleSheet(
            f"#cardTitle {{ color: {c['text']}; font-size: {T.FONT['card_title']}px;"
            f" font-weight: 600; }}")
        self.author.setStyleSheet(
            f"#cardSub {{ color: {c['text_secondary']}; font-size: {T.FONT['small']}px; }}")
        self.badges.setStyleSheet(
            f"#cardBadges {{ color: {c['accent']}; font-size: {T.FONT['small']}px; }}")

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.item)
        super().mouseReleaseEvent(e)
