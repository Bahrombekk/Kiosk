"""ui/window.py — Asosiy admin oynasi (sidebar + sahifalar)."""
from PyQt6.QtWidgets import (
    QWidget, QMainWindow, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QFrame, QStackedWidget, QButtonGroup
)
from PyQt6.QtCore import Qt, QTimer, QSize

import config
from icons import svg_icon, svg_pixmap
from ui.styles import C_ACCENT, C_BAD
from ui.helpers import local_ips
from ui.server_thread import ServerThread
from ui.pages.dashboard import DashboardPageMixin
from ui.pages.cache import CachePageMixin
from ui.pages.content import ContentPageMixin
from ui.pages.ads import AdsPageMixin
from ui.pages.crud import CrudPagesMixin
from ui.pages.settings import SettingsPageMixin
from ui.pages.stats import StatsPageMixin


# ----------------------------------------------------------------------------
#  Asosiy admin oynasi
# ----------------------------------------------------------------------------
class AdminWindow(DashboardPageMixin, CachePageMixin, ContentPageMixin,
                  AdsPageMixin, CrudPagesMixin, SettingsPageMixin,
                  StatsPageMixin, QMainWindow):
    NAV = [
        ("dashboard", "Boshqaruv", "layout-dashboard"),
        ("content", "Kontent", "clapperboard"),
        ("cache", "Lokal kesh", "save"),
        ("ads", "Reklama", "megaphone"),
        ("sites", "Saytlar", "globe"),
        ("route", "Bekatlar", "train-front"),
        ("stats", "Statistika", "bar-chart"),
        ("settings", "Sozlamalar", "settings"),
    ]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kiosk — Server admin")
        self.setWindowIcon(svg_icon("server", C_ACCENT, 64))
        self.resize(1180, 760)
        # Oyna erkin kichraytirilsin (sahifalardagi uzun yorliqlar wordWrap
        # bilan yoziladi — aks holda minimal kenglik matnga teng bo'lib qoladi)
        self.setMinimumSize(880, 560)

        self.server = ServerThread()
        self.server.start()

        # Generik CRUD sahifalar holati (reklama/sayt/bekat) shu yerda saqlanadi
        self._crud = {}

        central = QWidget(self)
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._sidebar())

        self.pages = QStackedWidget(central)
        self._page_index = {}
        self._page_refs = []
        builders = {
            "dashboard": self._dashboard_page, "content": self._content_page,
            "cache": self._cache_page,
            "ads": self._ads_page, "sites": self._sites_page,
            "route": self._route_page, "stats": self._stats_page,
            "settings": self._settings_page,
        }
        for key, _label, _icon in self.NAV:
            page = builders[key]()
            self._page_refs.append(page)
            self._page_index[key] = self.pages.count()
            self.pages.addWidget(page)
        root.addWidget(self.pages, 1)
        self._go("dashboard")
        self.statusBar().showMessage("Server ishga tushirilmoqda...", 3000)

        self.refresh_content()
        self.load_settings()
        self._update_stats()

        # Jonli holat (har soniyada) va statistika (har 5 soniyada)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_status)
        self.timer.start(1000)
        self._update_status()
        self.stats_timer = QTimer(self)
        self.stats_timer.timeout.connect(self._update_stats)
        self.stats_timer.start(5000)

    # ------------------------------------------------------------------
    #  Sidebar
    # ------------------------------------------------------------------
    def _sidebar(self):
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(232)
        lay = QVBoxLayout(side)
        lay.setContentsMargins(14, 18, 14, 16)
        lay.setSpacing(4)

        # Brend (logo + nom)
        brand_row = QHBoxLayout()
        brand_row.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(svg_pixmap("server", "#60A5FA", 28))
        brand_txt = QVBoxLayout()
        brand_txt.setSpacing(0)
        name = QLabel("Kiosk Server")
        name.setObjectName("brand")
        sub = QLabel("Boshqaruv paneli")
        sub.setObjectName("brandSub")
        brand_txt.addWidget(name)
        brand_txt.addWidget(sub)
        brand_row.addWidget(logo)
        brand_row.addLayout(brand_txt)
        brand_row.addStretch(1)
        lay.addLayout(brand_row)
        lay.addSpacing(18)

        # Navigatsiya tugmalari
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self._nav_btns = {}
        for key, label, icon_name in self.NAV:
            b = QPushButton("  " + label)
            b.setObjectName("navBtn")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setIconSize(QSize(19, 19))
            b.clicked.connect(lambda _c, k=key: self._go(k))
            self._nav_btns[key] = (b, icon_name)
            self.nav_group.addButton(b)
            lay.addWidget(b)
        lay.addStretch(1)

        # Pastda: server holati (rangli nuqta + matn) va manzil — kichik karta
        scard = QFrame()
        scard.setObjectName("sideCard")
        sclay = QVBoxLayout(scard)
        sclay.setContentsMargins(12, 10, 12, 10)
        sclay.setSpacing(3)
        self.side_dot = QLabel()
        self.side_status = QLabel("Server...")
        self.side_status.setObjectName("sideStatus")
        srow = QHBoxLayout()
        srow.setSpacing(8)
        srow.addWidget(self.side_dot)
        srow.addWidget(self.side_status, 1)
        sclay.addLayout(srow)
        self.side_addr = QLabel(f"{local_ips()[0]}:{config.PORT}")
        self.side_addr.setObjectName("sideAddr")
        sclay.addWidget(self.side_addr)
        lay.addWidget(scard)
        return side

    def _go(self, key):
        self.pages.setCurrentIndex(self._page_index.get(key, 0))
        for k, (b, icon_name) in self._nav_btns.items():
            active = (k == key)
            b.setChecked(active)
            b.setIcon(svg_icon(icon_name, "#FFFFFF" if active else "#94A3B8", 38))
        if key == "dashboard" and hasattr(self, "_stat_lbls"):
            self._update_stats()
        if key == "stats":
            self.refresh_usage_stats()
        if key == "cache" and hasattr(self, "_cache_timer"):
            self._refresh_cache_matrix()       # darhol
            self._cache_timer.start(2000)      # jonli yangilab turadi
        elif hasattr(self, "_cache_timer"):
            self._cache_timer.stop()           # boshqa sahifada — to'xtatamiz
        if key == "content":
            # Sahifa ko'rinib viewport haqiqiy kenglik olgach qayta teramiz
            QTimer.singleShot(0, self._recheck_cols)

    # ------------------------------------------------------------------
    #  Umumiy qurilish bloklari
    # ------------------------------------------------------------------
    def _card(self, padding=18):
        card = QFrame()
        card.setObjectName("card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(padding, padding, padding, padding)
        lay.setSpacing(10)
        return card, lay

    def _page(self, title, subtitle):
        """Standart sahifa skeleti: sarlavha + subtitle, keyin tarkib."""
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(26, 22, 26, 20)
        lay.setSpacing(14)
        t = QLabel(title)
        t.setObjectName("pageTitle")
        s = QLabel(subtitle)
        s.setObjectName("pageSub")
        lay.addWidget(t)
        lay.addWidget(s)
        return w, lay

    def _btn(self, text, icon_name, slot, kind=None, icon_color=None):
        b = QPushButton(" " + text)
        if kind:
            b.setObjectName(kind)
        color = icon_color or {"ghost": "#334155", "danger": C_BAD}.get(kind, "#FFFFFF")
        b.setIcon(svg_icon(icon_name, color, 32))
        b.setIconSize(QSize(16, 16))
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.clicked.connect(slot)
        return b

    def _broadcast_sync(self, scope="all"):
        """Kiosk ilovalariga katalog/sozlama o'zgarganini darhol bildiradi."""
        try:
            import ws
            ws.manager.broadcast_threadsafe(
                {"type": "catalog_update", "scope": scope})
        except Exception:
            pass

    @staticmethod
    def _setup_table(table):
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(46)   # kengroq qatorlar
        table.setShowGrid(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        table.horizontalHeader().setHighlightSections(False)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        # Layout viewport'ga yetib borgach tekshiramiz (singleShot(0) — navbatdan keyin)
        QTimer.singleShot(0, self._recheck_cols)

    # --- Yopilganda backendni to'xtatamiz ---
    def closeEvent(self, e):
        self.server.stop()
        self.server.wait(3000)
        super().closeEvent(e)
