"""
main.py — Foydalanuvchi (kiosk) ilovasining kirish nuqtasi (3-bosqich poydevori).

Vazifasi:
  - to'liq ekran, ramkasiz, doim ustda (kiosk rejim — TZ 13.1)
  - chiqib bo'lmaydi (Esc/Alt+F4/o'ng tugma bloklangan)
  - serverga ulanadi; ulanmasa "Serverga ulanmoqda..." ekrani (TZ FR-GEN-06)
  - yuqorida navigatsiya paneli + soat, 5 ta bo'lim sahifasi (QStackedWidget)

Ishga tushirish:
  pip install -r requirements.txt
  python main.py

Sinov tugmalari (faqat ishlab chiqishda):
  Ctrl+T          — Light/Dark almashtirish (Figma bilan solishtirish uchun)
  Ctrl+Shift+Q    — admin chiqishi (kiosk'dan chiqish)
  Ctrl+Shift+C    — admin chiqishi (kiosk'dan chiqish)
"""
import sys
import os
import faulthandler
import traceback
from datetime import datetime

# --- Crash'ni ko'rinadigan qilish (TZ debug) ---
# Muammo: ilova "o'zidan o'zi" yopilib, xatoni ko'rsatmasdi. PyQt6'da Qt
# hodisasi (paintEvent/slot) ichidagi ushlanmagan istisno yoki C++ darajasidagi
# nosozlik konsolga hech narsa chiqarmasdan jarayonni tugatishi mumkin.
# Quyidagi blok HAR QANDAY crash'ni `crash.log` fayliga va konsolga yozadi.
_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crash.log")
_logf = open(_LOG, "a", encoding="utf-8")
faulthandler.enable(file=_logf, all_threads=True)   # native crash (segfault) dump


def _excepthook(exc_type, exc, tb):
    """Ushlanmagan Python istisnolarini yozadi (PyQt jim yopib yubormasin)."""
    text = "".join(traceback.format_exception(exc_type, exc, tb))
    _logf.write("\n===== CRASH =====\n" + text)
    _logf.flush()
    sys.stderr.write(text)
    sys.stderr.flush()


sys.excepthook = _excepthook

from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QStackedWidget,
                             QLabel)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap, QPainter, QColor

import config
import theme as T
from threads import track
from api import ApiClient
from ws_client import WSClient
from widgets.navbar import NavBar
from screens.connecting import ConnectingScreen
from screens.home import HomeScreen
from screens.map import MapScreen
from screens.videos import VideosScreen
from screens.books import BooksScreen
from screens.sites import SitesScreen


class HealthChecker(QThread):
    """Serverga ulanishni alohida oqimda tekshiradi (UI qotib qolmasligi uchun)."""
    result = pyqtSignal(bool)

    def __init__(self, api):
        super().__init__()
        self.api = api

    def run(self):
        self.result.emit(self.api.health())


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.theme_name = config.DEFAULT_THEME
        self.connected = False
        self.api = ApiClient()
        self._checker = None
        # Butun oynani qoplaydigan orqa fon (atlas/satin tekstura) — paintEvent'da
        # chiziladi, shunda har bir ekranda (xarita ham) bir xil fon ko'rinadi.
        self._bg = QPixmap(T.BG_IMAGE)

        # --- VAQTINCHALIK: oddiy oyna ramkasi (—, □, ✕ tugmalari) bilan ---
        # Kiosk rejimdan chiqa olish uchun frameless va StaysOnTop o'chirildi.
        # Ishlab chiqishdan keyin pastdagi kiosk satrini qaytaring.
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setWindowTitle("Kiosk (vaqtinchalik chiqish rejimi)")
        # --- ASL KIOSK SATRI (vaqtinchalik o'chirilgan): ---
        # self.setWindowFlags(
        #     Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        # )
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)  # o'ng tugma o'chirildi

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Tashqi stack: [ulanish ekrani] <-> [asosiy ilova]
        self.outer = QStackedWidget()
        root.addWidget(self.outer)

        # 1) Ulanish ekrani
        self.connecting = ConnectingScreen()
        self.outer.addWidget(self.connecting)

        # 2) Asosiy ilova (navbar + bo'limlar)
        self.app = QWidget()
        app_lay = QVBoxLayout(self.app)
        app_lay.setContentsMargins(0, 0, 0, 0)
        app_lay.setSpacing(0)

        self.nav = NavBar()
        self.nav.navigate.connect(self.go)
        app_lay.addWidget(self.nav)

        self.stack = QStackedWidget()
        self.pages = {
            "home":   HomeScreen(self.api, self),
            "map":    MapScreen(self.api),
            "videos": VideosScreen(self.api),
            "books":  BooksScreen(self.api),
            "sites":  SitesScreen(self.api),
        }
        for page in self.pages.values():
            self.stack.addWidget(page)
        app_lay.addWidget(self.stack, 1)
        self.outer.addWidget(self.app)

        # Soat har soniyada yangilanadi
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._tick)
        self.clock_timer.start(1000)
        self._tick()

        # Ulanishni davriy tekshirish (TZ 12.2 — har 5 soniyada)
        self.conn_timer = QTimer(self)
        self.conn_timer.timeout.connect(self.check_connection)
        self.conn_timer.start(config.RECONNECT_INTERVAL_MS)

        # E'lon banneri (announcement uchun) — ustki qatlam
        self.banner = QLabel("", self)
        self.banner.setObjectName("banner")
        self.banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.banner.setWordWrap(True)
        self.banner.hide()
        self.banner_timer = QTimer(self)
        self.banner_timer.setSingleShot(True)
        self.banner_timer.timeout.connect(self.banner.hide)

        # WebSocket real-time (TZ 11.2): status va e'lonlarni tinglaydi
        self.ws = track(WSClient())
        self.ws.status.connect(self._on_status)
        self.ws.announcement.connect(self.show_announcement)
        self.ws.start()

        self.apply_theme()
        self.outer.setCurrentWidget(self.connecting)
        self.go("home")
        self.check_connection()  # darhol birinchi tekshiruv

    # --- Ulanish boshqaruvi ---
    def check_connection(self):
        if self._checker and self._checker.isRunning():
            return  # oldingi tekshiruv hali tugamagan
        self._checker = track(HealthChecker(self.api))
        self._checker.result.connect(self._on_health)
        self._checker.start()

    def _on_health(self, ok):
        was = self.connected
        self.connected = ok
        if ok:
            self.outer.setCurrentWidget(self.app)
            if not was:
                self.go(self.nav.active)  # qayta ulanganda joriy sahifani yangilash
        else:
            self.connecting.set_status(
                "Serverga ulanib bo'lmadi, qayta urinilmoqda...")
            self.outer.setCurrentWidget(self.connecting)

    # --- Real-time (WebSocket) ---
    def _on_status(self, data):
        """Serverdan status_update kelganda Asosiy ekranni jonli yangilaydi."""
        self.pages["home"]._apply_status(data)

    def show_announcement(self, text):
        """Admin yuborgan e'lonni ustki bannerda ko'rsatadi (10 soniya)."""
        if not text:
            return
        self.banner.setText("📢  " + text)
        self.banner.show()
        self.banner.raise_()
        self._place_banner()
        self.banner_timer.start(10000)

    def _place_banner(self):
        self.banner.setFixedWidth(self.width())
        self.banner.adjustSize()
        self.banner.move(0, 0)
        self.banner.setFixedWidth(self.width())

    def paintEvent(self, e):
        """Butun oynani orqa fon rasmi bilan qoplaydi (nisbatni saqlab, kesib
        to'ldiradi — cover). Light mavzuda satin rasm, dark mavzuda tekis rang."""
        p = QPainter(self)
        if self.theme_name == "light" and not self._bg.isNull():
            scaled = self._bg.scaled(
                self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation)
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            p.drawPixmap(x, y, scaled)
        else:
            p.fillRect(self.rect(), QColor(T.THEMES[self.theme_name]["bg"]))
        super().paintEvent(e)

    def resizeEvent(self, e):
        if hasattr(self, "banner"):
            self._place_banner()
        super().resizeEvent(e)

    # --- Navigatsiya ---
    def go(self, key):
        page = self.pages[key]
        self.stack.setCurrentWidget(page)
        self.nav.set_active(key)
        page.on_show()
        self._tick()

    def _tick(self):
        self.nav.set_clock(datetime.now().strftime("%H:%M"))

    # --- Mavzu ---
    def apply_theme(self):
        c = T.THEMES[self.theme_name]
        self.setObjectName("mainWin")
        # Oyna foni paintEvent'da satin rasm bilan butun oynaga chiziladi.
        # MUHIM: #mainWin va bolalarga `background` BERMAYMIZ — ular shaffof bo'lib
        # tursin, shunda paintEvent chizgan fon ular ortidan ko'rinadi. Faqat shrift.
        self.setStyleSheet(
            f"QWidget {{ font-family: {T.FONT_FAMILY}; }}"
            + f"QLabel {{ background: transparent; }}")
        self.update()  # fon qayta chizilsin (mavzu almashganda)
        self.connecting.apply_theme(self.theme_name)
        self.nav.apply_theme(self.theme_name)
        for page in self.pages.values():
            page.apply_theme(self.theme_name)
        if hasattr(self, "banner"):
            self.banner.setStyleSheet(
                f"#banner {{ background: {c['accent']}; color: {c['accent_text']};"
                f" font-size: {T.FONT['nav']}px; font-weight: 600; padding: 14px; }}")

    # --- Tugmalarni boshqarish (kiosk qulflash, TZ 13.1) ---
    def keyPressEvent(self, e):
        # Esc ni e'tiborsiz qoldiramiz (chiqib ketmasin)
        if e.key() == Qt.Key.Key_Escape:
            return
        # Ctrl+T -> mavzu almashtirish (sinov)
        if e.key() == Qt.Key.Key_T and (e.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self.theme_name = "dark" if self.theme_name == "light" else "light"
            self.apply_theme()
            return
        # Ctrl+Shift+Q yoki Ctrl+Shift+C -> admin chiqishi
        if (e.key() in (Qt.Key.Key_Q, Qt.Key.Key_C)
                and (e.modifiers() & Qt.KeyboardModifier.ControlModifier)
                and (e.modifiers() & Qt.KeyboardModifier.ShiftModifier)):
            self._shutdown()
            QApplication.quit()
            return
        super().keyPressEvent(e)

    def _shutdown(self):
        """Barcha fon oqimlarini xavfsiz to'xtatadi (Qt 'thread still running' bo'lmasin)."""
        import gc
        self.ws.stop()
        # Yangi fon ishi paydo bo'lmasin — sahifalardagi taymerlarni to'xtatamiz
        for p in self.pages.values():
            canvas = getattr(p, "canvas", p)
            t = getattr(canvas, "timer", None)
            if t is not None:
                t.stop()
        # Hozir ishlayotgan barcha QThread'lar (loader/fetcher/ws) tugashini kutamiz
        cur = QThread.currentThread()
        for obj in gc.get_objects():
            try:
                if isinstance(obj, QThread) and obj is not cur and obj.isRunning():
                    if not obj.wait(2000):
                        obj.terminate()
                        obj.wait(500)
            except RuntimeError:
                pass   # C++ obyekti allaqachon o'chirilgan — e'tiborsiz

    def closeEvent(self, e):
        # VAQTINCHALIK: ✕ tugmasi bilan yopilishga ruxsat berildi.
        # ASL (kiosk) xatti-harakati: e.ignore()  — yopishni bloklash
        self._shutdown()
        e.accept()


def main():
    try:
        app = QApplication(sys.argv)
        # Monitor o'lchamiga qarab global UI miqyosini o'rnatamiz (kichik/katta
        # ekranga moslashish). MUHIM: oyna qurilmasdan OLDIN.
        screen = app.primaryScreen()
        if screen is not None:
            T.init_scale(screen.size())
        win = MainWindow()
        win.showMaximized()  # VAQTINCHALIK: to'liq ekran o'rniga (ASL: win.showFullScreen())
        sys.exit(app.exec())
    except Exception:
        # Yaratish paytidagi istisnoni ham yozamiz (excepthook ba'zan kech ulanadi)
        _excepthook(*sys.exc_info())
        raise


if __name__ == "__main__":
    main()
