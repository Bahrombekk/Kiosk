"""
books.py — Kitoblar (Books) bo'limi (TZ 8.7-8.11).

Tarkibi:
  - tablar: Barchasi, Badiiy, Tarixiy, Biznes, Bolalarga
  - 4 ustunli kartochkalar (muqova, nom, muallif, o'qish/tinglash belgilari)
  - detal modal: muqova, sahifalar, tavsif, "Tinglash" (sariq) / "O'qish" (ko'k)
  - "O'qish" -> matn o'quvchi; "Tinglash" -> audiokitob pleyeri
"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QPushButton, QLabel, QScrollArea, QFrame)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QIcon

import theme as T
from threads import track
from widgets.card import BookCard, can_read, can_listen, _svg_pixmap
from widgets.modal import Modal
from widgets.cover import CoverLabel
from reader import Reader
from audio_player import AudioPlayer

# Tab ikonkalari — Kitoblar.html dizaynidan AYNAN ko'chirilgan inline SVG.
_GRID_SVG = ("<svg viewBox='0 0 24 24' fill='currentColor'>"
             "<rect x='3' y='3' width='7' height='7' rx='1.6'/>"
             "<rect x='14' y='3' width='7' height='7' rx='1.6'/>"
             "<rect x='3' y='14' width='7' height='7' rx='1.6'/>"
             "<circle cx='17.5' cy='17.5' r='3.4' fill='none' stroke='currentColor' stroke-width='2'/>"
             "<path d='m20 20 2 2' stroke='currentColor' stroke-width='2' stroke-linecap='round'/></svg>")
_GLOBE_SVG = ("<svg viewBox='0 0 24 24' fill='none'>"
              "<circle cx='12' cy='12' r='9' stroke='currentColor' stroke-width='1.9'/>"
              "<ellipse cx='12' cy='12' rx='4' ry='9' stroke='currentColor' stroke-width='1.9'/>"
              "<path d='M3.5 9h17M3.5 15h17' stroke='currentColor' stroke-width='1.9'/></svg>")
_BANK_SVG = ("<svg viewBox='0 0 24 24' fill='none'>"
             "<path d='M12 3 21 8H3l9-5Z' fill='currentColor'/>"
             "<path d='M5 8v9M9.5 8v9M14.5 8v9M19 8v9' stroke='currentColor' stroke-width='2'/>"
             "<path d='M3 20h18' stroke='currentColor' stroke-width='2.2' stroke-linecap='round'/></svg>")
_CASE_SVG = ("<svg viewBox='0 0 24 24' fill='none'>"
             "<rect x='3' y='7' width='18' height='13' rx='2.2' stroke='currentColor' stroke-width='2'/>"
             "<path d='M8 7V5.5A1.5 1.5 0 0 1 9.5 4h5A1.5 1.5 0 0 1 16 5.5V7'"
             " stroke='currentColor' stroke-width='2'/>"
             "<path d='M3 12h18' stroke='currentColor' stroke-width='2'/></svg>")
_SPARK_SVG = ("<svg viewBox='0 0 24 24' fill='none'>"
              "<path d='m5 19 10-10-3-3L2 16l3 3Z' stroke='currentColor'"
              " stroke-width='2' stroke-linejoin='round'/>"
              "<path d='m13 6 3 3 3-3-3-3-3 3Z' fill='currentColor'/>"
              "<path d='M18 14v3M16.5 15.5h3M6 3v2M5 4h2' stroke='currentColor'"
              " stroke-width='1.6' stroke-linecap='round'/></svg>")

# (nom, qaysi SVG ikonka)
TABS = [
    ("Barchasi",  _GRID_SVG),
    ("Badiiy",    _GLOBE_SVG),
    ("Tarixiy",   _BANK_SVG),
    ("Biznes",    _CASE_SVG),
    ("Bolalarga", _SPARK_SVG),
]
BOOK_TYPES = ("book", "audiobook")


class _Loader(QThread):
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


class BooksScreen(QWidget):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self.theme_name = "light"
        self.all_items = []
        self.active_tab = 0
        self.cards = []
        self._cols = 0
        self._loader = None
        self._modal = None
        self._reader = None
        self._audio = None
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(T.SPACE["page"], 0, T.SPACE["page"], T.SPACE["page"])
        root.setSpacing(T.SPACE["gap"])

        # Tablar umumiy pastki chiziq ustida (videos bilan bir xil uslub)
        self.tabs_frame = QFrame()
        self.tabs_frame.setObjectName("tabsFrame")
        tl = QHBoxLayout(self.tabs_frame)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(T.s(44))
        self.tab_btns = []
        for i, (name, _svg) in enumerate(TABS):
            b = QPushButton(" " + name)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setCheckable(True)
            b.setIconSize(QSize(T.s(28), T.s(28)))
            b.clicked.connect(lambda _c, idx=i: self._set_tab(idx))
            self.tab_btns.append(b)
            tl.addWidget(b)
        tl.addStretch(1)
        root.addWidget(self.tabs_frame)

        self.status = QLabel("")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.status)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.grid_host = QWidget()
        self.grid_host.setObjectName("gridHost")
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, T.s(8), 0, T.s(60))   # dizayn: grid padding-bottom 60
        self.grid.setHorizontalSpacing(T.s(26))                # dizayn: ustun gap 40
        self.grid.setVerticalSpacing(T.s(36))                  # dizayn: satr gap 54
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.grid_host)
        root.addWidget(self.scroll, 1)

        self.tab_btns[0].setChecked(True)

    # --- Yuklash ---
    def on_show(self):
        if not self.all_items:
            self.reload()

    def reload(self):
        self.status.setText("Yuklanmoqda...")
        self._loader = track(_Loader(self.api))
        self._loader.done.connect(self._on_loaded)
        self._loader.fail.connect(lambda: self.status.setText("Yuklab bo'lmadi"))
        self._loader.start()

    def _on_loaded(self, items):
        self.all_items = items
        self._render()

    # --- Filtr ---
    def _set_tab(self, idx):
        self.active_tab = idx
        for i, b in enumerate(self.tab_btns):
            b.setChecked(i == idx)
        self._restyle_tabs()
        self._render()

    def _filtered(self):
        out = []
        tab = TABS[self.active_tab][0]
        for it in self.all_items:
            if it.get("type") not in BOOK_TYPES:
                continue
            if self.active_tab != 0 and (it.get("category_tab") != tab):
                continue
            out.append(it)
        return out

    def _render(self):
        while self.grid.count():
            w = self.grid.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.cards = []
        items = self._filtered()
        if not items:
            self.status.setText("Hech narsa topilmadi")
            return
        self.status.setText("")
        cols = self._calc_cols()
        self._cols = cols
        for i, it in enumerate(items):
            card = BookCard(it, self.api, self.theme_name)
            card.clicked.connect(self._open_detail)
            self.cards.append(card)
            self.grid.addWidget(card, i // cols, i % cols)
        # Faol ustunlar teng cho'ziladi; avvalgi renderdan qolgan "fantom"
        # ustun stretch'larini nollaymiz (kartalar chapga surilib qolmasin).
        for cidx in range(16):
            self.grid.setColumnStretch(cidx, 1 if cidx < cols else 0)

    # Ekran kengligiga qarab ustunlar soni (katta monitorda yoyilib ketmasin).
    # Kitob muqovasi tikka — maqbul kenglik ~230px (ekran miqyosiga mos).
    def _calc_cols(self):
        avail = self.scroll.viewport().width()
        if avail <= 0:
            avail = self.width() - 2 * T.SPACE["page"]
        spacing = self.grid.horizontalSpacing()
        # Dizayn (Kitoblar.html) qatorda 4 ta karta ko'rsatadi; maqbul kenglik shunga
        # mos olinadi. Kichik ekranda kamida 3 ta sig'adi.
        target = T.s(320)
        cols = (avail + spacing) // (target + spacing)
        return max(3, int(cols))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.all_items and self._calc_cols() != getattr(self, "_cols", 0):
            self._render()

    # --- Detal modal + rejimlar ---
    def _open_detail(self, item):
        self._modal = _BookDetail(self.window(), item, self.api)
        self._modal.read.connect(self._read)
        self._modal.listen.connect(self._listen)
        self._modal.show_over(self.theme_name)

    def _read(self, item):
        if self._modal:
            self._modal.close_modal()
        self._reader = Reader(self.api, item, self.theme_name)
        self._reader.start()

    def _listen(self, item):
        if self._modal:
            self._modal.close_modal()
        self._audio = AudioPlayer(self.api, item, self.theme_name)
        self._audio.start()

    # --- Mavzu ---
    def apply_theme(self, name):
        self.theme_name = name
        c = T.THEMES[name]
        # Sahifa foni (satin) ko'rinsin — scroll/host shaffof
        self.scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.scroll.viewport().setStyleSheet("background: transparent;")
        self.grid_host.setStyleSheet("#gridHost { background: transparent; }")
        self.tabs_frame.setStyleSheet(
            f"#tabsFrame {{ border-bottom: 2px solid {c['border']}; }}")
        self.status.setStyleSheet(
            f"color: {c['text_secondary']}; font-size: {T.FONT['h2']}px;")
        self._restyle_tabs()
        for card in self.cards:
            card.apply_theme(name)

    def _restyle_tabs(self):
        c = T.THEMES[self.theme_name]
        for i, b in enumerate(self.tab_btns):
            active = (i == self.active_tab)
            color = c["accent"] if active else c["text_secondary"]
            border = c["accent"] if active else "transparent"
            b.setIcon(QIcon(_svg_pixmap(TABS[i][1], color, T.s(30))))
            b.setStyleSheet(
                f"QPushButton {{ background: transparent; color: {color};"
                f" border: none; border-bottom: {T.s(4)}px solid {border};"
                f" padding: {T.s(6)}px {T.s(4)}px {T.s(16)}px {T.s(4)}px;"
                f" font-size: {T.s(22)}px;"
                f" font-weight: {'700' if active else '600'}; }}")


class _BookDetail(Modal):
    """Kitob detal modali: chapda tikka muqova (pastida 'N sahifa' belgisi),
    o'ngda nom / muallif / ajratuvchi chiziq / tavsif va pastda yonma-yon
    Tinglash (sariq) va O'qish (ko'k) tugmalari."""
    read = pyqtSignal(dict)
    listen = pyqtSignal(dict)

    PANEL_W = 720
    COVER_W = 200
    COVER_H = 290

    def __init__(self, parent, item, api):
        self._pw = T.s(self.PANEL_W)
        super().__init__(parent, width=self._pw, height=T.s(420))
        self.item = item

        # Kenglik qat'iy, balandlik tarkibga moslashadi. MUHIM: tashqi layout
        # AlignCenter'i layout-darajasida — panelga per-item AlignCenter bermasak
        # panel butun oynani egallaydi. Shu bilan panel sizeHint'iga moslashadi.
        self.panel.setFixedWidth(self._pw)
        self.panel.setMinimumHeight(0)
        self.panel.setMaximumHeight(16777215)
        self.layout().setAlignment(self.panel, Qt.AlignmentFlag.AlignCenter)

        # X tugmani panel ustiga (yuqori-o'ng) suzuvchi qilamiz; bazaviy
        # joylashuvni tozalaymiz.
        self.close_btn.setParent(self.panel)
        while self.body.count():
            self.body.takeAt(0)
        self.body.setContentsMargins(T.s(30), T.s(30), T.s(30), T.s(30))
        self.body.setSpacing(0)

        row = QHBoxLayout()
        row.setSpacing(T.s(28))

        # --- Chap: muqova + 'N sahifa' belgisi (muqova pastida) ---
        cw, ch = T.s(self.COVER_W), T.s(self.COVER_H)
        self.cover_box = QFrame()
        self.cover_box.setFixedSize(cw, ch)
        self.cover = CoverLabel(cw, ch)
        self.cover.setParent(self.cover_box)
        self.cover.move(0, 0)
        self.cover.load(api.cover_url(item["id"]))
        pages = item.get("pages")
        self.pages_badge = None
        if pages:
            self.pages_badge = QLabel(f"{pages} sahifa", self.cover_box)
            self.pages_badge.setObjectName("bPages")
            self.pages_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left = QVBoxLayout()
        left.addWidget(self.cover_box)
        left.addStretch(1)
        row.addLayout(left)

        # --- O'ng: matn + tugmalar ---
        right = QVBoxLayout()
        right.setSpacing(0)
        self.title = QLabel(item.get("title", ""))
        self.title.setObjectName("bdTitle")
        self.title.setWordWrap(True)
        self.author = QLabel(item.get("author") or "")
        self.author.setObjectName("bdAuthor")
        self.author.setWordWrap(True)
        self.divider = QFrame()
        self.divider.setObjectName("bdDivider")
        self.divider.setFixedHeight(T.s(2))
        self.desc = QLabel(item.get("description") or "")
        self.desc.setObjectName("bdDesc")
        self.desc.setWordWrap(True)
        self.desc.setAlignment(Qt.AlignmentFlag.AlignTop)

        right.addWidget(self.title)
        right.addSpacing(T.s(10))
        right.addWidget(self.author)
        right.addSpacing(T.s(18))
        right.addWidget(self.divider)
        right.addSpacing(T.s(18))
        right.addWidget(self.desc, 1)
        right.addSpacing(T.s(20))

        btns = QHBoxLayout()
        btns.setSpacing(T.s(16))
        if can_listen(item):
            self.listen_btn = QPushButton("🎧  Tinglash")
            self.listen_btn.setObjectName("listenBtn")
            self.listen_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.listen_btn.setFixedHeight(T.s(56))
            self.listen_btn.clicked.connect(lambda: self.listen.emit(self.item))
            btns.addWidget(self.listen_btn, 1)
        if can_read(item):
            self.read_btn = QPushButton("📖  O'qish")
            self.read_btn.setObjectName("readBtn")
            self.read_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.read_btn.setFixedHeight(T.s(56))
            self.read_btn.clicked.connect(lambda: self.read.emit(self.item))
            btns.addWidget(self.read_btn, 1)
        right.addLayout(btns)
        row.addLayout(right, 1)
        self.body.addLayout(row)

    def show_over(self, name="light"):
        super().show_over(name)
        c = T.THEMES[name]
        # X tugma — panel ustida (yuqori-o'ng), yumaloq kulrang
        self.close_btn.setFixedSize(T.s(38), T.s(38))
        self.close_btn.move(self._pw - T.s(38) - T.s(18), T.s(18))
        self.close_btn.raise_()
        self.close_btn.setStyleSheet(
            f"#modalClose {{ background: {c['surface2']}; color: {c['text']};"
            f" border: none; border-radius: {T.s(19)}px; font-size: {T.s(17)}px; }}"
            f"#modalClose:hover {{ background: {c['border']}; }}")
        self.panel.setStyleSheet(
            f"#modalPanel {{ background: {c['surface']};"
            f" border-radius: {T.RADIUS['card']}px; }}"
            f"#bdTitle {{ background: transparent; color: {c['text']};"
            f" font-size: {T.s(30)}px; font-weight: 700; }}"
            f"#bdAuthor {{ background: transparent; color: {c['text_secondary']};"
            f" font-size: {T.s(20)}px; font-weight: 600; }}"
            f"#bdDivider {{ background: {c['border']}; border: none; }}"
            f"#bdDesc {{ background: transparent; color: {c['text_secondary']};"
            f" font-size: {T.s(18)}px; line-height: 150%; }}"
            f"#bPages {{ background: rgba(28,34,48,0.78); color: #FFFFFF;"
            f" border-radius: {T.s(16)}px; padding: {T.s(5)}px {T.s(16)}px;"
            f" font-size: {T.s(17)}px; font-weight: 600; }}"
            f"#listenBtn {{ background: {c['orange']}; color: #FFFFFF; border: none;"
            f" border-radius: {T.RADIUS['button']}px;"
            f" font-size: {T.s(21)}px; font-weight: 700; }}"
            f"#listenBtn:hover {{ background: #D97706; }}"
            f"#readBtn {{ background: {c['accent']}; color: {c['accent_text']};"
            f" border: none; border-radius: {T.RADIUS['button']}px;"
            f" font-size: {T.s(21)}px; font-weight: 700; }}"
            f"#readBtn:hover {{ background: #1D4ED8; }}")
        # 'N sahifa' belgisini muqova pastiga, markazga joylashtiramiz
        if self.pages_badge is not None:
            self.pages_badge.adjustSize()
            cw, ch = T.s(self.COVER_W), T.s(self.COVER_H)
            bw, bh = self.pages_badge.width(), self.pages_badge.height()
            self.pages_badge.move((cw - bw) // 2, ch - bh - T.s(14))
            self.pages_badge.raise_()
