"""ui/cards.py — Kontent kartochkasi va muqova pixmap yordamchisi."""
import os

from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
from PyQt6.QtCore import Qt, QSize, QRectF
from PyQt6.QtGui import QPixmap, QColor, QPainter, QPainterPath

import config
from icons import svg_icon, svg_pixmap
from ui.styles import TYPE_LABELS, TYPE_COLORS, C_MUTED, C_BAD

# ----------------------------------------------------------------------------
#  Kontent kartochkasi — user ilovadagi videolar ko'rinishi uslubida
# ----------------------------------------------------------------------------
CARD_W = 252                      # kartochka kengligi
COVER_W = CARD_W - 24             # muqova (karta ichki paddingsiz)
COVER_H = int(COVER_W * 9 / 16)   # 16:9 thumbnail


def _cover_pixmap(item, w, h, radius=12):
    """Muqovani markazdan kesib, yumaloq burchakli QPixmap qiladi.
    Muqova yo'q bo'lsa — turga mos ikonkali kulrang plashka."""
    pm = QPixmap(w, h)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(0, 0, w, h), radius, radius)
    p.setClipPath(clip)

    src = None
    if item.get("cover_path"):
        cand = os.path.join(config.COVERS_DIR, item["cover_path"])
        if os.path.exists(cand):
            src = QPixmap(cand)
    if src and not src.isNull():
        scaled = src.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                            Qt.TransformationMode.SmoothTransformation)
        p.drawPixmap(0, 0, scaled,
                     (scaled.width() - w) // 2, (scaled.height() - h) // 2, w, h)
    else:
        p.fillRect(0, 0, w, h, QColor("#EEF2F7"))
        icon_name = {"movie": "clapperboard", "cartoon": "clapperboard",
                     "book": "file-text", "audiobook": "file-text"}.get(
            item.get("type"), "image")
        ic = svg_pixmap(icon_name, "#94A3B8", 34)
        p.drawPixmap((w - 34) // 2, (h - 34) // 2, ic)
    p.end()
    return pm


class AdminContentCard(QFrame):
    """Bitta kontent kartochkasi: muqova (tur badge + tavsiya yulduzchasi
    ustida), nom, muallif·janr va tahrirlash/o'chirish tugmalari.
    Kartaning o'zi bosilsa — tahrirlash ochiladi."""

    def __init__(self, item, on_edit, on_delete):
        super().__init__()
        self.item = item
        self._on_edit = on_edit
        self.setObjectName("contentCard")
        self.setFixedWidth(CARD_W)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(7)

        # Muqova
        cover = QLabel()
        cover.setFixedSize(COVER_W, COVER_H)
        cover.setPixmap(_cover_pixmap(item, COVER_W, COVER_H))
        lay.addWidget(cover)

        # Tur badge — muqova ustida (chap-tepa)
        fg, _bg = TYPE_COLORS.get(item.get("type"), (C_MUTED, "#F1F5F9"))
        badge = QLabel(TYPE_LABELS.get(item.get("type"), item.get("type")), cover)
        badge.setStyleSheet(
            f"background: rgba(255,255,255,0.93); color: {fg};"
            "border-radius: 9px; padding: 3px 9px;"
            "font-weight: 700; font-size: 11px;")
        badge.adjustSize()
        badge.move(8, 8)

        # Tavsiya — o'ng-tepa yulduzcha
        if item.get("is_recommended"):
            star = QLabel("★", cover)
            star.setStyleSheet(
                "background: rgba(255,255,255,0.93); color: #D97706;"
                "border-radius: 9px; padding: 1px 7px 3px 7px;"
                "font-weight: 700; font-size: 14px;")
            star.adjustSize()
            star.move(COVER_W - star.width() - 8, 8)

        title = QLabel(item.get("title", ""))
        title.setObjectName("ccTitle")
        title.setWordWrap(True)
        lay.addWidget(title)

        sub_parts = [p for p in (item.get("author"), item.get("genre")) if p]
        if sub_parts:
            sub = QLabel(" • ".join(sub_parts))
            sub.setObjectName("ccSub")
            sub.setWordWrap(True)
            lay.addWidget(sub)

        # Majburiy fayl yetishmasa — ogohlantirish (kioskda ochilmaydi)
        t = item.get("type")
        warn = None
        if t in ("movie", "cartoon", "music", "audiobook") and not item.get("file_path"):
            warn = "Media fayl yo'q"
        elif t == "book" and not item.get("text_path"):
            warn = "Matn fayli yo'q"
        if warn:
            wl = QLabel("⚠ " + warn)
            wl.setObjectName("ccWarn")
            lay.addWidget(wl)

        lay.addStretch(1)

        # Pastki qator: ID + amal tugmalari
        foot = QHBoxLayout()
        foot.setSpacing(6)
        id_lbl = QLabel(f"#{item['id']}")
        id_lbl.setObjectName("hint")
        foot.addWidget(id_lbl)
        foot.addStretch(1)
        edit_b = QPushButton()
        edit_b.setObjectName("iconBtn")
        edit_b.setIcon(svg_icon("pencil", "#334155", 32))
        edit_b.setIconSize(QSize(15, 15))
        edit_b.setToolTip("Tahrirlash")
        edit_b.setCursor(Qt.CursorShape.PointingHandCursor)
        edit_b.clicked.connect(lambda: on_edit(self.item))
        del_b = QPushButton()
        del_b.setObjectName("iconBtnDanger")
        del_b.setIcon(svg_icon("trash-2", C_BAD, 32))
        del_b.setIconSize(QSize(15, 15))
        del_b.setToolTip("O'chirish")
        del_b.setCursor(Qt.CursorShape.PointingHandCursor)
        del_b.clicked.connect(lambda: on_delete(self.item))
        foot.addWidget(edit_b)
        foot.addWidget(del_b)
        lay.addLayout(foot)

    def mouseReleaseEvent(self, e):
        # Kartaning bo'sh joyi bosilsa ham tahrirlash ochilsin
        if (e.button() == Qt.MouseButton.LeftButton
                and self.rect().contains(e.position().toPoint())):
            self._on_edit(self.item)
        super().mouseReleaseEvent(e)
