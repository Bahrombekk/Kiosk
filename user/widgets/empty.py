"""
empty.py — Bo'sh holat komponenti ("Hech narsa topilmadi" o'rniga).

Markazda yumaloq plitka ichida bo'lim ikonkasi + xabar — oddiy matndan ko'ra
tushunarliroq va dizaynga mos.
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt

from core import theme as T
from widgets.icons import svg_pixmap


class EmptyState(QWidget):
    def __init__(self, icon="globe", theme="light"):
        super().__init__()
        self._icon = icon
        self._theme = theme

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, T.s(40), 0, T.s(40))
        lay.setSpacing(T.s(18))
        lay.addStretch(1)

        self.tile = QLabel()
        self.tile.setObjectName("emptyTile")
        self.tile.setFixedSize(T.s(120), T.s(120))
        self.tile.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.tile, 0, Qt.AlignmentFlag.AlignHCenter)

        self.msg = QLabel("")
        self.msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.msg.setObjectName("emptyMsg")
        lay.addWidget(self.msg, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addStretch(2)

        self.hide()
        self.apply_theme(theme)

    def set_message(self, text):
        self.msg.setText(text)

    def apply_theme(self, name):
        self._theme = name
        c = T.THEMES[name]
        self.tile.setStyleSheet(
            f"#emptyTile {{ background: {c['surface2']};"
            f" border-radius: {T.s(28)}px; }}")
        self.tile.setPixmap(svg_pixmap(self._icon, c["text_secondary"], T.s(64)))
        self.msg.setStyleSheet(
            f"#emptyMsg {{ color: {c['text_secondary']};"
            f" font-size: {T.FONT['h2']}px; background: transparent; }}")
