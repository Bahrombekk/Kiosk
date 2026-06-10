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
import theme as T

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

    def __init__(self):
        super().__init__()
        self.active = "home"
        self.theme = T.THEMES["light"]
        self.buttons = {}          # kalit -> [btn, label, icon_path]
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

        for key, label, icon_file, _title in T.NAV_ITEMS:
            btn = QPushButton()
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setIconSize(QSize(T.s(24), T.s(24)))
            btn.setFixedHeight(T.s(52))   # qat'iy balandlik — radius yarmiga = to'liq pill
            btn.clicked.connect(lambda _c, k=key: self.navigate.emit(k))
            self.buttons[key] = [btn, label, os.path.join(ICON_DIR, icon_file)]
            pl.addWidget(btn)

        root.addWidget(self.pill, alignment=Qt.AlignmentFlag.AlignLeft)
        root.addStretch(1)

        # Oflayn indikatori — server uzilib keshdan ishlayotganda ko'rinadi
        self.offline_lbl = QLabel("● Oflayn")
        self.offline_lbl.setObjectName("navOffline")
        self.offline_lbl.hide()
        root.addWidget(self.offline_lbl, alignment=Qt.AlignmentFlag.AlignRight)

        self.right = QLabel("")
        self.right.setObjectName("navRight")
        root.addWidget(self.right, alignment=Qt.AlignmentFlag.AlignRight)
        self.set_active("home")

    def set_offline(self, offline):
        self.offline_lbl.setVisible(bool(offline))

    def set_clock(self, text):
        if self.active == "home":
            self.right.setText(text)

    def set_active(self, key):
        self.active = key
        title = next((t for k, _l, _i, t in T.NAV_ITEMS if k == key), "")
        self.right.setText("" if key == "home" else title)
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
        self.offline_lbl.setStyleSheet(
            f"#navOffline {{ color: #F59E0B; font-size: {T.FONT['nav']}px;"
            f" font-weight: 700; padding-right: {T.s(14)}px; }}")
        for key, (btn, label, icon_path) in self.buttons.items():
            if key == self.active:
                btn.setText(" " + label)
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
                    f"QPushButton:hover {{ background: {c['surface2']}; }}")
