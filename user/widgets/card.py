"""
card.py — Kontent kartochkasi (muqova + nom + janr·davomiylik).
Videolar va Kitoblar ro'yxatlarida ishlatiladi. Bosilganda 'clicked' signal
(kontent dict bilan) yuboriladi.
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt, pyqtSignal
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


class ContentCard(QWidget):
    clicked = pyqtSignal(dict)

    def __init__(self, item, api, theme_name="light", cover_w=200, cover_h=280):
        super().__init__()
        self.item = item
        self.api = api
        self.theme_name = theme_name
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self.cover = CoverLabel(cover_w, cover_h)
        self.cover.load(api.cover_url(item["id"]))
        lay.addWidget(self.cover, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.title = QLabel(item.get("title", ""))
        self.title.setObjectName("cardTitle")
        self.title.setWordWrap(True)

        sub_parts = [p for p in (item.get("genre"),
                                 fmt_duration(item.get("duration"))) if p]
        self.sub = QLabel(" · ".join(sub_parts))
        self.sub.setObjectName("cardSub")
        self.sub.setWordWrap(True)

        lay.addWidget(self.title)
        lay.addWidget(self.sub)
        self.apply_theme(theme_name)

    def apply_theme(self, name):
        self.theme_name = name
        c = T.THEMES[name]
        self.title.setStyleSheet(
            f"#cardTitle {{ color: {c['text']}; font-size: {T.FONT['card_title']}px;"
            f" font-weight: 600; }}")
        self.sub.setStyleSheet(
            f"#cardSub {{ color: {c['text_secondary']}; font-size: {T.FONT['small']}px; }}")

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

    def __init__(self, item, api, theme_name="light", cover_w=190, cover_h=260):
        super().__init__()
        self.item = item
        self.theme_name = theme_name
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

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
