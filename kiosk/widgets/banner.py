"""
banner.py — E'lon banneri (admin yuborgan announcement, main.py dan ajratilgan).

Oyna tepasida ustki qatlam bo'lib chiqadi: ikonka + matn (emoji o'rniga
haqiqiy ikonka, assets/icons/megaphone.svg), 10 soniyadan keyin o'zi yopiladi.
MainWindow faqat show_message() / reposition() / apply_theme() ni chaqiradi.
"""
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel

from core import theme as T
from widgets.icons import svg_pixmap


class AnnouncementBanner(QFrame):
    """Admin e'lonini ko'rsatadigan ustki banner (parent oyna kengligida)."""

    SHOW_MS = 10000   # e'lon shu vaqtcha ko'rinadi

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("banner")
        bl = QHBoxLayout(self)
        bl.setContentsMargins(T.s(20), T.s(14), T.s(20), T.s(14))
        bl.setSpacing(T.s(12))
        bl.addStretch(1)
        self._ic = QLabel()
        self._ic.setStyleSheet("background: transparent;")
        bl.addWidget(self._ic, 0, Qt.AlignmentFlag.AlignVCenter)
        self._lbl = QLabel("")
        self._lbl.setObjectName("bannerTxt")
        self._lbl.setWordWrap(True)
        bl.addWidget(self._lbl, 0, Qt.AlignmentFlag.AlignVCenter)
        bl.addStretch(1)
        self.hide()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def show_message(self, text):
        """Admin yuborgan e'lonni ustki bannerda ko'rsatadi (10 soniya)."""
        if not text:
            return
        self._lbl.setText(text)
        self.show()
        self.raise_()
        self.reposition()
        self._timer.start(self.SHOW_MS)

    def reposition(self):
        """Bannerni parent oyna kengligiga moslab tepaga joylaydi
        (MainWindow.resizeEvent har o'lcham o'zgarishida chaqiradi)."""
        w = self.parentWidget().width()
        self.setFixedWidth(w)
        self.adjustSize()
        self.move(0, 0)
        self.setFixedWidth(w)

    def apply_theme(self, c):
        """Mavzu ranglarini qo'llaydi (c — T.THEMES[...] lug'ati)."""
        self.setStyleSheet(
            f"#banner {{ background: {c['accent']}; }}"
            f"#bannerTxt {{ background: transparent; color: {c['accent_text']};"
            f" font-size: {T.FONT['nav']}px; font-weight: 600; }}")
        self._ic.setPixmap(
            svg_pixmap("megaphone", c["accent_text"], T.s(26)))
