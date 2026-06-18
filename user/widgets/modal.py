"""
modal.py — Markaziy modal oyna asosi (xira fon + panel).
Detal oynalari (video/kitob) shu asosdan foydalanadi. Ota-widget ustini
to'liq qoplaydi; tashqi xira joyga yoki X bosilsa yopiladi.
"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFrame,
                             QPushButton, QGraphicsOpacityEffect)
from PyQt6.QtCore import (Qt, pyqtSignal, QSize, QPropertyAnimation,
                          QEasingCurve)
from core import theme as T
from widgets.icons import svg_icon


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
        self.close_btn = QPushButton()
        self.close_btn.setObjectName("modalClose")
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setFixedSize(T.s(36), T.s(36))
        self.close_btn.setIconSize(QSize(T.s(18), T.s(18)))
        self.close_btn.clicked.connect(self.close_modal)
        top.addWidget(self.close_btn)
        self.body.addLayout(top)

        # Tarkib joyi
        self.content = QVBoxLayout()
        self.content.setContentsMargins(T.s(24), 0, T.s(24), T.s(24))
        self.body.addLayout(self.content, 1)

        outer.addWidget(self.panel)

    def show_over(self, name="light"):
        """Ota-widgetni to'liq qoplab ko'rsatadi (yumshoq fade bilan)."""
        self.theme_name = name
        self._restyle()
        if self.parent():
            self.setGeometry(self.parent().rect())
        self.show()
        self.raise_()
        # Fade-in (180ms). MUHIM: tugagach effekt olib tashlanadi — doimiy
        # opacity effekti butun modalni offscreen buferda chizdirib sekinlatadi.
        eff = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(eff)
        self._fade = QPropertyAnimation(eff, b"opacity", self)
        self._fade.setDuration(180)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade.finished.connect(self._end_fade)
        self._fade.start()

    def _end_fade(self):
        try:
            self.setGraphicsEffect(None)
        except RuntimeError:
            pass  # modal allaqachon yopilgan/o'chirilgan bo'lishi mumkin

    def close_modal(self):
        self.hide()
        self.closed.emit()
        self.deleteLater()

    def mousePressEvent(self, e):
        # Bosish ham panel tashqarisida boshlangani belgilab qo'yiladi —
        # panel ichidan boshlangan drag tashqarida tugasa modal yopilmasin.
        self._press_outside = not self.panel.geometry().contains(e.pos())

    def mouseReleaseEvent(self, e):
        # Faqat bosish HAM, qo'yib yuborish HAM panel tashqarisida bo'lsa yopiladi
        if (getattr(self, "_press_outside", False)
                and not self.panel.geometry().contains(e.pos())):
            self.close_modal()
        self._press_outside = False

    def _restyle(self):
        c = T.THEMES[self.theme_name]
        self.close_btn.setIcon(svg_icon("x", c["text"], T.s(36)))
        self.setStyleSheet(
            f"Modal {{ background: rgba(0,0,0,0.55); }}")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.panel.setStyleSheet(
            f"#modalPanel {{ background: {c['surface']};"
            f" border-radius: {T.RADIUS['card']}px; }}"
            f"#modalClose {{ background: {c['surface2']}; color: {c['text']};"
            f" border: none; border-radius: {T.s(18)}px; font-size: {T.s(18)}px; }}"
            f"#modalClose:hover {{ background: {c['border']}; }}"
            f"#modalClose:pressed {{ background: {c['text_secondary']}; }}")
