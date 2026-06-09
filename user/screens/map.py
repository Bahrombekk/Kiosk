"""
map.py — Xarita (Map) bo'limi.

Katta oq karta ichida:
  - kulrang sarlavha banneri: poyezd nomi, yo'nalish, 3 chip, poyezd rasmi;
  - chapda bekatlar timeline'i (skroll qilinadi);
  - o'ngda HAQIQIY, INTERAKTIV offline xarita (lokal OSM/Carto plitkalaridan) —
    suriladi (drag), zumlanadi (g'ildirak yoki +/− tugmalari).

Bu ekran QGraphicsView miqyoslagichiga O'RALMAGAN — shunda xarita to'g'ridan-to'g'ri
sichqoncha hodisalarini oladi (interaktiv bo'ladi). Moslashuvchan layout ishlatiladi.
"""
import os
from datetime import datetime

from PyQt6.QtWidgets import (QWidget, QFrame, QLabel, QHBoxLayout, QVBoxLayout,
                             QScrollArea, QSizePolicy)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QRectF
from PyQt6.QtGui import QPixmap, QColor, QPen, QBrush, QFont, QPainter

import theme as T
from threads import track
from widgets.slippymap import SlippyMap

ASSETS = os.path.join(os.path.dirname(__file__), "..", "assets", "design")
TRAIN_IMG = os.path.join(ASSETS, "train.png")

UZ_MONTHS = ["", "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
             "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"]


class _Loader(QThread):
    done = pyqtSignal(list, dict, dict)
    fail = pyqtSignal()

    def __init__(self, api):
        super().__init__()
        self.api = api

    def run(self):
        try:
            self.done.emit(self.api.get_route(), self.api.get_status(),
                           self.api.get_settings())
        except Exception:
            self.fail.emit()


class Timeline(QWidget):
    """Bekatlar timeline'i (skroll uchun qat'iy oraliqli)."""

    PAD_T = 30
    STOP_GAP = 92

    def __init__(self):
        super().__init__()
        self.stops = []
        self.current = 0
        self.theme_name = "light"
        self.setStyleSheet("background: transparent;")

    def set_data(self, stops, current, theme_name):
        self.stops = stops
        self.current = current
        self.theme_name = theme_name
        n = len(stops)
        self.setMinimumHeight(self.PAD_T * 2 + max(0, n - 1) * self.STOP_GAP)
        self.update()

    def paintEvent(self, e):
        if not self.stops:
            return
        c = T.THEMES[self.theme_name]
        accent = QColor(c["accent"])
        gray = QColor("#C7CDD8")
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        n = len(self.stops)
        x = 26
        text_x = 56
        ys = [self.PAD_T + i * self.STOP_GAP for i in range(n)]

        for i in range(n - 1):
            y1, y2 = ys[i] + 11, ys[i + 1] - 11
            if i < self.current:
                p.setPen(QPen(accent, 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            else:
                p.setPen(QPen(gray, 3, Qt.PenStyle.DashLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(int(x), int(y1), int(x), int(y2))

        name_font = QFont(); name_font.setPixelSize(24); name_font.setWeight(QFont.Weight.Bold)
        small_font = QFont(); small_font.setPixelSize(15); small_font.setWeight(QFont.Weight.Medium)

        for i, s in enumerate(self.stops):
            y = ys[i]
            if i < self.current:
                p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(accent))
                p.drawEllipse(int(x - 8), int(y - 8), 16, 16)
            elif i == self.current:
                p.setBrush(QBrush(QColor("#FFFFFF"))); p.setPen(QPen(accent, 4))
                p.drawEllipse(int(x - 9), int(y - 9), 18, 18)
            else:
                p.setBrush(QBrush(QColor("#FFFFFF"))); p.setPen(QPen(gray, 3))
                p.drawEllipse(int(x - 7), int(y - 7), 14, 14)

            time = s.get("arrival_time") or ""
            if i == 0:
                detail = f"Jo'nagan: {time}" if time else ""
            elif i == n - 1:
                detail = f"Yetib kelish: {time}" if time else ""
            else:
                detail = time

            p.setFont(name_font)
            p.setPen(accent if i == self.current else QColor(c["text"]))
            p.drawText(QRectF(text_x, y - 22, 320, 28),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       s.get("name", ""))
            p.setFont(small_font)
            p.setPen(QColor(c["text_secondary"]))
            p.drawText(QRectF(text_x, y + 6, 320, 22),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       detail)
        p.end()


class MapScreen(QWidget):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self.theme_name = "light"
        self.stops = []
        self.current = 0
        self._loader = None
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 12, 24, 24)

        self.card = QFrame()
        self.card.setObjectName("mainCard")
        cv = QVBoxLayout(self.card)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.setSpacing(0)

        # ---- Sarlavha banneri ----
        self.header = QFrame()
        self.header.setObjectName("mapHeader")
        self.header.setFixedHeight(196)
        hh = QHBoxLayout(self.header)
        hh.setContentsMargins(34, 26, 30, 26)
        left = QVBoxLayout()
        left.setSpacing(6)
        self.train_name = QLabel("Poyezd")
        self.train_name.setObjectName("hTitle")
        self.route = QLabel("")
        self.route.setObjectName("hSub")
        left.addWidget(self.train_name)
        left.addWidget(self.route)
        chips = QHBoxLayout()
        chips.setSpacing(14)
        self.chip_date = self._chip("📅", "")
        self.chip_depart = self._chip("🕐", "")
        self.chip_dur = self._chip("🏁", "")
        for ch in (self.chip_date, self.chip_depart, self.chip_dur):
            chips.addWidget(ch)
        chips.addStretch(1)
        left.addSpacing(6)
        left.addLayout(chips)
        left.addStretch(1)
        hh.addLayout(left, 1)

        self.train_img = QLabel()
        tpm = QPixmap(TRAIN_IMG)
        if not tpm.isNull():
            self.train_img.setPixmap(tpm.scaledToHeight(
                150, Qt.TransformationMode.SmoothTransformation))
        self.train_img.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        hh.addWidget(self.train_img, 0, Qt.AlignmentFlag.AlignVCenter)
        cv.addWidget(self.header)

        # ---- Tana: timeline (chap) + xarita (o'ng) ----
        body = QHBoxLayout()
        body.setContentsMargins(28, 24, 28, 28)
        body.setSpacing(26)

        self.timeline = Timeline()
        self.tl_scroll = QScrollArea()
        self.tl_scroll.setObjectName("tlScroll")
        self.tl_scroll.setWidget(self.timeline)
        self.tl_scroll.setWidgetResizable(True)
        self.tl_scroll.setFixedWidth(380)
        self.tl_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.tl_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tl_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        body.addWidget(self.tl_scroll)

        self.slippy = SlippyMap(radius=22)
        self.slippy.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        body.addWidget(self.slippy, 1)

        cv.addLayout(body, 1)
        root.addWidget(self.card)

    def _chip(self, emoji, text):
        chip = QFrame()
        chip.setObjectName("chip")
        chip.setFixedHeight(48)
        lay = QHBoxLayout(chip)
        lay.setContentsMargins(16, 0, 18, 0)
        lay.setSpacing(9)
        ic = QLabel(emoji); ic.setObjectName("chipIc")
        lbl = QLabel(text); lbl.setObjectName("chipTxt")
        lay.addWidget(ic)
        lay.addWidget(lbl)
        chip._text = lbl
        return chip

    # ---- Ma'lumot ----
    def on_show(self):
        self._loader = track(_Loader(self.api))
        self._loader.done.connect(self._on_data)
        self._loader.start()

    def _on_data(self, stops, status, settings):
        self.stops = stops
        cur_name = status.get("current_stop")
        self.current = next((i for i, s in enumerate(stops)
                             if s.get("name") == cur_name), 0)
        self.train_name.setText(status.get("train_name")
                                or settings.get("train_name") or "Poyezd")
        route = status.get("route") or settings.get("route") or ""
        if "→" in route:
            a, _, b = route.partition("→")
            self.route.setText(
                f"{a.strip()} <font color='{T.THEMES[self.theme_name]['accent']}'>"
                f"&rarr;</font> {b.strip()}")
        else:
            self.route.setText(route)
        self.chip_date._text.setText(self._today())
        self.chip_depart._text.setText(f"Jo'nash: {settings.get('depart_time') or '—'}")
        self.chip_dur._text.setText(settings.get("duration") or "—")
        self.timeline.set_data(stops, self.current, self.theme_name)
        self.slippy.set_route(stops, self.current, self.theme_name)

    def _today(self):
        d = datetime.now()
        return f"{d.day}-{UZ_MONTHS[d.month]}, {d.year}"

    # ---- Mavzu ----
    def apply_theme(self, name):
        self.theme_name = name
        c = T.THEMES[name]
        self.setStyleSheet(
            f"#mainCard {{ background: {c['surface']}; border-radius: 26px; }}"
            f"#mapHeader {{ background: #E9EDF5;"
            f" border-top-left-radius: 26px; border-top-right-radius: 26px; }}"
            f"#hTitle {{ background: transparent; color: #1C2230;"
            f" font-size: 36px; font-weight: 700; }}"
            f"#hSub {{ background: transparent; color: #8B94A4;"
            f" font-size: 22px; font-weight: 500; }}"
            f"#chip {{ background: #FFFFFF; border-radius: 12px; }}"
            f"#chipIc {{ background: transparent; font-size: 18px; }}"
            f"#chipTxt {{ background: transparent; color: #2B3340;"
            f" font-size: 18px; font-weight: 600; }}"
            f"#tlScroll {{ background: transparent; }}"
            f"#tlScroll QWidget {{ background: transparent; }}")
        if self.stops:
            self.timeline.set_data(self.stops, self.current, name)
            self.slippy.set_route(self.stops, self.current, name)
