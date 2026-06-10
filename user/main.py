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

# --- O'rnatilgan (PyInstaller) nusxada birga keladigan VLC'ni ulaymiz ---
# MUHIM: `player` (import vlc) yuklanishidan OLDIN bo'lishi shart. VLC
# o'rnatilmagan kompyuterda ham video ishlashi uchun libvlc dasturga qo'shib
# beriladi (_internal/vlc), python-vlc'ga yo'lini env orqali ko'rsatamiz.
if getattr(sys, "frozen", False):
    _vlc_dir = os.path.join(getattr(sys, "_MEIPASS",
                            os.path.dirname(os.path.abspath(__file__))), "vlc")
    if os.path.isdir(_vlc_dir):
        os.environ.setdefault("PYTHON_VLC_LIB_PATH",
                              os.path.join(_vlc_dir, "libvlc.dll"))
        os.environ.setdefault("VLC_PLUGIN_PATH",
                              os.path.join(_vlc_dir, "plugins"))
        os.add_dll_directory(_vlc_dir)

from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QStackedWidget,
                             QLabel, QFrame, QHBoxLayout)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QEvent, QPoint, QRect
from PyQt6.QtGui import QPixmap, QPainter, QColor, QIcon

import config
import theme as T
from threads import track
from api import ApiClient
from ws_client import WSClient
from widgets.navbar import NavBar
from widgets.icons import svg_pixmap
from widgets.screensaver import ScreenSaver
from player import VideoPlayer
from audio_player import AudioPlayer
from reader import Reader
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

        # KIOSK REJIM: ramkasiz, doim ustda, yopib bo'lmaydi (TZ 13.1).
        # Chiqish faqat: soatga 7 marta teginish -> PIN, yoki Ctrl+Shift+Q.
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setWindowTitle("Kiosk")
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

        # E'lon banneri (announcement uchun) — ustki qatlam.
        # Ikonka + matn (emoji o'rniga haqiqiy ikonka, assets/icons/megaphone.svg)
        self.banner = QFrame(self)
        self.banner.setObjectName("banner")
        bl = QHBoxLayout(self.banner)
        bl.setContentsMargins(T.s(20), T.s(14), T.s(20), T.s(14))
        bl.setSpacing(T.s(12))
        bl.addStretch(1)
        self.banner_ic = QLabel()
        self.banner_ic.setStyleSheet("background: transparent;")
        bl.addWidget(self.banner_ic, 0, Qt.AlignmentFlag.AlignVCenter)
        self.banner_lbl = QLabel("")
        self.banner_lbl.setObjectName("bannerTxt")
        self.banner_lbl.setWordWrap(True)
        bl.addWidget(self.banner_lbl, 0, Qt.AlignmentFlag.AlignVCenter)
        bl.addStretch(1)
        self.banner.hide()
        self.banner_timer = QTimer(self)
        self.banner_timer.setSingleShot(True)
        self.banner_timer.timeout.connect(self.banner.hide)

        # WebSocket real-time (TZ 11.2): status va e'lonlarni tinglaydi
        self.ws = track(WSClient())
        self.ws.status.connect(self._on_status)
        self.ws.announcement.connect(self.show_announcement)
        self.ws.start()

        # Maxfiy texnik chiqish: yuqori-o'ng burchakka EXIT_TAPS marta teginish
        # PIN klaviaturani ochadi (sensorli, klaviaturasiz ekranlar uchun ham).
        # Filtr QApplication'ga o'rnatiladi — bosish qaysi vidjetga tushsa ham ko'ramiz.
        self._exit_taps = []
        self._pin_open = False
        self._allow_exit = False   # faqat PIN/admin chiqishi True qiladi
        QApplication.instance().installEventFilter(self)

        # Zastavka (splash + screensaver): logotipli to'liq ekran overlay.
        # Harakatsizlik taymeri har qanday teginishda qayta boshlanadi
        # (event filtrda); vaqti kelganda zastavka chiqadi.
        self.saver = ScreenSaver()
        self.idle_timer = QTimer(self)
        self.idle_timer.setSingleShot(True)
        self.idle_timer.setInterval(config.SCREENSAVER_IDLE_MIN * 60_000)
        self.idle_timer.timeout.connect(self._maybe_screensaver)

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
        self.banner_lbl.setText(text)
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
        # Zastavka mustaqil top-level oyna (o'z ekraniga to'liq cho'ziladi) —
        # bu yerda boshqarish shart emas.
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
                f"#banner {{ background: {c['accent']}; }}"
                f"#bannerTxt {{ background: transparent; color: {c['accent_text']};"
                f" font-size: {T.FONT['nav']}px; font-weight: 600; }}")
            self.banner_ic.setPixmap(
                svg_pixmap("megaphone", c["accent_text"], T.s(26)))

    # --- Global kirish filtri: maxfiy chiqish + zastavka boshqaruvi ---
    _ACTIVITY = (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease,
                 QEvent.Type.MouseMove, QEvent.Type.KeyPress,
                 QEvent.Type.Wheel, QEvent.Type.TouchBegin)

    def eventFilter(self, obj, ev):
        t = ev.type()
        if t in self._ACTIVITY:
            if self.saver.isVisible():
                # Zastavka ochiq: birinchi teginish/bosish uni yopadi, voqea
                # YUTILADI (ostidagi tugmaga tasodifan tegib ketmasin).
                if t in (QEvent.Type.MouseButtonPress, QEvent.Type.KeyPress,
                         QEvent.Type.TouchBegin):
                    self._dismiss_saver()
                    return True
                if t == QEvent.Type.MouseButtonRelease:
                    return True   # yutilgan bosishning juft release'i
            else:
                self.idle_timer.start()   # har harakatda hisob qaytadan
                if t == QEvent.Type.MouseButtonPress:
                    try:
                        self._register_secret_tap(ev.globalPosition().toPoint())
                    except Exception:
                        pass  # chiqish mexanizmi hech qachon ilovani yiqitmasin
        return super().eventFilter(obj, ev)

    # --- Zastavka (screensaver) ---
    def _media_open(self):
        """Video/audio pleyer yoki kitob o'quvchi ochiqmi? (tomosha/tinglash/
        o'qish payti zastavka chiqmasligi kerak)."""
        return any(isinstance(w, (VideoPlayer, AudioPlayer, Reader))
                   and w.isVisible()
                   for w in QApplication.topLevelWidgets())

    def start_splash(self):
        """Ochilish splash'i — main oyna ko'rsatilgandan KEYIN chaqiriladi
        (aks holda fullscreen main oyna uni berkitib qo'yadi)."""
        self.saver.show_over()
        QTimer.singleShot(config.SPLASH_SECONDS * 1000, self._dismiss_saver)
        self.idle_timer.start()

    def _maybe_screensaver(self):
        if self._media_open() or self._pin_open:
            self.idle_timer.start()   # band — keyinroq yana tekshiramiz
            return
        self.saver.show_over()

    def _dismiss_saver(self):
        self.saver.hide()
        self.idle_timer.start()

    def _register_secret_tap(self, gpos):
        """Navbar'dagi SOAT ustiga ketma-ket teginishlarni sanaydi.

        Soat ko'rinmasa (masalan, 'ulanmoqda' ekrani) — zaxira sifatida ekran
        yuqori-o'ng burchagi ishlaydi (server o'chiq bo'lsa ham chiqib bo'lsin)."""
        import time as _time
        lbl = self.nav.right
        if lbl.isVisible() and lbl.width() > 0:
            # Soat yorlig'ining global to'rtburchagi + barmoq uchun qo'shimcha joy
            pad = T.s(18)
            zone = QRect(lbl.mapToGlobal(QPoint(0, 0)), lbl.size())
            zone = zone.adjusted(-pad, -pad, pad, pad)
            in_zone = zone.contains(gpos)
        else:
            g = (self.screen() or QApplication.primaryScreen()).geometry()
            size = T.s(config.EXIT_CORNER_PX)
            in_zone = (gpos.x() >= g.right() - size and gpos.y() <= g.top() + size)
        if not in_zone:
            self._exit_taps.clear()   # boshqa joyga tegilsa hisob qaytadan
            return
        now = _time.monotonic()
        # Bitta fizik bosish filtrga ikki marta kelishi mumkin (QWindow + widget)
        # — 50ms ichidagi takrorni bitta teginish deb hisoblaymiz.
        if self._exit_taps and now - self._exit_taps[-1] < 0.05:
            return
        self._exit_taps.append(now)
        self._exit_taps = [t for t in self._exit_taps
                           if now - t <= config.EXIT_TAP_WINDOW_S]
        if len(self._exit_taps) >= config.EXIT_TAPS:
            self._exit_taps.clear()
            self._ask_exit_pin()

    def _ask_exit_pin(self):
        if self._pin_open:
            return
        self._pin_open = True
        try:
            from widgets.pinpad import PinDialog
            dlg = PinDialog(self, config.EXIT_PIN, theme=self.theme_name)
            ok = dlg.exec()
        finally:
            self._pin_open = False
        if ok:
            self._exit_app()

    def _exit_app(self):
        """Yagona chiqish nuqtasi: fon oqimlarini to'xtatib, ilovani yopadi."""
        self._allow_exit = True
        self._shutdown()
        QApplication.quit()

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
            self._exit_app()
            return
        super().keyPressEvent(e)

    def _shutdown(self):
        """Barcha fon oqimlarini xavfsiz to'xtatadi (Qt 'thread still running' bo'lmasin)."""
        import threads
        self.ws.stop()
        # Yangi fon ishi paydo bo'lmasin — sahifalardagi taymerlarni to'xtatamiz
        for p in self.pages.values():
            canvas = getattr(p, "canvas", p)
            t = getattr(canvas, "timer", None)
            if t is not None:
                t.stop()
        # Kuzatilayotgan barcha worker'lar (loader/fetcher/ws) tugashini kutamiz.
        # gc.get_objects() bo'ylab yurish o'rniga aniq registr (faqat o'zimizniki).
        threads.wait_all(2000)

    def closeEvent(self, e):
        # KIOSK: tashqi yopish urinishlari bloklanadi (Alt+F4 va h.k.).
        # Faqat maxfiy PIN / Ctrl+Shift+Q chiqishi (_allow_exit) ruxsat etiladi.
        if not self._allow_exit:
            e.ignore()
            return
        self._shutdown()
        e.accept()


def main():
    try:
        app = QApplication(sys.argv)
        ico = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "assets", "design", "app.ico")
        if os.path.exists(ico):
            app.setWindowIcon(QIcon(ico))
        # Monitor o'lchamiga qarab global UI miqyosini o'rnatamiz (kichik/katta
        # ekranga moslashish). MUHIM: oyna qurilmasdan OLDIN.
        screen = app.primaryScreen()
        if screen is not None:
            T.init_scale(screen.size())
        win = MainWindow()
        win.showFullScreen()  # KIOSK: butun ekran
        win.start_splash()     # logotipli splash (fullscreen'dan keyin)
        sys.exit(app.exec())
    except Exception:
        # Yaratish paytidagi istisnoni ham yozamiz (excepthook ba'zan kech ulanadi)
        _excepthook(*sys.exc_info())
        raise


if __name__ == "__main__":
    main()
