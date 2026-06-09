"""
card.py — Kontent kartochkasi (muqova + nom + janr·davomiylik).
Videolar va Kitoblar ro'yxatlarida ishlatiladi. Bosilganda 'clicked' signal
(kontent dict bilan) yuboriladi.
"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
                             QGraphicsDropShadowEffect, QSizePolicy)
from PyQt6.QtCore import Qt, pyqtSignal, QByteArray, QRectF
from PyQt6.QtGui import QColor, QPixmap, QPainter
from PyQt6.QtSvg import QSvgRenderer
import theme as T
from widgets.cover import CoverLabel

# Kitob kartasidagi belgilar (muqova ustidagi oq pill ichida) — inline SVG.
_BOOK_SVG = ("<svg viewBox='0 0 24 24' fill='none'>"
             "<path d='M12 6.5C12 5 10.5 4 8 4S4 5 4 5v13s1.5-1 4-1 4 1 4 1m0-11.5"
             "V18m0-11.5C12 5 13.5 4 16 4s4 1 4 1v13s-1.5-1-4-1-4 1-4 1'"
             " stroke='currentColor' stroke-width='1.8' stroke-linecap='round'"
             " stroke-linejoin='round'/></svg>")
_HEAD_SVG = ("<svg viewBox='0 0 24 24' fill='none'>"
             "<path d='M4 14v-2a8 8 0 0 1 16 0v2' stroke='currentColor'"
             " stroke-width='1.8' stroke-linecap='round'/>"
             "<rect x='3' y='13.5' width='4.5' height='7' rx='2.2'"
             " stroke='currentColor' stroke-width='1.8'/>"
             "<rect x='16.5' y='13.5' width='4.5' height='7' rx='2.2'"
             " stroke='currentColor' stroke-width='1.8'/></svg>")


def _svg_pixmap(svg, color_hex, size):
    """Inline SVG matnini berilgan rangdagi QPixmap ikonkaga aylantiradi."""
    body = svg.replace("<svg", "<svg xmlns='http://www.w3.org/2000/svg'", 1)
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    QSvgRenderer(QByteArray(body.encode("utf-8"))).render(p, QRectF(0, 0, size, size))
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    p.fillRect(pm.rect(), QColor(color_hex))
    p.end()
    return pm


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


class BookCard(QFrame):
    """Kitob kartochkasi (ContentCard uslubida): oq panel + yumshoq soya,
    tikka (portret) muqova karta kengligini to'ldiradi, nom, muallif va
    o'qish/tinglash belgilari."""
    clicked = pyqtSignal(dict)

    def __init__(self, item, api, theme_name="light", cover_w=None, cover_h=None):
        super().__init__()
        self.item = item
        self.theme_name = theme_name
        # O'lcham ekran miqyosiga (T.s) moslanadi; muqova karta kengligini
        # to'ldiradi. Dizayn (Kitoblar.html): thumb aspect-ratio 252/243 — deyarli
        # kvadrat, object-fit:cover bilan kesiladi.
        cover_w = T.s(220) if cover_w is None else cover_w
        self.setObjectName("bookCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # Karta ustun kengligini to'ldiradi (grid teng ustunlar), vertikal cho'zilmaydi
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        self._m = T.s(20)            # karta ichki padding (dizayn: 20px)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(self._m, self._m, self._m, self._m)
        lay.setSpacing(0)

        # Muqova — karta kengligini to'ldiradi, deyarli kvadrat (252/243), radius 18
        self.cover = CoverLabel(cover_w, radius=T.s(18), aspect=252 / 243)
        self.cover.load(api.cover_url(item["id"]))
        lay.addWidget(self.cover)

        # Sarlavha — bir qatorda, sig'masa "..." (dizayn: nowrap + ellipsis)
        self._full_title = item.get("title", "")
        self.title = QLabel(self._full_title)
        self.title.setObjectName("cardTitle")
        self.title.setWordWrap(False)
        # Matn uzun bo'lsa kartani kengaytirib yubormasin — joriy kenglikka elide qilamiz
        self.title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.author = QLabel(item.get("author") or "")
        self.author.setObjectName("cardSub")
        self.author.setWordWrap(False)
        self.author.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

        lay.addSpacing(T.s(24))     # dizayn: title margin-top 24
        lay.addWidget(self.title)
        lay.addSpacing(T.s(12))     # dizayn: author margin-top 12
        lay.addWidget(self.author)

        # Belgilar — muqova ustida suzuvchi oq pill (yuqori-o'ng): ko'k kitob
        # (o'qish mumkin) va to'q sariq quloqchin (tinglash mumkin).
        self.badge = QFrame(self)
        self.badge.setObjectName("bookBadge")
        bl = QHBoxLayout(self.badge)
        bl.setContentsMargins(T.s(11), T.s(7), T.s(11), T.s(7))
        bl.setSpacing(T.s(9))
        self._badge_icons = []       # (label, svg, theme rang kaliti)
        if can_read(item):
            ic = QLabel(); bl.addWidget(ic)
            self._badge_icons.append((ic, _BOOK_SVG, "accent"))
        if can_listen(item):
            ic = QLabel(); bl.addWidget(ic)
            self._badge_icons.append((ic, _HEAD_SVG, "orange"))
        self.badge.setVisible(bool(self._badge_icons))

        # Yumshoq soya (ContentCard bilan bir xil)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(T.s(40))
        shadow.setOffset(0, T.s(14))
        shadow.setColor(QColor(40, 55, 90, 60))
        self.setGraphicsEffect(shadow)

        self.apply_theme(theme_name)

    def _place_badge(self):
        """Belgili pill'ni muqovaning yuqori-o'ng burchagiga qo'yadi."""
        if not self._badge_icons:
            return
        self.badge.adjustSize()
        inset = T.s(12)
        x = self.width() - self._m - inset - self.badge.width()
        self.badge.move(max(self._m, x), self._m + inset)
        self.badge.raise_()

    def _elide_title(self):
        """Sarlavha karta kengligiga sig'masa oxirini '...' bilan qisqartiradi."""
        w = self.title.width()
        if w > 8:
            fm = self.title.fontMetrics()
            self.title.setText(
                fm.elidedText(self._full_title, Qt.TextElideMode.ElideRight, w))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._place_badge()
        self._elide_title()

    def apply_theme(self, name):
        self.theme_name = name
        c = T.THEMES[name]
        # Dizayn (Kitoblar.html): card radius 26, title 42/700 #1c2230, author 32/500 #8b94a4
        self.setStyleSheet(
            f"#bookCard {{ background: {c['surface']}; border-radius: {T.s(26)}px; }}"
            f"#cardTitle {{ background: transparent; color: {c['text']};"
            f" font-size: {T.FONT['card_title']}px; font-weight: 700; }}"
            f"#cardSub {{ background: transparent; color: {c['text_secondary']};"
            f" font-size: {T.FONT['small']}px; font-weight: 500; }}"
            f"#bookBadge {{ background: rgba(255,255,255,0.94);"
            f" border-radius: {T.s(15)}px; }}"
            f"#bookBadge QLabel {{ background: transparent; }}")
        icon_px = T.s(22)
        for ic, svg, key in self._badge_icons:
            ic.setPixmap(_svg_pixmap(svg, c[key], icon_px))
        self._place_badge()
        self._elide_title()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.item)
        super().mouseReleaseEvent(e)
