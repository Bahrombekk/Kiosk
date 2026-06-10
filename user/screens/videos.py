"""
videos.py — Videolar (Videos) bo'limi — flagman modul (TZ 8.4-8.6).

Tarkibi:
  - tablar: Barchasi, Kinolar, Multfilmlar, Musiqa
  - nom bo'yicha real vaqt qidiruv
  - kartochkalar to'ri (3 ustun): muqova, nom, janr·davomiylik
  - kartochka bosilsa — detal modal (tavsif + "Tomosha qilish")
  - "Tomosha qilish" — to'liq ekran VLC pleyer
"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QPushButton, QLineEdit, QScrollArea, QLabel, QFrame,
                             QGraphicsDropShadowEffect)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QByteArray, QRectF, QTimer
from PyQt6.QtGui import QPixmap, QPainter, QColor, QIcon
from PyQt6.QtSvg import QSvgRenderer

from core import theme as T
from core.i18n import tr
from core.threads import track
from widgets.card import ContentCard, fmt_duration
from widgets.empty import EmptyState
from widgets.modal import Modal
from widgets.cover import CoverLabel
from widgets.spinner import StatusLabel
from players.video import VideoPlayer

# Tab nomi -> qaysi turlar ko'rsatiladi (+ dizayndagi inline SVG ikonka)
# Ikonkalar Videolar.html dizaynidan aynan ko'chirilgan.
_GRID_SVG = ("<svg viewBox='0 0 24 24' fill='currentColor'>"
             "<rect x='3' y='3' width='7' height='7' rx='1.6'/>"
             "<rect x='14' y='3' width='7' height='7' rx='1.6'/>"
             "<rect x='3' y='14' width='7' height='7' rx='1.6'/>"
             "<rect x='14' y='14' width='7' height='7' rx='1.6'/></svg>")
_FILM_SVG = ("<svg viewBox='0 0 24 24' fill='currentColor'>"
             "<rect x='3' y='6' width='18' height='14' rx='2.5'/>"
             "<path d='M4 6 7 2.5h3L7 6H4Zm6 0 3-3.5h3L13 6h-3Zm6 0 3-3.5h1.6L18.6 6H16Z'/></svg>")
_WAND_SVG = ("<svg viewBox='0 0 24 24' fill='none'>"
             "<path d='m5 19 10-10-3-3L2 16l3 3Z' stroke='currentColor' stroke-width='2' stroke-linejoin='round'/>"
             "<path d='m13 6 3 3 3-3-3-3-3 3Z' fill='currentColor'/>"
             "<path d='M18 14v3M16.5 15.5h3M6 3v2M5 4h2' stroke='currentColor' stroke-width='1.6' stroke-linecap='round'/></svg>")
_MUSIC_SVG = ("<svg viewBox='0 0 24 24' fill='none'>"
              "<path d='M9 18V6l11-2v12' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'/>"
              "<circle cx='6' cy='18' r='3' fill='currentColor'/>"
              "<circle cx='17' cy='16' r='3' fill='currentColor'/></svg>")
_SEARCH_SVG = ("<svg viewBox='0 0 24 24' fill='none'>"
               "<circle cx='11' cy='11' r='7' stroke='currentColor' stroke-width='2.2'/>"
               "<path d='m20 20-4-4' stroke='currentColor' stroke-width='2.2' stroke-linecap='round'/></svg>")

# (yorliq tr-kaliti, content turlari, ikonka) — yorliq i18n orqali tarjima qilinadi
TABS = [
    ("common.tab_all",      ("movie", "cartoon", "music"), _GRID_SVG),
    ("videos.tab.movies",   ("movie",),                    _FILM_SVG),
    ("videos.tab.cartoons", ("cartoon",),                  _WAND_SVG),
    ("videos.tab.music",    ("music",),                    _MUSIC_SVG),
]


def _svg_icon(svg, color_hex, size=28):
    """Inline SVG matnini berilgan rangdagi QPixmap ikonkaga aylantiradi
    (navbar.colored_icon kabi, lekin fayl emas, matndan)."""
    body = svg.replace("currentColor", "#000000")
    body = body.replace("<svg", "<svg xmlns='http://www.w3.org/2000/svg'", 1)
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    QSvgRenderer(QByteArray(body.encode("utf-8"))).render(p, QRectF(0, 0, size, size))
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    p.fillRect(pm.rect(), QColor(color_hex))
    p.end()
    return pm


class _Loader(QThread):
    """Katalogni serverdan alohida oqimda oladi (UI qotmaydi)."""
    done = pyqtSignal(list)
    fail = pyqtSignal()

    def __init__(self, api):
        super().__init__()
        self.api = api

    def run(self):
        try:
            self.done.emit(self.api.get_content())
        except Exception:
            self.fail.emit()


class VideosScreen(QWidget):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self.theme_name = "light"
        self.all_items = []      # serverdan kelgan barcha kontent
        self.active_tab = 0
        self.search_text = ""
        self.cards = []
        self._cols = 0
        self._loader = None
        self._player = None
        self._modal = None
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(T.SPACE["page"], T.SPACE["gap"],
                                T.SPACE["page"], T.SPACE["page"])
        root.setSpacing(T.SPACE["gap"])

        # --- Tablar (ikonka + matn) + qidiruv qutisi ---
        head = QHBoxLayout()
        head.setSpacing(T.s(28))

        # Tablar umumiy pastki chiziq ustida turadi (dizayn: #tabs border-bottom)
        self.tabs_frame = QFrame()
        self.tabs_frame.setObjectName("tabsFrame")
        tl = QHBoxLayout(self.tabs_frame)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(T.s(44))
        self.tab_btns = []
        for i, (name_key, _types, _svg) in enumerate(TABS):
            b = QPushButton(" " + tr(name_key))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setCheckable(True)
            b.setIconSize(QSize(T.s(28), T.s(28)))
            b.clicked.connect(lambda _c, idx=i: self._set_tab(idx))
            self.tab_btns.append(b)
            tl.addWidget(b)
        tl.addStretch(1)
        head.addWidget(self.tabs_frame, 1)

        # Qidiruv — oq dumaloq quti, ichida lupa ikonka (dizayn: #search)
        self.search_box = QFrame()
        self.search_box.setObjectName("searchBox")
        self.search_box.setFixedSize(T.s(360), T.s(54))
        sl = QHBoxLayout(self.search_box)
        sl.setContentsMargins(T.s(22), 0, T.s(22), 0)
        sl.setSpacing(T.s(14))
        self.search_icon = QLabel()
        self.search_icon.setFixedSize(T.s(24), T.s(24))
        self.search = QLineEdit()
        self.search.setObjectName("searchInput")
        self.search.setPlaceholderText(tr("videos.search"))
        self.search.setFrame(False)
        self.search.textChanged.connect(self._on_search)
        sl.addWidget(self.search_icon)
        sl.addWidget(self.search, 1)
        ssh = QGraphicsDropShadowEffect(self.search_box)
        ssh.setBlurRadius(T.s(36))
        ssh.setOffset(0, T.s(12))
        ssh.setColor(QColor(40, 55, 90, 50))
        self.search_box.setGraphicsEffect(ssh)
        head.addWidget(self.search_box, 0, Qt.AlignmentFlag.AlignBottom)
        root.addLayout(head)

        # Holat (spinner + matn) va bo'sh holat komponentlari
        self.status = StatusLabel(self.theme_name)
        root.addWidget(self.status)
        self.empty = EmptyState(icon="video", theme=self.theme_name)
        root.addWidget(self.empty)

        # Kartochkalar to'ri (scroll ichida) — 3 ustun
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.grid_host = QWidget()
        self.grid_host.setObjectName("gridHost")
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, T.s(8), 0, T.s(40))
        self.grid.setHorizontalSpacing(T.s(28))
        self.grid.setVerticalSpacing(T.s(34))
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.grid_host)
        root.addWidget(self.scroll, 1)

        self.tab_btns[0].setChecked(True)

    # ---------- Ma'lumot yuklash ----------
    def on_show(self):
        if not self.all_items:
            self.reload()

    def reload(self):
        self.empty.hide()
        self.status.loading(tr("common.loading"))
        self._loader = track(_Loader(self.api))
        self._loader.done.connect(self._on_loaded)
        self._loader.fail.connect(
            lambda: self.status.text(tr("common.load_failed")))
        self._loader.start()

    def _on_loaded(self, items):
        self.all_items = items
        self._render()

    # ---------- Filtr ----------
    def _set_tab(self, idx):
        self.active_tab = idx
        for i, b in enumerate(self.tab_btns):
            b.setChecked(i == idx)
        self._restyle_tabs()
        self._render()

    def _on_search(self, text):
        self.search_text = text.strip().lower()
        self._render()

    def _filtered(self):
        types = TABS[self.active_tab][1]
        out = []
        for it in self.all_items:
            if it.get("type") not in types:
                continue
            if self.search_text and self.search_text not in (it.get("title") or "").lower():
                continue
            out.append(it)
        return out

    def _render(self):
        # Eski kartochkalarni tozalaymiz
        while self.grid.count():
            w = self.grid.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.cards = []

        items = self._filtered()
        if not items:
            self.status.clear()
            self.empty.set_message(tr("common.nothing_found"))
            self.empty.show()
            return
        self.status.clear()
        self.empty.hide()

        cols = self._calc_cols()
        self._cols = cols
        for i, it in enumerate(items):
            card = ContentCard(it, self.api, self.theme_name)
            card.clicked.connect(self._open_detail)
            self.cards.append(card)
            self.grid.addWidget(card, i // cols, i % cols)
        # Faol ustunlar teng cho'ziladi; avvalgi (ko'proq ustunli) renderdan
        # qolishi mumkin bo'lgan barcha "fantom" ustun stretch'larini nollaymiz —
        # aks holda kartalar chapga surilib o'ngda bo'sh joy qoladi.
        for cidx in range(16):
            self.grid.setColumnStretch(cidx, 1 if cidx < cols else 0)
        # Layout o'rnashgach ustun sonini qayta tekshiramiz (birinchi ochilishda
        # viewport kengligi hali yakuniy emas — kartalar kichik/siqilgan chiqadi).
        QTimer.singleShot(0, self._recheck_cols)

    def _recheck_cols(self):
        if self.all_items and self.isVisible() and self._calc_cols() != self._cols:
            self._render()

    def showEvent(self, e):
        super().showEvent(e)
        QTimer.singleShot(0, self._recheck_cols)

    # Ekran kengligiga qarab ustunlar soni. Kichik ekranda ham qatorda kamida
    # 3 ta kartochka turishi uchun maqbul kenglik kichikroq (~300px) olinadi va
    # quyi chegara 3 ga qo'yiladi; katta monitorda kerak bo'lsa ko'payadi.
    def _calc_cols(self):
        avail = self.scroll.viewport().width()
        if avail <= 0:
            avail = self.width() - 2 * T.SPACE["page"]
        spacing = self.grid.horizontalSpacing()
        target = T.s(300)
        cols = (avail + spacing) // (target + spacing)
        return max(3, int(cols))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        # Kenglik o'zgarib ustunlar soni boshqacha bo'lsa — qaytadan teramiz.
        if self.all_items and self._calc_cols() != getattr(self, "_cols", 0):
            self._render()

    # ---------- Detal modal ----------
    def _open_detail(self, item):
        self._modal = _VideoDetail(self.window(), item, self.api)
        self._modal.play.connect(self._play)
        self._modal.show_over(self.theme_name)

    def _play(self, item):
        if self._modal:
            self._modal.close_modal()
        # Oflaynda striming ishlamaydi — pleyerni ochib qotirmaymiz
        if self.api.offline:
            self.status.text(tr("videos.offline"))
            return
        # Avvalgi pleyer hali ochiq bo'lsa — yopamiz (VLC resurslari bo'shasin va
        # ishlab turgan obyekt referenssiz qolib GC tomonidan abort qilinmasin).
        if self._player is not None:
            self._player.stop_and_close()
        url = self.api.stream_url(item["id"])
        self._player = VideoPlayer(url, item.get("title", ""))
        self._player.closed.connect(self._on_player_closed)
        self._player.start()

    def _on_player_closed(self):
        self._player = None

    # ---------- Mavzu ----------
    def apply_theme(self, name):
        self.theme_name = name
        c = T.THEMES[name]
        # Sahifa foni (satin) ko'rinsin — scroll/host shaffof
        self.scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            + T.scrollbar_qss(c))
        self.scroll.viewport().setStyleSheet("background: transparent;")
        self.grid_host.setStyleSheet("#gridHost { background: transparent; }")
        self.status.apply_theme(name)
        self.empty.apply_theme(name)
        # Qidiruv qutisi
        self.tabs_frame.setStyleSheet(
            f"#tabsFrame {{ border-bottom: 2px solid {c['border']}; }}")
        self.search_box.setStyleSheet(
            f"#searchBox {{ background: {c['surface']}; border-radius: {T.s(27)}px; }}")
        self.search.setStyleSheet(
            f"#searchInput {{ background: transparent; border: none; color: {c['text']};"
            f" font-size: {T.FONT['body']}px; }}")
        self.search_icon.setPixmap(_svg_icon(_SEARCH_SVG, c["text_secondary"], T.s(24)))
        self._restyle_tabs()
        for card in self.cards:
            card.apply_theme(name)

    def _restyle_tabs(self):
        c = T.THEMES[self.theme_name]
        for i, b in enumerate(self.tab_btns):
            active = (i == self.active_tab)
            color = c["accent"] if active else c["text_secondary"]
            border = c["accent"] if active else "transparent"
            b.setIcon(QIcon(_svg_icon(TABS[i][2], color, T.s(30))))
            b.setStyleSheet(
                f"QPushButton {{ background: transparent; color: {color};"
                f" border: none; border-bottom: {T.s(4)}px solid {border};"
                f" padding: {T.s(6)}px {T.s(4)}px {T.s(16)}px {T.s(4)}px;"
                f" font-size: {T.s(22)}px;"
                f" font-weight: {'700' if active else '600'}; }}"
                f"QPushButton:pressed {{ color: {c['accent']}; }}")


class _VideoDetail(Modal):
    """Video detal modali (vertikal dizayn): tepada afisha (tepa burchaklari
    yumaloq, X tugma ustida), pastida nom / janr·davomiylik / tavsif va eng
    pastda to'liq kenglikdagi ko'k 'Tomosha qilish' tugmasi."""
    play = pyqtSignal(dict)

    PANEL_W = 460
    PANEL_H = 800
    IMG_H = 300

    def __init__(self, parent, item, api):
        # O'lchamlar ekran miqyosiga moslanadi (kichik/katta monitor).
        self._pw = T.s(self.PANEL_W)
        self._img_h = T.s(self.IMG_H)
        super().__init__(parent, width=self._pw, height=T.s(self.PANEL_H))
        self.item = item

        # Balandlik tarkibga moslashsin (qat'iy emas) — kenglik qat'iy qoladi.
        self.panel.setFixedWidth(self._pw)
        self.panel.setMinimumHeight(0)
        self.panel.setMaximumHeight(16777215)

        # Bazaviy joylashuvni tozalaymiz; X tugmani panel ustiga (rasm tepasiga)
        # suzuvchi qilib ko'chiramiz.
        self.close_btn.setParent(self.panel)
        while self.body.count():
            self.body.takeAt(0)
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(0)

        # --- Header afisha: to'liq kenglik, tepa burchaklari yumaloq ---
        self.cover = CoverLabel(self._pw, self._img_h,
                                radius=T.RADIUS["card"], round_top_only=True)
        self.cover.load(api.cover_url(item["id"]))
        self.body.addWidget(self.cover)

        # --- Tarkib (padding bilan) ---
        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(T.s(30), T.s(26), T.s(30), T.s(30))
        cl.setSpacing(0)

        self.title = QLabel(item.get("title", ""))
        self.title.setObjectName("vdTitle")
        self.title.setWordWrap(True)

        sub_parts = [p for p in (item.get("genre"),
                                 fmt_duration(item.get("duration"))) if p]
        self.sub = QLabel(" • ".join(sub_parts))
        self.sub.setObjectName("vdSub")

        self.desc = QLabel(item.get("description") or "")
        self.desc.setObjectName("vdDesc")
        self.desc.setWordWrap(True)
        self.desc.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.watch = QPushButton(tr("videos.watch"))
        self.watch.setObjectName("watchBtn")
        self.watch.setCursor(Qt.CursorShape.PointingHandCursor)
        self.watch.setFixedHeight(T.s(64))
        self.watch.clicked.connect(lambda: self.play.emit(self.item))

        cl.addWidget(self.title)
        cl.addSpacing(T.s(10))
        cl.addWidget(self.sub)
        cl.addSpacing(T.s(20))
        cl.addWidget(self.desc)
        cl.addSpacing(T.s(24))
        cl.addWidget(self.watch)
        self.body.addWidget(content)

    def show_over(self, name="light"):
        super().show_over(name)
        c = T.THEMES[name]
        # X tugma rasm ustida (tepa-o'ng), yumaloq, yarim shaffof fon
        self.close_btn.setFixedSize(T.s(40), T.s(40))
        self.close_btn.move(self._pw - T.s(40) - T.s(14), T.s(14))
        self.close_btn.raise_()
        self.close_btn.setStyleSheet(
            "#modalClose { background: rgba(15,20,30,0.55); color: #FFFFFF;"
            f" border: none; border-radius: {T.s(20)}px; font-size: {T.s(18)}px; }}"
            "#modalClose:hover { background: rgba(15,20,30,0.78); }")
        self.panel.setStyleSheet(
            f"#modalPanel {{ background: {c['surface']};"
            f" border-radius: {T.RADIUS['card']}px; }}"
            f"#vdTitle {{ background: transparent; color: {c['text']};"
            f" font-size: {T.s(34)}px; font-weight: 800; }}"
            f"#vdSub {{ background: transparent; color: {c['text_secondary']};"
            f" font-size: {T.s(18)}px; font-weight: 500; }}"
            f"#vdDesc {{ background: transparent; color: {c['text_secondary']};"
            f" font-size: {T.s(18)}px; }}"
            f"#watchBtn {{ background: {c['accent']}; color: {c['accent_text']};"
            f" border: none; border-radius: {T.RADIUS['button']}px;"
            f" font-size: {T.FONT['nav']}px; font-weight: 700; }}"
            f"#watchBtn:hover {{ background: #1D4ED8; }}"
            f"#watchBtn:pressed {{ background: #1E40AF; }}")
