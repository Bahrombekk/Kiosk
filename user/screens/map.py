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
from widgets.icons import svg_pixmap
from widgets.routemap import RouteMap

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

    def __init__(self):
        super().__init__()
        self.stops = []
        self.current = 0
        self.theme_name = "light"
        # O'lchamlar ekran miqyosiga moslanadi (kichik/katta monitor).
        self.PAD_T = T.s(30)
        self.STOP_GAP = T.s(92)
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
        x = T.s(26)
        text_x = T.s(56)
        tw = T.s(320)
        ys = [self.PAD_T + i * self.STOP_GAP for i in range(n)]

        for i in range(n - 1):
            y1, y2 = ys[i] + T.s(11), ys[i + 1] - T.s(11)
            if i < self.current:
                p.setPen(QPen(accent, T.s(4), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            else:
                p.setPen(QPen(gray, T.s(3), Qt.PenStyle.DashLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(int(x), int(y1), int(x), int(y2))

        name_font = QFont(); name_font.setPixelSize(T.s(24)); name_font.setWeight(QFont.Weight.Bold)
        small_font = QFont(); small_font.setPixelSize(T.s(15)); small_font.setWeight(QFont.Weight.Medium)

        for i, s in enumerate(self.stops):
            y = ys[i]
            if i < self.current:
                p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(accent))
                r = T.s(8); p.drawEllipse(int(x - r), int(y - r), 2 * r, 2 * r)
            elif i == self.current:
                p.setBrush(QBrush(QColor("#FFFFFF"))); p.setPen(QPen(accent, T.s(4)))
                r = T.s(9); p.drawEllipse(int(x - r), int(y - r), 2 * r, 2 * r)
            else:
                p.setBrush(QBrush(QColor("#FFFFFF"))); p.setPen(QPen(gray, T.s(3)))
                r = T.s(7); p.drawEllipse(int(x - r), int(y - r), 2 * r, 2 * r)

            time = s.get("arrival_time") or ""
            if i == 0:
                detail = f"Jo'nagan: {time}" if time else ""
            elif i == n - 1:
                detail = f"Yetib kelish: {time}" if time else ""
            else:
                detail = time

            p.setFont(name_font)
            p.setPen(accent if i == self.current else QColor(c["text"]))
            p.drawText(QRectF(text_x, y - T.s(22), tw, T.s(28)),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       s.get("name", ""))
            p.setFont(small_font)
            p.setPen(QColor(c["text_secondary"]))
            p.drawText(QRectF(text_x, y + T.s(6), tw, T.s(22)),
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
        root.setContentsMargins(T.s(24), T.s(12), T.s(24), T.s(24))

        self.card = QFrame()
        self.card.setObjectName("mainCard")
        cv = QVBoxLayout(self.card)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.setSpacing(0)

        # ---- Sarlavha banneri ----
        self.header = QFrame()
        self.header.setObjectName("mapHeader")
        self.header.setFixedHeight(T.s(196))
        hh = QHBoxLayout(self.header)
        hh.setContentsMargins(T.s(34), T.s(26), T.s(30), T.s(26))
        left = QVBoxLayout()
        left.setSpacing(T.s(6))
        self.train_name = QLabel("Poyezd")
        self.train_name.setObjectName("hTitle")
        self.route = QLabel("")
        self.route.setObjectName("hSub")
        left.addWidget(self.train_name)
        left.addWidget(self.route)
        chips = QHBoxLayout()
        chips.setSpacing(T.s(14))
        self.chip_date = self._chip("calendar", "")
        self.chip_depart = self._chip("clock", "")
        self.chip_dur = self._chip("flag", "")
        for ch in (self.chip_date, self.chip_depart, self.chip_dur):
            chips.addWidget(ch)
        chips.addStretch(1)
        left.addSpacing(T.s(6))
        left.addLayout(chips)
        left.addStretch(1)
        hh.addLayout(left, 1)

        self.train_img = QLabel()
        tpm = QPixmap(TRAIN_IMG)
        if not tpm.isNull():
            self.train_img.setPixmap(tpm.scaledToHeight(
                T.s(150), Qt.TransformationMode.SmoothTransformation))
        self.train_img.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        hh.addWidget(self.train_img, 0, Qt.AlignmentFlag.AlignVCenter)
        cv.addWidget(self.header)

        # ---- Tana: timeline (chap) + xarita (o'ng) ----
        body = QHBoxLayout()
        body.setContentsMargins(T.s(28), T.s(24), T.s(28), T.s(28))
        body.setSpacing(T.s(26))

        self.timeline = Timeline()
        self.tl_scroll = QScrollArea()
        self.tl_scroll.setObjectName("tlScroll")
        self.tl_scroll.setWidget(self.timeline)
        self.tl_scroll.setWidgetResizable(True)
        self.tl_scroll.setFixedWidth(T.s(380))
        self.tl_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.tl_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tl_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        body.addWidget(self.tl_scroll)

        self.routemap = RouteMap(radius=T.s(22))
        self.routemap.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        body.addWidget(self.routemap, 1)

        cv.addLayout(body, 1)
        root.addWidget(self.card)

    def _chip(self, icon_name, text):
        chip = QFrame()
        chip.setObjectName("chip")
        chip.setFixedHeight(T.s(48))
        lay = QHBoxLayout(chip)
        lay.setContentsMargins(T.s(16), 0, T.s(18), 0)
        lay.setSpacing(T.s(9))
        ic = QLabel(); ic.setObjectName("chipIc")
        # Chip foni har mavzuda oq — ikonka rangi matn bilan bir xil (#2B3340)
        ic.setPixmap(svg_pixmap(icon_name, "#2B3340", T.s(20)))
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
        self.routemap.set_route(stops, self.current, self.theme_name)

    def _today(self):
        d = datetime.now()
        return f"{d.day}-{UZ_MONTHS[d.month]}, {d.year}"

    # ---- Mavzu ----
    def apply_theme(self, name):
        self.theme_name = name
        c = T.THEMES[name]
        self.setStyleSheet(
            f"#mainCard {{ background: {c['surface']}; border-radius: {T.s(26)}px; }}"
            f"#mapHeader {{ background: #E9EDF5;"
            f" border-top-left-radius: {T.s(26)}px; border-top-right-radius: {T.s(26)}px; }}"
            f"#hTitle {{ background: transparent; color: #1C2230;"
            f" font-size: {T.s(36)}px; font-weight: 700; }}"
            f"#hSub {{ background: transparent; color: #8B94A4;"
            f" font-size: {T.s(22)}px; font-weight: 500; }}"
            f"#chip {{ background: #FFFFFF; border-radius: {T.s(12)}px; }}"
            f"#chipIc {{ background: transparent; font-size: {T.s(18)}px; }}"
            f"#chipTxt {{ background: transparent; color: #2B3340;"
            f" font-size: {T.s(18)}px; font-weight: 600; }}"
            f"#tlScroll {{ background: transparent; }}"
            f"#tlScroll QWidget {{ background: transparent; }}")
        if self.stops:
            self.timeline.set_data(self.stops, self.current, name)
            self.routemap.set_route(self.stops, self.current, name)
