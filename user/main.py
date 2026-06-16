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

Texnik tugmalar:
  Ctrl+Shift+Q    — admin chiqishi (PIN so'raladi)
  Ctrl+Shift+C    — admin chiqishi (PIN so'raladi)
"""
import sys
import os
import time
import faulthandler
import traceback
from datetime import datetime

# --- Crash'ni ko'rinadigan qilish (TZ debug) ---
# Muammo: ilova "o'zidan o'zi" yopilib, xatoni ko'rsatmasdi. PyQt6'da Qt
# hodisasi (paintEvent/slot) ichidagi ushlanmagan istisno yoki C++ darajasidagi
# nosozlik konsolga hech narsa chiqarmasdan jarayonni tugatishi mumkin.
# Quyidagi blok HAR QANDAY crash'ni `crash.log` fayliga va konsolga yozadi.
from core import logsetup

_LOG = os.path.join(logsetup.base_dir(), "crash.log")
# crash.log cheksiz o'smasin — 1MB dan oshsa eskisini chetga suramiz
try:
    if os.path.exists(_LOG) and os.path.getsize(_LOG) > 1_000_000:
        os.replace(_LOG, _LOG + ".1")
except OSError:
    pass
_logf = open(_LOG, "a", encoding="utf-8")
faulthandler.enable(file=_logf, all_threads=True)   # native crash (segfault) dump

logsetup.setup()


def _excepthook(exc_type, exc, tb):
    """Ushlanmagan Python istisnolarini yozadi (PyQt jim yopib yubormasin).

    Yozib bo'lgach jarayon ataylab 1-kod bilan tugatiladi (fail-fast):
    Qt sloti ichidagi xato ilovani "yarim o'lik" (qora ekran) holatda
    qoldirmasin — watchdog uni darhol qayta ko'taradi."""
    text = "".join(traceback.format_exception(exc_type, exc, tb))
    _logf.write("\n===== CRASH =====\n" + text)
    _logf.flush()
    sys.stderr.write(text)
    sys.stderr.flush()
    try:
        import logging
        logging.getLogger("crash").error("Ushlanmagan istisno:\n%s", text)
    except Exception:
        pass
    os._exit(1)


sys.excepthook = _excepthook

# --- O'rnatilgan (PyInstaller) nusxada birga keladigan VLC'ni ulaymiz ---
# MUHIM: `players.video` (import vlc) yuklanishidan OLDIN bo'lishi shart
# (python-vlc env'ni import paytida o'qiydi) — system/vlcsetup.py ga qarang.
from system.vlcsetup import setup_vlc

setup_vlc()

from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QStackedWidget
from PyQt6.QtCore import Qt, QTimer, QEvent
from PyQt6.QtGui import QPixmap, QPainter, QColor, QIcon

from core import cache
from core import config
from core import i18n
from core import theme as T
from core.security import ExitGuard
from core.threads import track
from services.api import ApiClient
from services.ads import AdManager
from services import stats
from services.health import HealthChecker, _SettingsPrefetch
from services.ws_client import WSClient
from widgets.banner import AnnouncementBanner
from widgets.emergency import sos_enabled
from widgets.navbar import NavBar
from widgets.screensaver import ScreenSaver
from players.video import VideoPlayer
from players.audio import AudioPlayer
from players.reader import Reader
from screens.connecting import ConnectingScreen
from screens.home import HomeScreen
from screens.map import MapScreen
from screens.videos import VideosScreen
from screens.books import BooksScreen
from screens.sites import SitesScreen


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

        # Ramkasiz, doim ustda (TZ 13.1) — VAQTINCHALIK: WINDOWED rejimda oddiy
        # ramkali oyna (min/max/close tugmalari), shunda chiqib-kirish oson.
        if not config.WINDOWED:
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
            self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)  # o'ng tugma o'chirildi
        self.setWindowTitle("Kiosk")

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
        self.nav.lang_changed.connect(self.set_language)
        self.nav.sos_clicked.connect(self._show_sos)
        self.nav.set_sos_visible(sos_enabled())   # admin o'chirgan bo'lsa yashirin
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

        # E'lon banneri (announcement uchun) — ustki qatlam (widgets/banner.py).
        self.banner = AnnouncementBanner(self)

        # WebSocket real-time (TZ 11.2): status va e'lonlarni tinglaydi
        self.ws = track(WSClient())
        self.ws.status.connect(self._on_status)
        self.ws.announcement.connect(self.show_announcement)
        self.ws.sync.connect(self._on_sync)
        self.ws.cache_clear.connect(self._on_cache_clear)
        self.ws.link.connect(self._on_ws_link)
        self.ws.start()

        # Maxfiy texnik chiqish: yuqori-o'ng burchakka EXIT_TAPS marta teginish
        # PIN klaviaturani ochadi (sensorli, klaviaturasiz ekranlar uchun ham).
        # Mantiq core/security.py (ExitGuard) ichida; filtr QApplication'ga
        # o'rnatiladi — bosish qaysi vidjetga tushsa ham ko'ramiz.
        self._exit_guard = ExitGuard(self, self._exit_app)
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

        # Qalqib chiquvchi reklamalar: qaysi bo'lim ochiq bo'lishidan qat'i
        # nazar global kadans bilan popup chiqaradi (services/ads.py).
        # last_activity — oxirgi teginish vaqti (eventFilter yangilaydi);
        # AdManager foydalanuvchi faol payt popup chiqarmaslik uchun o'qiydi.
        self.last_activity = time.monotonic()
        self.ad_manager = AdManager(self, self.api)
        self.ad_manager.start()

        # Foydalanish statistikasi: eventlar diskdagi navbatga yoziladi va
        # davriy ravishda serverga yuboriladi (oflaynda yig'ilib turadi).
        self.stats_service = stats.StatsService(self, self.api)
        self.stats_service.start()

        # Lokal media kesh: kontent fayllarini fonda diskka sinxlaydi
        # (xotirasi yetsa) — oflaynda ham ijro, serverga kam yuk.
        from services.media_cache import MediaCacheSync
        self.media_sync = track(MediaCacheSync(self.api))
        self.media_sync.start()

        self.apply_theme()
        self.outer.setCurrentWidget(self.connecting)
        self.go("home")
        self.check_connection()  # darhol birinchi tekshiruv

    @property
    def _pin_open(self):
        """PIN oynasi ochiqmi? (zastavka/til/reklama tekshiruvlari uchun —
        haqiqiy holat ExitGuard'da turadi)."""
        return self._exit_guard.pin_open

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
        # SOS ko'rinishi admin sozlamasidan (health tekshiruvi settings
        # keshini yangilab turadi — o'zgarish bir necha soniyada yetib keladi)
        self.nav.set_sos_visible(sos_enabled())
        if ok:
            self.nav.set_offline(False)
            self.outer.setCurrentWidget(self.app)
            if not was:
                self.go(self.nav.active)  # qayta ulanganda joriy sahifani yangilash
                # PIN xeshi va sozlamalar keshi yangilansin (fonda)
                track(_SettingsPrefetch(self.api)).start()
                self.media_sync.kick()    # media keshni darhol sinxlash
        elif cache.has_catalog():
            # OFLAYN REJIM: server o'chgan, lekin keshlangan katalog bor —
            # "ulanmoqda" ekraniga qaytarmaymiz, kiosk ishlashda davom etadi
            # (ro'yxat/kitoblar keshdan; faqat video striming ishlamaydi).
            self.nav.set_offline(True)
            self.outer.setCurrentWidget(self.app)
        else:
            # Birinchi ishga tushish (kesh yo'q) — ulanish ekrani
            self.connecting.set_status(i18n.tr("conn.retry"))
            self.outer.setCurrentWidget(self.connecting)

    # --- Real-time (WebSocket) ---
    def _on_status(self, data):
        """Serverdan status_update kelganda Asosiy ekranni jonli yangilaydi."""
        self.pages["home"]._apply_status(data)

    def _on_ws_link(self, ok):
        """WebSocket qayta ulanganda katalogni bir marta to'liq tenglashtiradi."""
        if ok:
            self._on_sync({"scope": "all"})

    def _refresh_settings_cache(self):
        worker = track(_SettingsPrefetch(self.api))
        worker.finished.connect(lambda: self.nav.set_sos_visible(sos_enabled()))
        worker.start()

    def _reload_page(self, key):
        page = self.pages.get(key)
        if page is None:
            return
        if hasattr(page, "reload"):
            page.reload()
        else:
            page.on_show()

    def _on_sync(self, data):
        """Admin paneldagi o'zgarishlarni kiosk oynasiga darhol tushiradi."""
        scope = (data or {}).get("scope") or "all"
        all_scopes = scope == "all"

        if all_scopes or scope in ("settings", "route"):
            self._refresh_settings_cache()
        if all_scopes or scope in ("content", "ads", "settings"):
            self._reload_page("home")
        if all_scopes or scope in ("content",):
            self._reload_page("videos")
            self._reload_page("books")
            if hasattr(self, "media_sync"):
                self.media_sync.kick()
        if all_scopes or scope in ("ads", "settings"):
            if hasattr(self, "ad_manager"):
                self.ad_manager.reload()
        if all_scopes or scope in ("sites",):
            self._reload_page("sites")
        if all_scopes or scope in ("route", "settings"):
            self._reload_page("map")

    def _on_cache_clear(self):
        """Admin «keshni tozalash» buyrug'i: lokal media keshi o'chiriladi.
        Kesh yoqiq bo'lsa, keyingi sinxda fayllar qaytadan yuklanadi."""
        if hasattr(self, "media_sync"):
            self.media_sync.clear()

    def show_announcement(self, text):
        """Admin yuborgan e'lonni ustki bannerda ko'rsatadi (10 soniya)."""
        self.banner.show_message(text)

    # --- Favqulodda ma'lumot (SOS) ---
    def _show_sos(self):
        """Favqulodda raqamlar va kiosk joylashuvi modali (navbar'dagi SOS)."""
        from widgets.emergency import EmergencyModal
        stats.event("sos_open")
        self._sos_modal = EmergencyModal(self, self.theme_name)
        self._sos_modal.show_over(self.theme_name)

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
            self.banner.reposition()
        # Zastavka mustaqil top-level oyna (o'z ekraniga to'liq cho'ziladi) —
        # bu yerda boshqarish shart emas.
        super().resizeEvent(e)

    # --- Navigatsiya ---
    def go(self, key):
        page = self.pages[key]
        self.stack.setCurrentWidget(page)
        if key != self.nav.active:
            stats.event("screen_view", screen=key)
        self.nav.set_active(key)
        page.on_show()
        self._tick()

    # --- Til almashtirish (UZ/RU/EN) ---
    def set_language(self, code):
        """Navbar'dagi til tugmasi bosilganda — sahifalarni yangi tilda qayta
        quradi. Pleyer/o'quvchi/PIN ochiq bo'lsa rad etiladi (xavfsiz)."""
        if code == i18n.get_lang():
            return
        if self._media_open() or self._pin_open:
            return
        i18n.set_lang(code)
        stats.event("lang_change", lang=code)
        self._rebuild_pages()

    def _rebuild_pages(self):
        """5 sahifani joriy tilda qaytadan yaratadi (matnlar _build paytida
        tr() bilan olinadi — retranslate mexanizmi shart emas)."""
        cur = self.nav.active
        for p in self.pages.values():
            # Fon ishlarini uzamiz: timerlar to'xtaydi, uchayotgan loader'lar
            # o'chirilgan widgetga signal yubormasin (RuntimeError -> crash).
            canvas = getattr(p, "canvas", p)
            t = getattr(canvas, "timer", None)
            if t is not None:
                t.stop()
            for holder in (p, canvas):
                th = getattr(holder, "_loader", None)
                if th is not None:
                    for sig in ("done", "fail"):
                        try:
                            getattr(th, sig).disconnect()
                        except (TypeError, AttributeError, RuntimeError):
                            pass  # signal ulanmagan bo'lishi mumkin
            self.stack.removeWidget(p)
            p.deleteLater()
        self.pages = {
            "home":   HomeScreen(self.api, self),
            "map":    MapScreen(self.api),
            "videos": VideosScreen(self.api),
            "books":  BooksScreen(self.api),
            "sites":  SitesScreen(self.api),
        }
        for page in self.pages.values():
            self.stack.addWidget(page)
        self.apply_theme()   # yangi sahifalar + navbar (yangi til yorliqlari)
        self.go(cur)         # joriy sahifa saqlanadi; on_show qayta yuklaydi

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
            self.banner.apply_theme(c)

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
                self.last_activity = time.monotonic()   # reklama kechiktirish
                if t == QEvent.Type.MouseButtonPress:
                    try:
                        self._exit_guard.register_tap(ev.globalPosition().toPoint())
                    except Exception:
                        # chiqish mexanizmi hech qachon ilovani yiqitmasin
                        logsetup.get_logger(__name__).exception(
                            "Maxfiy chiqish teginishida xato")
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
        stats.session_end()   # tashrif tugadi (davomiyligi bilan yoziladi)
        # Ommaviy kiosk: yo'lovchi tilni almashtirib ketgan bo'lsa, zastavka
        # paytida standart (UZ) tilga qaytaramiz — rebuild zastavka ortida
        # bo'lgani uchun ko'rinmaydi.
        if i18n.get_lang() != i18n.DEFAULT:
            i18n.set_lang(i18n.DEFAULT)
            self._rebuild_pages()

    def _dismiss_saver(self):
        was_visible = self.saver.isVisible()
        self.saver.hide()
        self.idle_timer.start()
        if was_visible:
            stats.session_start()   # yangi tashrif boshlandi
            # Yangi odamga darhol reklama urilmasin (SESSION_GRACE_S)
            if hasattr(self, "ad_manager"):
                self.ad_manager.on_session_start()

    def _exit_app(self):
        """Yagona chiqish nuqtasi: fon oqimlarini to'xtatib, ilovani yopadi."""
        self._allow_exit = True
        from system import lockdown
        lockdown.uninstall()   # klaviatura quli ochilsin (texnik xizmat uchun)
        self._shutdown()
        QApplication.quit()

    # --- Tugmalarni boshqarish (kiosk qulflash, TZ 13.1) ---
    def keyPressEvent(self, e):
        # Ctrl+Shift+Q yoki Ctrl+Shift+C -> admin chiqishi (PIN talab qilinadi —
        # klaviatura ulagan yo'lovchi PIN'siz chiqib keta olmasin)
        if (e.key() in (Qt.Key.Key_Q, Qt.Key.Key_C)
                and (e.modifiers() & Qt.KeyboardModifier.ControlModifier)
                and (e.modifiers() & Qt.KeyboardModifier.ShiftModifier)):
            self._exit_guard.ask_exit_pin()
            return
        super().keyPressEvent(e)

    def _shutdown(self):
        """Barcha fon oqimlarini xavfsiz to'xtatadi (Qt 'thread still running' bo'lmasin)."""
        from core import threads
        stats.session_end()   # ochiq sessiya navbatga yozilsin (disk saqlaydi)
        self.stats_service.stop()
        self.ws.stop()
        self.ad_manager.stop()
        self.media_sync.stop()
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
        # WINDOWED rejimda close (X) tugmasi normal yopsin; kiosk rejimda esa
        # faqat PIN/admin chiqishi (_allow_exit) ruxsat beradi.
        if not config.WINDOWED and not self._allow_exit:
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
        # Serverni topish: manzil qo'lda berilmagan bo'lsa, imzolangan UDP
        # beacon orqali avtomatik topiladi (bir nechta bo'lsa tanlatadi).
        # MUHIM: MainWindow (ApiClient/WSClient) yaratilishidan OLDIN.
        from services import discovery
        try:
            discovery.resolve_server()
        except Exception:
            logsetup.get_logger(__name__).exception("Discovery xatosi")
        # OS-darajali klaviatura qulfi (Win/Alt+Tab) — faqat frozen buildda
        # yoki KIOSK_LOCKDOWN=1 bo'lsa (system/lockdown.py'ga qarang).
        # VAQTINCHALIK: WINDOWED rejimda qulf o'rnatilmaydi.
        from system import lockdown
        if not config.WINDOWED:
            lockdown.install()
        win = MainWindow()
        if config.WINDOWED:
            win.showMaximized()    # ramkali, lekin ekranni to'ldiradi
        else:
            win.showFullScreen()
        win.start_splash()     # logotipli splash
        sys.exit(app.exec())
    except Exception:
        # Yaratish paytidagi istisnoni ham yozamiz (excepthook ba'zan kech ulanadi)
        _excepthook(*sys.exc_info())
        raise


if __name__ == "__main__":
    main()
