"""
books.py — Kitoblar (Books) bo'limi (TZ 8.7-8.11).

Tarkibi:
  - tablar: Barchasi, Badiiy, Tarixiy, Biznes, Bolalarga
  - 4 ustunli kartochkalar (muqova, nom, muallif, o'qish/tinglash belgilari)
  - detal modal: muqova, sahifalar, tavsif, "Tinglash" (sariq) / "O'qish" (ko'k)
  - "O'qish" -> matn o'quvchi; "Tinglash" -> audiokitob pleyeri
"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QPushButton, QLabel, QScrollArea)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

import theme as T
from threads import track
from widgets.card import BookCard, can_read, can_listen
from widgets.modal import Modal
from widgets.cover import CoverLabel
from reader import Reader
from audio_player import AudioPlayer

TABS = ["Barchasi", "Badiiy", "Tarixiy", "Biznes", "Bolalarga"]
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

        head = QHBoxLayout()
        self.tab_btns = []
        for i, name in enumerate(TABS):
            b = QPushButton(name)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setCheckable(True)
            b.clicked.connect(lambda _c, idx=i: self._set_tab(idx))
            self.tab_btns.append(b)
            head.addWidget(b)
        head.addStretch(1)
        root.addLayout(head)

        self.status = QLabel("")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.status)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.grid_host = QWidget()
        self.grid = QGridLayout(self.grid_host)
        self.grid.setSpacing(T.SPACE["page"])
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
        tab = TABS[self.active_tab]
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

    # Ekran kengligiga qarab ustunlar soni (katta monitorda yoyilib ketmasin).
    # Kitob muqovasi tikka — maqbul kenglik ~230px (ekran miqyosiga mos).
    def _calc_cols(self):
        avail = self.scroll.viewport().width()
        if avail <= 0:
            avail = self.width() - 2 * T.SPACE["page"]
        spacing = self.grid.horizontalSpacing()
        target = T.s(230)
        cols = (avail + spacing) // (target + spacing)
        return max(2, int(cols))

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
            b.setStyleSheet(
                f"QPushButton {{ background: transparent; color: {color};"
                f" border: none; border-bottom: {T.s(3)}px solid {border};"
                f" padding: {T.s(10)}px {T.s(18)}px; font-size: {T.FONT['nav']}px;"
                f" font-weight: {'700' if active else '500'}; }}")


class _BookDetail(Modal):
    """Kitob detal modali (TZ 8.8)."""
    read = pyqtSignal(dict)
    listen = pyqtSignal(dict)

    def __init__(self, parent, item, api):
        super().__init__(parent, width=T.s(820), height=T.s(460))
        self.item = item

        row = QHBoxLayout()
        row.setSpacing(T.s(24))

        left = QVBoxLayout()
        cover = CoverLabel(T.s(200), T.s(290))
        cover.load(api.cover_url(item["id"]))
        left.addWidget(cover)
        pages = item.get("pages")
        plabel = QLabel(f"{pages} sahifa" if pages else "")
        plabel.setObjectName("bPages")
        plabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left.addWidget(plabel)
        row.addLayout(left)

        right = QVBoxLayout()
        right.setSpacing(T.s(10))
        title = QLabel(item.get("title", ""))
        title.setStyleSheet(f"font-size:{T.FONT['title']}px; font-weight:700;")
        title.setWordWrap(True)
        author = QLabel(item.get("author") or "")
        author.setObjectName("bAuthor")
        desc = QLabel(item.get("description") or "")
        desc.setObjectName("bDesc")
        desc.setWordWrap(True)

        btns = QHBoxLayout()
        if can_listen(item):
            listen_btn = QPushButton("🎧  Tinglash")
            listen_btn.setObjectName("listenBtn")
            listen_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            listen_btn.setFixedHeight(T.s(52))
            listen_btn.clicked.connect(lambda: self.listen.emit(self.item))
            btns.addWidget(listen_btn)
        if can_read(item):
            read_btn = QPushButton("📖  O'qish")
            read_btn.setObjectName("readBtn")
            read_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            read_btn.setFixedHeight(T.s(52))
            read_btn.clicked.connect(lambda: self.read.emit(self.item))
            btns.addWidget(read_btn)
        btns.addStretch(1)

        right.addWidget(title)
        right.addWidget(author)
        right.addWidget(desc, 1)
        right.addLayout(btns)
        row.addLayout(right, 1)
        self.content.addLayout(row)

    def show_over(self, name="light"):
        super().show_over(name)
        c = T.THEMES[name]
        self.panel.setStyleSheet(self.panel.styleSheet() + (
            f"QLabel {{ color: {c['text']}; }}"
            f"#bAuthor {{ color: {c['text_secondary']}; font-size: {T.FONT['body']}px; }}"
            f"#bDesc {{ color: {c['text_secondary']}; font-size: {T.FONT['body']}px; }}"
            f"#bPages {{ color: {c['text_secondary']}; font-size: {T.FONT['small']}px; }}"
            f"#listenBtn {{ background: {c['orange']}; color: #FFFFFF; border: none;"
            f" border-radius: {T.RADIUS['button']}px; padding: 0 {T.s(24)}px;"
            f" font-size: {T.FONT['nav']}px; font-weight: 600; }}"
            f"#listenBtn:hover {{ background: #D97706; }}"
            f"#readBtn {{ background: {c['accent']}; color: {c['accent_text']};"
            f" border: none; border-radius: {T.RADIUS['button']}px; padding: 0 {T.s(24)}px;"
            f" font-size: {T.FONT['nav']}px; font-weight: 600; }}"
            f"#readBtn:hover {{ background: #1D4ED8; }}"))
