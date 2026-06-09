"""
map.py — Xarita (Map) bo'limi (Figma "Xarita.html" maketiga moslangan).

Katta oq karta ichida:
  - kulrang sarlavha banneri: poyezd nomi, yo'nalish, 3 ta chip (sana / jo'nash /
    davomiylik) va poyezd rasmi;
  - chapda bekatlar timeline'i (o'tilgan to'la nuqta, joriy halqa, kelgusi bo'sh;
    o'tilgan qism to'liq chiziq, qolgani uzuq chiziq);
  - o'ngda marshrut xaritasi rasmi.
Bekatlar va joriy bekat serverdan olinadi (dinamik). Butun ekran qat'iy
o'lchamda quriladi va ScaledScreen orqali miqyoslanadi — katta ekranda buzilmaydi.
"""
import os
from datetime import datetime

from PyQt6.QtWidgets import QWidget, QFrame, QLabel, QHBoxLayout
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QRectF, QPointF
from PyQt6.QtGui import (QPixmap, QPainter, QPainterPath, QColor, QPen, QBrush,
                         QFont)

import theme as T
from widgets.scaled import ScaledScreen

ASSETS = os.path.join(os.path.dirname(__file__), "..", "assets", "design")
MAP_IMG = os.path.join(ASSETS, "map.png")
TRAIN_IMG = os.path.join(ASSETS, "train.png")

# Sahna o'lchami (Figma main-card 1918×1213 + atrofdagi kichik chekka)
BASE_W, BASE_H = 1980, 1280
CARD_X, CARD_Y, CARD_W, CARD_H = 31, 34, 1918, 1213

UZ_MONTHS = ["", "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
             "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"]


class _Loader(QThread):
    done = pyqtSignal(list, dict, dict)   # stops, status, settings
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


def _rounded(pm, w, h, radius):
    """Pixmap'ni w×h ga to'ldirib (cover) burchaklarini yumaloqlaydi."""
    scaled = pm.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                       Qt.TransformationMode.SmoothTransformation)
    out = QPixmap(w, h)
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(0, 0, w, h, radius, radius)
    p.setClipPath(path)
    p.drawPixmap((w - scaled.width()) // 2, (h - scaled.height()) // 2, scaled)
    p.end()
    return out


class Timeline(QWidget):
    """Bekatlar timeline'i — chiziq (o'tilgan: to'liq, qolgani: uzuq) + nuqtalar."""

    def __init__(self):
        super().__init__()
        self.stops = []
        self.current = 0
        self.theme_name = "light"

    def set_data(self, stops, current, theme_name):
        self.stops = stops
        self.current = current
        self.theme_name = theme_name
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
        pad_t, pad_b = 36, 40
        x = 92                      # nuqtalar markazi
        text_x = 156
        H = self.height()
        ys = [pad_t if n == 1 else pad_t + i * (H - pad_t - pad_b) / (n - 1)
              for i in range(n)]

        # --- Bog'lovchi chiziqlar ---
        for i in range(n - 1):
            y1, y2 = ys[i] + 18, ys[i + 1] - 18
            if i < self.current:                       # o'tilgan — to'liq ko'k
                p.setPen(QPen(accent, 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            else:                                      # qolgan — uzuq kulrang
                p.setPen(QPen(gray, 5, Qt.PenStyle.DashLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(QPointF(x, y1), QPointF(x, y2))

        # --- Nuqtalar va matn ---
        name_font = QFont(); name_font.setPixelSize(56); name_font.setWeight(QFont.Weight.Bold)
        small_font = QFont(); small_font.setPixelSize(34); small_font.setWeight(QFont.Weight.Medium)

        for i, s in enumerate(self.stops):
            y = ys[i]
            if i < self.current:                       # o'tilgan — to'la
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(accent))
                p.drawEllipse(QPointF(x, y), 16, 16)
            elif i == self.current:                    # joriy — halqa
                p.setBrush(QBrush(QColor("#FFFFFF")))
                p.setPen(QPen(accent, 7))
                p.drawEllipse(QPointF(x, y), 15, 15)
            else:                                      # kelgusi — bo'sh
                p.setBrush(QBrush(QColor(c["surface"])))
                p.setPen(QPen(gray, 5))
                p.drawEllipse(QPointF(x, y), 14, 14)

            time = s.get("arrival_time") or ""
            if i == 0:
                detail = f"Jo'nagan: {time}" if time else ""
            elif i == n - 1:
                detail = f"Yetib kelish: {time}" if time else ""
            else:
                detail = time

            # nom
            p.setFont(name_font)
            p.setPen(accent if i == self.current else QColor(c["text"]))
            p.drawText(QRectF(text_x, y - 44, 600, 60),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       s.get("name", ""))
            # detal (vaqt)
            p.setFont(small_font)
            p.setPen(QColor(c["text_secondary"]))
            p.drawText(QRectF(text_x, y + 12, 600, 44),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       detail)
        p.end()


class _MapCanvas(QWidget):
    """Xarita tarkibi — qat'iy BASE_W×BASE_H o'lchamda."""

    def __init__(self, api):
        super().__init__()
        self.api = api
        self.theme_name = "light"
        self.stops = []
        self.current = 0
        self._loader = None
        self.setObjectName("mapBg")
        self.setFixedSize(BASE_W, BASE_H)
        self._build()

    def _build(self):
        # Oq asosiy karta
        self.card = QFrame(self)
        self.card.setObjectName("mainCard")
        self.card.setGeometry(CARD_X, CARD_Y, CARD_W, CARD_H)

        # --- Sarlavha banneri ---
        self.header = QFrame(self.card)
        self.header.setObjectName("mapHeader")
        self.header.setGeometry(0, 0, CARD_W, 372)

        self.train_name = QLabel("Poyezd", self.header)
        self.train_name.setObjectName("hTitle")
        self.train_name.setGeometry(64, 46, 1100, 84)

        self.route = QLabel("", self.header)
        self.route.setObjectName("hSub")
        self.route.setGeometry(64, 142, 1100, 56)

        # chiplar
        self.chips = QWidget(self.header)
        self.chips.setGeometry(64, 236, 1120, 92)
        crow = QHBoxLayout(self.chips)
        crow.setContentsMargins(0, 0, 0, 0)
        crow.setSpacing(22)
        self.chip_date = self._chip("📅", "")
        self.chip_depart = self._chip("🕐", "")
        self.chip_dur = self._chip("🏁", "")
        for ch in (self.chip_date, self.chip_depart, self.chip_dur):
            crow.addWidget(ch)
        crow.addStretch(1)

        # poyezd rasmi
        self.train_img = QLabel(self.header)
        self.train_img.setGeometry(CARD_W - 46 - 670, 40, 670, 316)
        tpm = QPixmap(TRAIN_IMG)
        if not tpm.isNull():
            self.train_img.setPixmap(tpm.scaled(
                670, 316, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
        self.train_img.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)

        # --- Timeline ---
        self.timeline = Timeline()
        self.timeline.setParent(self.card)
        self.timeline.setGeometry(0, 398, 760, 770)

        # --- Xarita rasmi ---
        self.map_lbl = QLabel(self.card)
        self.map_lbl.setObjectName("mapImg")
        self.map_lbl.setGeometry(775, 398, 1060, 750)
        mpm = QPixmap(MAP_IMG)
        if not mpm.isNull():
            self.map_lbl.setPixmap(_rounded(mpm, 1060, 750, 28))

    def _chip(self, emoji, text):
        chip = QFrame()
        chip.setObjectName("chip")
        chip.setFixedHeight(88)
        lay = QHBoxLayout(chip)
        lay.setContentsMargins(30, 0, 32, 0)
        lay.setSpacing(16)
        ic = QLabel(emoji)
        ic.setObjectName("chipIc")
        lbl = QLabel(text)
        lbl.setObjectName("chipTxt")
        lay.addWidget(ic)
        lay.addWidget(lbl)
        chip._text = lbl
        return chip

    # ---- Ma'lumot ----
    def on_show(self):
        self._loader = _Loader(self.api)
        self._loader.done.connect(self._on_data)
        self._loader.start()

    def _on_data(self, stops, status, settings):
        self.stops = stops
        cur_name = status.get("current_stop")
        self.current = next((i for i, s in enumerate(stops)
                             if s.get("name") == cur_name), 0)
        self.train_name.setText(status.get("train_name") or settings.get("train_name") or "Poyezd")
        route = status.get("route") or settings.get("route") or ""
        if "→" in route:
            a, _, b = route.partition("→")
            self.route.setText(
                f"{a.strip()} <font color='{T.THEMES[self.theme_name]['accent']}'>"
                f"&rarr;</font> {b.strip()}")
        else:
            self.route.setText(route)
        # chiplar
        self.chip_date._text.setText(self._today())
        depart = settings.get("depart_time") or "—"
        self.chip_depart._text.setText(f"Jo'nash: {depart}")
        self.chip_dur._text.setText(settings.get("duration") or "—")
        self.timeline.set_data(stops, self.current, self.theme_name)

    def _today(self):
        d = datetime.now()
        return f"{d.day}-{UZ_MONTHS[d.month]}, {d.year}"

    # ---- Mavzu ----
    def apply_theme(self, name):
        self.theme_name = name
        c = T.THEMES[name]
        self.setStyleSheet(
            f"#mapBg {{ background: transparent; }}"
            f"#mainCard {{ background: {c['surface']}; border-radius: 34px; }}"
            f"#mapHeader {{ background: #E9EDF5; border-radius: 34px; }}"
            f"#hTitle {{ background: transparent; color: #1C2230;"
            f" font-size: 70px; font-weight: 700; }}"
            f"#hSub {{ background: transparent; color: #8B94A4;"
            f" font-size: 42px; font-weight: 500; }}"
            f"#chip {{ background: #FFFFFF; border-radius: 18px; }}"
            f"#chipIc {{ background: transparent; font-size: 34px; }}"
            f"#chipTxt {{ background: transparent; color: #2B3340;"
            f" font-size: 36px; font-weight: 600; }}"
            f"#mapImg {{ background: transparent; }}")
        if self.stops:
            self.timeline.set_data(self.stops, self.current, name)


class MapScreen(ScaledScreen):
    def __init__(self, api):
        super().__init__(_MapCanvas(api))
