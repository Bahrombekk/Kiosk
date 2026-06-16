"""ui/cards.py — Kartochkalar (kontent/reklama), to'r va pixmap yordamchilari."""
import os

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QFrame, QScrollArea, QGridLayout)
from PyQt6.QtCore import Qt, QSize, QRectF, QPointF, QTimer
from PyQt6.QtGui import (QPixmap, QColor, QPainter, QPainterPath, QImage,
                         QLinearGradient, QBrush, QFont)

import config
from icons import svg_icon, svg_pixmap
from ui.styles import TYPE_LABELS, TYPE_COLORS, C_MUTED, C_BAD


# ----------------------------------------------------------------------------
#  CardGrid — qayta ishlatiladigan kartochkalar to'ri (scroll + moslashuvchan
#  ustunlar). Kartalar chap-tepada zich turadi, bo'sh joyga cho'zilmaydi.
# ----------------------------------------------------------------------------
class CardGrid(QScrollArea):
    def __init__(self, card_w, spacing=14):
        super().__init__()
        self._card_w = card_w
        self._cards = []
        self._cols_now = 0
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        host = QWidget()
        host.setStyleSheet("background: transparent;")
        self._grid = QGridLayout(host)
        self._grid.setContentsMargins(0, 4, 0, 12)
        self._grid.setHorizontalSpacing(spacing)
        self._grid.setVerticalSpacing(spacing)
        self._grid.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.setWidget(host)
        self.viewport().setStyleSheet("background: transparent;")

    def set_cards(self, cards):
        """Eski kartalarni tozalab, yangilarini teradi."""
        while self._grid.count():
            old = self._grid.takeAt(0).widget()
            if old:
                old.deleteLater()
        self._cards = list(cards)
        self._regrid()
        QTimer.singleShot(0, self._recheck)

    def _cols(self):
        avail = self.viewport().width()
        if avail <= 0:
            avail = max(self.width(), self._card_w)
        sp = self._grid.horizontalSpacing()
        return max(1, (avail + sp) // (self._card_w + sp))

    def _regrid(self):
        g = self._grid
        cols = self._cols()
        self._cols_now = cols
        for i, card in enumerate(self._cards):
            g.addWidget(card, i // cols, i % cols,
                        Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        # Avvalgi stretchlarni nollab, oxiriga yangisini qo'yamiz
        rows = (len(self._cards) + cols - 1) // cols
        for c in range(g.columnCount() + 1):
            g.setColumnStretch(c, 0)
        for r in range(g.rowCount() + 1):
            g.setRowStretch(r, 0)
        g.setColumnStretch(cols, 1)
        g.setRowStretch(rows, 1)

    def _recheck(self):
        if self._cards and self._cols() != self._cols_now:
            self._regrid()

    # Resize/ko'rinish o'zgarganda layout o'rnashgach qayta tekshiramiz
    def resizeEvent(self, e):
        super().resizeEvent(e)
        QTimer.singleShot(0, self._recheck)

    def showEvent(self, e):
        super().showEvent(e)
        QTimer.singleShot(0, self._recheck)


# ----------------------------------------------------------------------------
#  CardFlow — CardGrid'ning SKROLLSIZ varianti: tashqi umumiy scroll ichida
#  bo'lim (masalan, Reklama sahifasida Popup/Banner guruhlari) sifatida
#  ishlatiladi. Kenglik o'zgarsa ustun soni qayta hisoblanadi.
# ----------------------------------------------------------------------------
class CardFlow(QWidget):
    def __init__(self, card_w, spacing=14):
        super().__init__()
        self._card_w = card_w
        self._cards = []
        self._cols_now = 0
        self.setStyleSheet("background: transparent;")
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 4, 0, 12)
        self._grid.setHorizontalSpacing(spacing)
        self._grid.setVerticalSpacing(spacing)
        self._grid.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

    def set_cards(self, cards):
        while self._grid.count():
            old = self._grid.takeAt(0).widget()
            if old:
                old.deleteLater()
        self._cards = list(cards)
        self._regrid()
        QTimer.singleShot(0, self._recheck)

    def _cols(self):
        avail = self.width()
        if avail <= 0:
            avail = self._card_w
        sp = self._grid.horizontalSpacing()
        return max(1, (avail + sp) // (self._card_w + sp))

    def _regrid(self):
        g = self._grid
        cols = self._cols()
        self._cols_now = cols
        for i, card in enumerate(self._cards):
            g.addWidget(card, i // cols, i % cols,
                        Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        for c in range(g.columnCount() + 1):
            g.setColumnStretch(c, 0)
        g.setColumnStretch(cols, 1)

    def _recheck(self):
        if self._cards and self._cols() != self._cols_now:
            self._regrid()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        QTimer.singleShot(0, self._recheck)


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
    elif item.get("type") == "music":
        # Muqovasiz musiqa — gradient + nota (kioskdagi bilan bir xil ko'rinish)
        g = QLinearGradient(0, 0, w, h)
        g.setColorAt(0.0, QColor("#6366F1"))
        g.setColorAt(1.0, QColor("#8B5CF6"))
        p.fillRect(0, 0, w, h, QBrush(g))
        p.setPen(QColor(255, 255, 255, 235))
        f = QFont()
        f.setPixelSize(max(20, h // 2))
        p.setFont(f)
        p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, "♪")
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

        # Til badge — tur yonida (UZ/RU/EN; bo'sh = barcha tillarda, 🌐)
        lang = (item.get("lang") or "").strip()
        lb = QLabel(lang.upper() if lang else "🌐", cover)
        lb.setStyleSheet(
            "background: rgba(15,23,42,0.78); color: #FFFFFF;"
            "border-radius: 9px; padding: 3px 8px;"
            "font-weight: 700; font-size: 11px;")
        lb.adjustSize()
        lb.move(8 + badge.width() + 6, 8)

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

        # Lokal kesh belgisi qo'yilmagan media — kiosklarga yuklanmaydi
        # (faqat striming); admin buni kartadan ko'rib tursin.
        if (item.get("type") in ("movie", "cartoon", "music", "audiobook")
                and item.get("cache_enabled") is not None
                and not item.get("cache_enabled")):
            nc = QLabel("⛔ Kiosklarga yuklanmaydi (faqat striming)")
            nc.setObjectName("ccSub")
            nc.setStyleSheet("color: #B45309; font-size: 11px;"
                             " font-weight: 600;")
            lay.addWidget(nc)

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


# ----------------------------------------------------------------------------
#  Reklama kartochkasi
# ----------------------------------------------------------------------------
AD_CARD_W = 280                        # reklama kartasi kengligi
AD_THUMB_W = AD_CARD_W - 24
AD_THUMB_H = int(AD_THUMB_W * 9 / 16)  # 16:9


def _video_first_frame(path):
    """Videoning boshidan kadr oladi (cv2 bo'lsa); bo'lmasa None."""
    try:
        import cv2
        cap = cv2.VideoCapture(path)
        # Birinchi kadrlar ko'pincha qora — biroz oldinga suramiz
        total = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        if total > 30:
            cap.set(cv2.CAP_PROP_POS_FRAMES, min(30, int(total // 10)))
        ok, frame = cap.read()
        if not ok:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = cap.read()
        cap.release()
        if ok and frame is not None:
            h, w = frame.shape[:2]
            img = QImage(frame.data, w, h, frame.strides[0],
                         QImage.Format.Format_BGR888).copy()
            return QPixmap.fromImage(img)
    except Exception:                              # noqa: BLE001 — cv2 yo'q/xato
        pass
    return None


def _ad_thumb_pixmap(ad, w, h, radius=12):
    """Reklama thumbnail'i: rasm — o'zi, video — birinchi kadr + play belgisi,
    fayl yo'q — kulrang plashka."""
    pm = QPixmap(w, h)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(0, 0, w, h), radius, radius)
    p.setClipPath(clip)

    is_video = ad.get("media_kind") == "Video"
    src = None
    mp = ad.get("media_path") or ""
    path = os.path.join(config.ADS_DIR, mp) if mp else ""
    if ad.get("media_kind") and os.path.isfile(path):
        src = _video_first_frame(path) if is_video else QPixmap(path)
    if src and not src.isNull():
        scaled = src.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                            Qt.TransformationMode.SmoothTransformation)
        p.drawPixmap(0, 0, scaled,
                     (scaled.width() - w) // 2, (scaled.height() - h) // 2, w, h)
    else:
        p.fillRect(0, 0, w, h, QColor("#1E293B" if is_video else "#EEF2F7"))
        ic = svg_pixmap("clapperboard" if is_video else "image",
                        "#64748B" if is_video else "#94A3B8", 34)
        p.drawPixmap((w - 34) // 2, (h - 34) // 2, ic)
    # Video — markazda play belgisi (yarim shaffof doira + uchburchak)
    if is_video and src and not src.isNull():
        cx, cy, r = w / 2, h / 2, 22
        p.setBrush(QColor(15, 20, 30, 150))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy), r, r)
        tri = QPainterPath()
        tri.moveTo(cx - 7, cy - 11)
        tri.lineTo(cx - 7, cy + 11)
        tri.lineTo(cx + 12, cy)
        tri.closeSubpath()
        p.fillPath(tri, QColor("#FFFFFF"))
    p.end()
    return pm


def _overlay_badge(parent, text, fg, bg="rgba(255,255,255,0.93)"):
    """Thumbnail ustidagi kichik badge yorlig'i."""
    b = QLabel(text, parent)
    b.setStyleSheet(
        f"background: {bg}; color: {fg}; border-radius: 9px;"
        "padding: 3px 9px; font-weight: 700; font-size: 11px;")
    b.adjustSize()
    return b


class AdCard(QFrame):
    """Bitta reklama kartochkasi: thumbnail (media turi + holat badge'lari),
    sarlavha, «10 s · har 5 daq · 16:46–20:00» ma'lumot qatori va
    tahrirlash/o'chirish tugmalari. Kartaning o'zi bosilsa — tahrirlash."""

    def __init__(self, ad, on_edit, on_delete):
        super().__init__()
        self.ad = ad
        self._on_edit = on_edit
        self.setObjectName("contentCard")     # kontent kartasi uslubi qayta ishlatiladi
        self.setFixedWidth(AD_CARD_W)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(7)

        # Thumbnail
        thumb = QLabel()
        thumb.setFixedSize(AD_THUMB_W, AD_THUMB_H)
        thumb.setPixmap(_ad_thumb_pixmap(ad, AD_THUMB_W, AD_THUMB_H))
        lay.addWidget(thumb)

        # Chap-tepa: media turi (yoki fayl yo'q — qizil)
        kind = ad.get("media_kind")
        if kind == "Video":
            kb = _overlay_badge(thumb, "Video", "#1D4ED8")
        elif kind == "Rasm":
            kb = _overlay_badge(thumb, "Rasm", "#047857")
        else:
            kb = _overlay_badge(thumb, "Fayl yo'q", "#FFFFFF",
                                bg="rgba(220,38,38,0.92)")
        kb.move(8, 8)

        # O'ng-tepa: holat (Faol / O'chiq)
        if ad.get("is_active"):
            sb = _overlay_badge(thumb, "Faol", "#047857")
        else:
            sb = _overlay_badge(thumb, "O'chiq", "#64748B")
        sb.move(AD_THUMB_W - sb.width() - 8, 8)

        title = QLabel(ad.get("title") or "—")
        title.setObjectName("ccTitle")
        title.setWordWrap(True)
        lay.addWidget(title)

        # Ma'lumot qatori: joylashuv · namoyish · takrorlanish · vaqt oralig'i
        place_disp = {"banner": "Banner", "both": "Popup+Banner"}.get(
            ad.get("placement") or "popup", "Popup")
        info = QLabel(" · ".join(x for x in (
            place_disp, ad.get("dur_disp"), ad.get("int_disp"),
            ad.get("time_disp")) if x))
        info.setObjectName("ccSub")
        info.setWordWrap(True)
        lay.addWidget(info)

        if not kind:
            warn = QLabel("⚠ Media fayl topilmadi — kiosk o'tkazib yuboradi")
            warn.setObjectName("ccWarn")
            warn.setWordWrap(True)
            lay.addWidget(warn)

        lay.addStretch(1)

        # Pastki qator: ID + amal tugmalari
        foot = QHBoxLayout()
        foot.setSpacing(6)
        id_lbl = QLabel(f"#{ad['id']}")
        id_lbl.setObjectName("hint")
        foot.addWidget(id_lbl)
        foot.addStretch(1)
        edit_b = QPushButton()
        edit_b.setObjectName("iconBtn")
        edit_b.setIcon(svg_icon("pencil", "#334155", 32))
        edit_b.setIconSize(QSize(15, 15))
        edit_b.setToolTip("Tahrirlash")
        edit_b.setCursor(Qt.CursorShape.PointingHandCursor)
        edit_b.clicked.connect(lambda: on_edit(self.ad))
        del_b = QPushButton()
        del_b.setObjectName("iconBtnDanger")
        del_b.setIcon(svg_icon("trash-2", C_BAD, 32))
        del_b.setIconSize(QSize(15, 15))
        del_b.setToolTip("O'chirish")
        del_b.setCursor(Qt.CursorShape.PointingHandCursor)
        del_b.clicked.connect(lambda: on_delete(self.ad))
        foot.addWidget(edit_b)
        foot.addWidget(del_b)
        lay.addLayout(foot)

    def mouseReleaseEvent(self, e):
        if (e.button() == Qt.MouseButton.LeftButton
                and self.rect().contains(e.position().toPoint())):
            self._on_edit(self.ad)
        super().mouseReleaseEvent(e)
