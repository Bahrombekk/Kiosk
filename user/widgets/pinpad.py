"""
pinpad.py — Maxfiy texnik chiqish uchun sensorbop PIN klaviatura.

Kiosk qulflangan (klaviatura/sichqonsiz sensorli ekran) holatda ham admin
dasturdan chiqa olishi uchun: ekran yuqori-o'ng burchagiga 7 marta tez-tez
tegilsa shu dialog ochiladi. To'g'ri PIN -> accept(), dastur yopiladi.

Xavfsizlik: 5 marta noto'g'ri urinishdan keyin dialog yopiladi; 30 soniya
harakatsizlikdan keyin ham o'zi yopiladi (yo'lovchi tasodifan ochib qo'ysa).
"""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QLabel, QPushButton, QFrame)
from PyQt6.QtCore import Qt, QTimer, QSize
import theme as T
from widgets.icons import svg_icon

MAX_ATTEMPTS = 5
IDLE_CLOSE_MS = 30_000


class PinDialog(QDialog):
    def __init__(self, parent, pin, theme="light"):
        super().__init__(parent)
        self._pin = str(pin)
        self._entered = ""
        self._attempts = 0
        self.c = T.THEMES[theme]

        # Video pleyer (StaysOnTop) ustida ham ko'rinishi uchun
        self.setWindowFlags(Qt.WindowType.Dialog
                            | Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setModal(True)

        self._idle = QTimer(self)
        self._idle.setSingleShot(True)
        self._idle.timeout.connect(self.reject)
        self._idle.start(IDLE_CLOSE_MS)

        self._build()

    def _build(self):
        c = self.c
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        panel = QFrame()
        panel.setObjectName("pinPanel")
        panel.setStyleSheet(
            f"#pinPanel {{ background: {c['surface']};"
            f" border: 1px solid {c['border']};"
            f" border-radius: {T.s(24)}px; }}")
        outer.addWidget(panel)

        lay = QVBoxLayout(panel)
        m = T.s(28)
        lay.setContentsMargins(m, m, m, m)
        lay.setSpacing(T.s(14))

        title = QLabel("Texnik chiqish")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {c['text']}; font-size: {T.s(22)}px;"
                            f" font-weight: 700; background: transparent;")
        lay.addWidget(title)

        # Kiritilgan raqamlar (nuqtalar bilan maskalangan)
        self.dots = QLabel("")
        self.dots.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dots.setFixedHeight(T.s(44))
        self.dots.setStyleSheet(
            f"color: {c['text']}; font-size: {T.s(30)}px; letter-spacing: {T.s(8)}px;"
            f" background: {c['surface2']}; border-radius: {T.s(12)}px;")
        lay.addWidget(self.dots)

        self.err = QLabel(" ")
        self.err.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.err.setStyleSheet(f"color: #EF4444; font-size: {T.s(15)}px;"
                               f" font-weight: 600; background: transparent;")
        lay.addWidget(self.err)

        # Raqamli klaviatura: 1-9, keyin [o'chirish] 0 [OK]
        grid = QGridLayout()
        grid.setSpacing(T.s(10))
        for i, d in enumerate("123456789"):
            grid.addWidget(self._key(d, lambda _c, x=d: self._digit(x)),
                           i // 3, i % 3)
        back = self._key("", self._backspace)
        back.setIcon(svg_icon("x", c["text"], 48))
        back.setIconSize(QSize(T.s(24), T.s(24)))
        ok = self._key("OK", self._check, accent=True)
        grid.addWidget(back, 3, 0)
        grid.addWidget(self._key("0", lambda: self._digit("0")), 3, 1)
        grid.addWidget(ok, 3, 2)
        lay.addLayout(grid)

        cancel = QPushButton("Bekor qilish")
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.setFixedHeight(T.s(46))
        cancel.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {c['text_secondary']};"
            f" border: none; font-size: {T.s(16)}px; font-weight: 600; }}"
            f"QPushButton:hover {{ color: {c['text']}; }}")
        cancel.clicked.connect(self.reject)
        lay.addWidget(cancel)

    def _key(self, text, slot, accent=False):
        b = QPushButton(text)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        s = T.s(76)
        b.setFixedSize(s, s)
        c = self.c
        bg = c["accent"] if accent else c["surface2"]
        fg = c["accent_text"] if accent else c["text"]
        b.setStyleSheet(
            f"QPushButton {{ background: {bg}; color: {fg}; border: none;"
            f" border-radius: {s // 2}px; font-size: {T.s(24)}px;"
            f" font-weight: 700; }}"
            f"QPushButton:pressed {{ background: {c['accent']};"
            f" color: {c['accent_text']}; }}")
        b.clicked.connect(slot)
        return b

    # --- Kiritish ---
    def _touch(self):
        self._idle.start(IDLE_CLOSE_MS)  # har harakatda taymerni qayta boshlaymiz

    def _digit(self, d):
        self._touch()
        if len(self._entered) < 8:
            self._entered += d
            self._refresh()

    def _backspace(self, *_):
        self._touch()
        self._entered = self._entered[:-1]
        self._refresh()

    def _refresh(self):
        self.dots.setText("●" * len(self._entered))
        self.err.setText(" ")

    def _check(self, *_):
        self._touch()
        if self._entered == self._pin:
            self.accept()
            return
        self._attempts += 1
        self._entered = ""
        self.dots.setText("")
        if self._attempts >= MAX_ATTEMPTS:
            self.reject()
            return
        self.err.setText(
            f"Noto'g'ri PIN ({MAX_ATTEMPTS - self._attempts} urinish qoldi)")

    # Klaviatura ulangan bo'lsa, undan ham kiritish mumkin
    def keyPressEvent(self, e):
        k = e.key()
        if Qt.Key.Key_0 <= k <= Qt.Key.Key_9:
            self._digit(chr(k))
        elif k == Qt.Key.Key_Backspace:
            self._backspace()
        elif k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._check()
        elif k == Qt.Key.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(e)
