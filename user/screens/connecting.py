"""
connecting.py — Boshlang'ich / ulanish ekrani (Splash, TZ 8.1).

Server bilan ulanish o'rnatilgunча ko'rsatiladi. Ulanish bo'lmasa
"Serverga ulanib bo'lmadi, qayta urinilmoqda..." xabari (TZ FR-GEN-06).
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
from core import theme as T
from core.i18n import tr
from widgets.spinner import Spinner


class ConnectingScreen(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(14)

        self.logo = QLabel("KIOSK")
        self.logo.setObjectName("splashLogo")
        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.status = QLabel(tr("conn.connecting"))
        self.status.setObjectName("splashStatus")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.spinner = Spinner(size=T.s(44), line=T.s(4))

        lay.addWidget(self.logo)
        lay.addWidget(self.status)
        lay.addSpacing(T.s(10))
        lay.addWidget(self.spinner, 0, Qt.AlignmentFlag.AlignHCenter)
        self.spinner.start()

    def set_status(self, text):
        self.status.setText(text)

    def apply_theme(self, name):
        c = T.THEMES[name]
        self.logo.setStyleSheet(
            f"#splashLogo {{ color: {c['accent']}; font-size: {T.s(64)}px;"
            f" font-weight: 800; letter-spacing: {T.s(4)}px; }}")
        self.status.setStyleSheet(
            f"#splashStatus {{ color: {c['text_secondary']};"
            f" font-size: {T.FONT['h2']}px; }}")
        self.spinner.apply_theme(name)
