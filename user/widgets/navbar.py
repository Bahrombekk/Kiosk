"""
navbar.py — Yuqori navigatsiya paneli (Figma'dagi kabi).
Chapda: yumaloq panel ichida 5 bo'lim. Faol bo'lim ko'k pill (ikonka + matn),
qolganlari faqat ikonka. O'ngda: Asosiy'da soat, boshqa ekranlarda bo'lim nomi.
Ikonkalar mavzu rangiga moslab avtomatik bo'yaladi (oq/kulrang).
"""
import os
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel, QFrame
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QRectF
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
from PyQt6.QtSvg import QSvgRenderer
from core import i18n
from core import theme as T

ICON_DIR = os.path.join(os.path.dirname(__file__), "..", "assets", "icons")


def colored_icon(path, color_hex, size=48):
    """SVG ikonkani berilgan rangda QIcon qilib qaytaradi."""
    if not os.path.exists(path):
        return QIcon()
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    QSvgRenderer(path).render(p, QRectF(0, 0, size, size))
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    p.fillRect(pm.rect(), QColor(color_hex))
    p.end()
    return QIcon(pm)


class NavBar(QWidget):
    navigate = pyqtSignal(str)
    lang_changed = pyqtSignal(str)   # til almashtirgich bosilganda ("uz"/"ru"/"en")
    sos_clicked = pyqtSignal()       # SOS (favqulodda ma'lumot) tugmasi

    def __init__(self):
        super().__init__()
        self.active = "home"
        self.theme = T.THEMES["light"]
        self.buttons = {}          # kalit -> [btn, icon_path]
        self._build()

    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(T.SPACE["page"], T.SPACE["gap"],
                                T.SPACE["page"], T.SPACE["gap"])

        self.pill = QFrame()
        self.pill.setObjectName("navPill")
        pl = QHBoxLayout(self.pill)
        pl.setContentsMargins(T.s(8), T.s(8), T.s(8), T.s(8))
        pl.setSpacing(T.s(6))

        for key, icon_file in T.NAV_ITEMS:
            btn = QPushButton()
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setIconSize(QSize(T.s(24), T.s(24)))
            btn.setFixedHeight(T.s(52))   # qat'iy balandlik — radius yarmiga = to'liq pill
            btn.clicked.connect(lambda _c, k=key: self.navigate.emit(k))
            self.buttons[key] = [btn, os.path.join(ICON_DIR, icon_file)]
            pl.addWidget(btn)

        root.addWidget(self.pill, alignment=Qt.AlignmentFlag.AlignLeft)
        root.addStretch(1)

        # SOS — favqulodda xizmat raqamlari modalini ochadi (qizil pill).
        # Ommaviy kioskda doim ko'rinib turishi kerak (xavfsizlik talabi).
        self.sos_btn = QPushButton(" " + i18n.tr("sos.btn"))
        self.sos_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sos_btn.setFixedHeight(T.s(56))
        self.sos_btn.setIconSize(QSize(T.s(22), T.s(22)))
        self.sos_btn.clicked.connect(self.sos_clicked.emit)
        root.addWidget(self.sos_btn, alignment=Qt.AlignmentFlag.AlignRight)
        root.addSpacing(T.s(14))

        # Til almashtirgich: UZ | RU | EN (segmentli pill, nav pill uslubida).
        # Maxfiy chiqish tap-zonasi (self.right) bilan aralashmasin — alohida
        # widget, soat yorlig'idan chapda turadi.
        self.lang_pill = QFrame()
        self.lang_pill.setObjectName("langPill")
        ll = QHBoxLayout(self.lang_pill)
        ll.setContentsMargins(T.s(6), T.s(6), T.s(6), T.s(6))
        ll.setSpacing(T.s(4))
        self.lang_btns = {}
        for code in i18n.LANGS:
            b = QPushButton(code.upper())
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFixedSize(T.s(64), T.s(44))
            b.clicked.connect(lambda _c, c=code: self.lang_changed.emit(c))
            self.lang_btns[code] = b
            ll.addWidget(b)
        root.addWidget(self.lang_pill, alignment=Qt.AlignmentFlag.AlignRight)
        root.addSpacing(T.s(14))

        # Oflayn indikatori — server uzilib keshdan ishlayotganda ko'rinadi
        self.offline_lbl = QLabel(i18n.tr("common.offline"))
        self.offline_lbl.setObjectName("navOffline")
        self.offline_lbl.hide()
        root.addWidget(self.offline_lbl, alignment=Qt.AlignmentFlag.AlignRight)

        # Soat — BARCHA sahifalarda doim ko'rinadi (maxfiy chiqish zonasi ham shu)
        self.clock = QLabel("")
        self.clock.setObjectName("navClock")
        root.addWidget(self.clock, alignment=Qt.AlignmentFlag.AlignRight)
        root.addSpacing(T.s(18))

        # Sahifa nomi (Asosiy'da bo'sh) — soatdan o'ngda
        self.right = QLabel("")
        self.right.setObjectName("navRight")
        root.addWidget(self.right, alignment=Qt.AlignmentFlag.AlignRight)
        self.set_active("home")

    def set_offline(self, offline):
        self.offline_lbl.setVisible(bool(offline))

    def set_sos_visible(self, visible):
        """Admin sozlamasiga ko'ra SOS tugmasini ko'rsatadi/yashiradi."""
        self.sos_btn.setVisible(bool(visible))

    def set_clock(self, text):
        # Soat barcha sahifalarda ko'rinadi (alohida yorliqda)
        self.clock.setText(text)

    def set_active(self, key):
        self.active = key
        self.right.setText(
            "" if key == "home" else i18n.tr(f"title.{key}").upper())
        self._restyle()

    def apply_theme(self, name):
        self.theme = T.THEMES[name]
        self._restyle()

    def _restyle(self):
        c = self.theme
        # To'liq pill (kapsula): radius = balandlikning yarmi.
        btn_h = T.s(52)
        btn_r = btn_h // 2
        pill_r = (btn_h + 2 * T.s(8)) // 2     # pill konteyner balandligi = tugma + margin
        self.pill.setStyleSheet(
            f"#navPill {{ background: {c['surface']};"
            f" border-radius: {pill_r}px; }}")
        self.right.setStyleSheet(
            f"#navRight {{ color: {c['text']}; font-size: {T.FONT['clock']}px;"
            f" font-weight: 600; }}")
        self.clock.setStyleSheet(
            f"#navClock {{ color: {c['text']}; font-size: {T.FONT['clock']}px;"
            f" font-weight: 600; }}")
        self.offline_lbl.setText(i18n.tr("common.offline"))
        self.offline_lbl.setStyleSheet(
            f"#navOffline {{ color: #F59E0B; font-size: {T.FONT['nav']}px;"
            f" font-weight: 700; padding-right: {T.s(14)}px; }}")
        # SOS: telefon ikonkali qizil gradient kapsula. MUHIM: radius aynan
        # balandlikning yarmidan hisoblanadi — T.s() yaxlitlashida radius
        # yarmidan 1px oshsa Qt burchaklarni umuman yumaloqlamaydi (kvadrat
        # bo'lib qoladi).
        sos_h = T.s(56)
        self.sos_btn.setIcon(colored_icon(
            os.path.join(ICON_DIR, "phone.svg"), "#FFFFFF", T.s(22)))
        self.sos_btn.setStyleSheet(
            f"QPushButton {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1,"
            f" stop:0 #F87171, stop:1 #DC2626); color: #FFFFFF;"
            f" border: none; border-radius: {sos_h // 2}px;"
            f" padding: 0 {T.s(26)}px 0 {T.s(20)}px;"
            f" font-size: {T.FONT['nav']}px; font-weight: 800; }}"
            f"QPushButton:pressed {{ background: #B91C1C; }}")
        # Til almashtirgich pill: faol til — accent, qolganlari shaffof
        lang_r = (T.s(44) + 2 * T.s(6)) // 2
        self.lang_pill.setStyleSheet(
            f"#langPill {{ background: {c['surface']};"
            f" border-radius: {lang_r}px; }}")
        for code, b in self.lang_btns.items():
            if code == i18n.get_lang():
                b.setStyleSheet(
                    f"QPushButton {{ background: {c['accent']};"
                    f" color: {c['accent_text']}; border: none;"
                    f" border-radius: {T.s(44) // 2}px;"
                    f" font-size: {T.FONT['nav']}px; font-weight: 700; }}")
            else:
                b.setStyleSheet(
                    f"QPushButton {{ background: transparent; border: none;"
                    f" color: {c['text_secondary']};"
                    f" border-radius: {T.s(44) // 2}px;"
                    f" font-size: {T.FONT['nav']}px; font-weight: 600; }}"
                    f"QPushButton:hover {{ background: {c['surface2']}; }}"
                    f"QPushButton:pressed {{ background: {c['border']}; }}")
        for key, (btn, icon_path) in self.buttons.items():
            if key == self.active:
                btn.setText(" " + i18n.tr(f"nav.{key}"))
                btn.setIcon(colored_icon(icon_path, c["accent_text"]))
                btn.setStyleSheet(
                    f"QPushButton {{ background: {c['accent']};"
                    f" color: {c['accent_text']}; border: none;"
                    f" border-radius: {btn_r}px;"
                    f" padding: 0 {T.s(22)}px; font-size: {T.FONT['nav']}px;"
                    f" font-weight: 600; }}")
            else:
                btn.setText("")
                # Faol bo'lmagan ikonkalar to'q rangda (Figma dizayni)
                btn.setIcon(colored_icon(icon_path, c["text"]))
                btn.setStyleSheet(
                    f"QPushButton {{ background: transparent; border: none;"
                    f" border-radius: {btn_r}px; padding: 0 {T.s(16)}px; }}"
                    f"QPushButton:hover {{ background: {c['surface2']}; }}"
                    f"QPushButton:pressed {{ background: {c['border']}; }}")
