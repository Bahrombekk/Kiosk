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
                             QPushButton, QLineEdit, QScrollArea, QLabel)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

import theme as T
from threads import track
from widgets.card import ContentCard, fmt_duration
from widgets.modal import Modal
from widgets.cover import CoverLabel
from player import VideoPlayer

# Tab nomi -> qaysi turlar ko'rsatiladi
TABS = [
    ("Barchasi",    ("movie", "cartoon", "music")),
    ("Kinolar",     ("movie",)),
    ("Multfilmlar", ("cartoon",)),
    ("Musiqa",      ("music",)),
]


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
        self._loader = None
        self._player = None
        self._modal = None
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(T.SPACE["page"], 0, T.SPACE["page"], T.SPACE["page"])
        root.setSpacing(T.SPACE["gap"])

        # Tablar + qidiruv
        head = QHBoxLayout()
        self.tab_btns = []
        for i, (name, _types) in enumerate(TABS):
            b = QPushButton(name)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setCheckable(True)
            b.clicked.connect(lambda _c, idx=i: self._set_tab(idx))
            self.tab_btns.append(b)
            head.addWidget(b)
        head.addStretch(1)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Nomi bo'yicha qidirish")
        self.search.setFixedWidth(280)
        self.search.textChanged.connect(self._on_search)
        head.addWidget(self.search)
        root.addLayout(head)

        # Holat matni (yuklanmoqda / bo'sh)
        self.status = QLabel("")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.status)

        # Kartochkalar to'ri (scroll ichida)
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

    # ---------- Ma'lumot yuklash ----------
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
            self.status.setText("Hech narsa topilmadi")
            return
        self.status.setText("")

        cols = 3
        for i, it in enumerate(items):
            card = ContentCard(it, self.api, self.theme_name)
            card.clicked.connect(self._open_detail)
            self.cards.append(card)
            self.grid.addWidget(card, i // cols, i % cols)

    # ---------- Detal modal ----------
    def _open_detail(self, item):
        self._modal = _VideoDetail(self.window(), item, self.api)
        self._modal.play.connect(self._play)
        self._modal.show_over(self.theme_name)

    def _play(self, item):
        if self._modal:
            self._modal.close_modal()
        url = self.api.stream_url(item["id"])
        self._player = VideoPlayer(url, item.get("title", ""))
        self._player.start()

    # ---------- Mavzu ----------
    def apply_theme(self, name):
        self.theme_name = name
        c = T.THEMES[name]
        self.status.setStyleSheet(
            f"color: {c['text_secondary']}; font-size: {T.FONT['h2']}px;")
        self.search.setStyleSheet(
            f"QLineEdit {{ background: {c['surface']}; color: {c['text']};"
            f" border: 1px solid {c['border']}; border-radius: {T.RADIUS['button']}px;"
            f" padding: 10px 14px; font-size: {T.FONT['body']}px; }}")
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
                f" border: none; border-bottom: 3px solid {border};"
                f" padding: 10px 18px; font-size: {T.FONT['nav']}px;"
                f" font-weight: {'700' if active else '500'}; }}")


class _VideoDetail(Modal):
    """Video detal modali (TZ 8.5): muqova, tavsif, 'Tomosha qilish'."""
    play = pyqtSignal(dict)

    def __init__(self, parent, item, api):
        super().__init__(parent, width=820, height=460)
        self.item = item

        row = QHBoxLayout()
        row.setSpacing(24)

        cover = CoverLabel(220, 310)
        cover.load(api.cover_url(item["id"]))
        row.addWidget(cover)

        right = QVBoxLayout()
        right.setSpacing(12)
        title = QLabel(item.get("title", ""))
        title.setStyleSheet(f"font-size:{T.FONT['title']}px; font-weight:700;")
        title.setWordWrap(True)

        sub_parts = [p for p in (item.get("genre"),
                                 fmt_duration(item.get("duration"))) if p]
        sub = QLabel(" · ".join(sub_parts))
        sub.setObjectName("detSub")

        desc = QLabel(item.get("description") or "")
        desc.setWordWrap(True)
        desc.setObjectName("detDesc")

        watch = QPushButton("▶  Tomosha qilish")
        watch.setObjectName("watchBtn")
        watch.setCursor(Qt.CursorShape.PointingHandCursor)
        watch.setFixedHeight(52)
        watch.clicked.connect(lambda: self.play.emit(self.item))

        right.addWidget(title)
        right.addWidget(sub)
        right.addWidget(desc, 1)
        right.addWidget(watch)
        row.addLayout(right, 1)
        self.content.addLayout(row)

        self._style_detail()

    def _style_detail(self):
        c = T.THEMES["light"]  # show_over keyin to'g'ri mavzuni qo'yadi
        self.setStyleSheet(self.styleSheet())

    def show_over(self, name="light"):
        super().show_over(name)
        c = T.THEMES[name]
        self.panel.setStyleSheet(self.panel.styleSheet() + (
            f"QLabel {{ color: {c['text']}; }}"
            f"#detSub {{ color: {c['text_secondary']}; font-size: {T.FONT['body']}px; }}"
            f"#detDesc {{ color: {c['text_secondary']}; font-size: {T.FONT['body']}px; }}"
            f"#watchBtn {{ background: {c['accent']}; color: {c['accent_text']};"
            f" border: none; border-radius: {T.RADIUS['button']}px;"
            f" font-size: {T.FONT['nav']}px; font-weight: 600; }}"
            f"#watchBtn:hover {{ background: #1D4ED8; }}"))
