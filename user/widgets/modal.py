"""
modal.py — Markaziy modal oyna asosi (xira fon + panel).
Detal oynalari (video/kitob) shu asosdan foydalanadi. Ota-widget ustini
to'liq qoplaydi; tashqi xira joyga yoki X bosilsa yopiladi.
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFrame, QPushButton
from PyQt6.QtCore import Qt, pyqtSignal
import theme as T


class Modal(QWidget):
    closed = pyqtSignal()

    def __init__(self, parent, width=820, height=460):
        super().__init__(parent)
        self._pw, self._ph = width, height
        self.theme_name = "light"

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.panel = QFrame()
        self.panel.setObjectName("modalPanel")
        self.panel.setFixedSize(width, height)

        # Panel ichidagi tarkib (subklass to'ldiradi) + X tugma ustda
        self.body = QVBoxLayout(self.panel)
        self.body.setContentsMargins(0, 0, 0, 0)

        top = QHBoxLayout()
        top.setContentsMargins(0, T.s(8), T.s(8), 0)
        top.addStretch(1)
        self.close_btn = QPushButton("✕")
        self.close_btn.setObjectName("modalClose")
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setFixedSize(T.s(36), T.s(36))
        self.close_btn.clicked.connect(self.close_modal)
        top.addWidget(self.close_btn)
        self.body.addLayout(top)

        # Tarkib joyi
        self.content = QVBoxLayout()
        self.content.setContentsMargins(T.s(24), 0, T.s(24), T.s(24))
        self.body.addLayout(self.content, 1)

        outer.addWidget(self.panel)

    def show_over(self, name="light"):
        """Ota-widgetni to'liq qoplab ko'rsatadi."""
        self.theme_name = name
        self._restyle()
        if self.parent():
            self.setGeometry(self.parent().rect())
        self.show()
        self.raise_()

    def close_modal(self):
        self.hide()
        self.closed.emit()
        self.deleteLater()

    def mouseReleaseEvent(self, e):
        # Panel tashqarisiga bosilsa yopiladi
        if not self.panel.geometry().contains(e.pos()):
            self.close_modal()

    def _restyle(self):
        c = T.THEMES[self.theme_name]
        self.setStyleSheet(
            f"Modal {{ background: rgba(0,0,0,0.55); }}")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.panel.setStyleSheet(
            f"#modalPanel {{ background: {c['surface']};"
            f" border-radius: {T.RADIUS['card']}px; }}"
            f"#modalClose {{ background: {c['surface2']}; color: {c['text']};"
            f" border: none; border-radius: {T.s(18)}px; font-size: {T.s(18)}px; }}"
            f"#modalClose:hover {{ background: {c['border']}; }}")
