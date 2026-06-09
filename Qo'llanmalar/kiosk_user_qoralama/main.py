"""
main.py — Foydalanuvchi (kiosk) ilovasining kirish nuqtasi.
Vazifasi (3-bosqich poydevori):
  - to'liq ekran, ramkasiz, doim ustda (kiosk)
  - chiqib bo'lmaydi (Esc/Alt+F4 bloklangan)
  - yuqorida Figma'dagi navigatsiya paneli + soat
  - 5 ta bo'lim sahifasi (hozircha placeholder, keyin haqiqiy ekranlar qo'shiladi)

Ishga tushirish:
  pip install PyQt6
  python main.py

Sinov tugmalari (faqat ishlab chiqishda):
  Ctrl+T          — Light/Dark almashtirish (Figma bilan solishtirish uchun)
  Ctrl+Shift+Q    — admin chiqishi (kiosk'dan chiqish)
"""
import sys
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QStackedWidget,
                             QLabel)
from PyQt6.QtCore import Qt, QTimer
import theme as T
from widgets.navbar import NavBar


def placeholder(title):
    """Vaqtinchalik bo'lim sahifasi (keyin haqiqiy ekran bilan almashtiriladi)."""
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl = QLabel(title)
    lbl.setObjectName("ph")
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lay.addWidget(lbl)
    return w, lbl


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.theme_name = "light"

        # --- Kiosk: ramkasiz, ustda ---
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Navigatsiya
        self.nav = NavBar()
        self.nav.navigate.connect(self.go)
        root.addWidget(self.nav)

        # Bo'limlar
        self.stack = QStackedWidget()
        self.pages = {}
        self.ph_labels = []
        for key, label, _icon, _title in T.NAV_ITEMS:
            page, lbl = placeholder(f"«{label}» bo'limi\n(bu yerga haqiqiy ekran qo'shiladi)")
            self.pages[key] = page
            self.ph_labels.append(lbl)
            self.stack.addWidget(page)
        root.addWidget(self.stack, 1)

        # Soat har soniyada yangilanadi
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(1000)
        self._tick()

        self.apply_theme()
        self.go("home")

    def go(self, key):
        self.stack.setCurrentWidget(self.pages[key])
        self.nav.set_active(key)
        self._tick()

    def _tick(self):
        self.nav.set_clock(datetime.now().strftime("%H:%M"))

    def apply_theme(self):
        c = T.THEMES[self.theme_name]
        self.setStyleSheet(
            f"QWidget {{ background: {c['bg']}; font-family: {T.FONT_FAMILY}; }}"
            f"#ph {{ color: {c['text_secondary']}; font-size: {T.FONT['h2']}px; }}"
        )
        self.nav.apply_theme(self.theme_name)

    # --- Tugmalarni boshqarish (kiosk qulflash) ---
    def keyPressEvent(self, e):
        # Esc ni e'tiborsiz qoldiramiz (chiqib ketmasin)
        if e.key() == Qt.Key.Key_Escape:
            return
        # Ctrl+T -> mavzu almashtirish (sinov)
        if e.key() == Qt.Key.Key_T and (e.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self.theme_name = "dark" if self.theme_name == "light" else "light"
            self.apply_theme()
            return
        # Ctrl+Shift+Q -> admin chiqishi
        if (e.key() == Qt.Key.Key_Q
                and (e.modifiers() & Qt.KeyboardModifier.ControlModifier)
                and (e.modifiers() & Qt.KeyboardModifier.ShiftModifier)):
            QApplication.quit()
            return
        super().keyPressEvent(e)

    def closeEvent(self, e):
        # Alt+F4 / yopishni bloklash (faqat admin chiqishi orqali yopiladi)
        e.ignore()


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.showFullScreen()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
