"""
reader.py — Kitob matn o'quvchi (TZ 8.10).

To'liq ekran: tepa-chapda "← Ortga", markazda bob nomi; o'rtada matn;
past-chapda sahifa hisoblagichi (45/560). Sahifalar matnni belgilangan
hajmga bo'lish orqali hosil qilinadi.
"""
import requests
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QScrollArea)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
import theme as T
from threads import track

PAGE_CHARS = 900   # bitta sahifaga taxminan necha belgi


class _TextLoader(QThread):
    done = pyqtSignal(dict)
    fail = pyqtSignal()

    def __init__(self, api, content_id):
        super().__init__()
        self.api = api
        self.content_id = content_id

    def run(self):
        try:
            self.done.emit(self.api.get_book_text(self.content_id))
        except requests.RequestException:
            self.fail.emit()


def paginate(chapters):
    """Boblardan sahifalar ro'yxati hosil qiladi: [(bob_nomi, matn), ...]."""
    pages = []
    for ch in chapters:
        title = ch.get("title", "")
        text = ch.get("text", "")
        # Bobni paragraflarga ajratamiz va sahifaga to'planadi
        buf = ""
        for para in text.split("\n"):
            if len(buf) + len(para) + 1 > PAGE_CHARS and buf:
                pages.append((title, buf.strip()))
                buf = ""
            buf += para + "\n"
        pages.append((title, buf.strip()))
    return pages or [("", "")]


class Reader(QWidget):
    closed = pyqtSignal()

    def __init__(self, api, item, theme_name="light"):
        super().__init__()
        self.api = api
        self.item = item
        self.theme_name = theme_name
        self.pages = []
        self.idx = 0

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        # Tepa: Ortga + bob nomi
        top = QHBoxLayout()
        top.setContentsMargins(T.SPACE["page"], T.SPACE["gap"], T.SPACE["page"], 0)
        self.back = QPushButton("←  Ortga")
        self.back.setObjectName("rBack")
        self.back.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back.clicked.connect(self.close_reader)
        self.chapter = QLabel("")
        self.chapter.setObjectName("rChapter")
        self.chapter.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top.addWidget(self.back)
        top.addWidget(self.chapter, 1)
        top.addSpacing(120)
        root.addLayout(top)

        # Matn (markazda, cheklangan kenglik)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        host = QWidget()
        hl = QHBoxLayout(host)
        hl.addStretch(1)
        self.text = QLabel("Yuklanmoqda...")
        self.text.setObjectName("rText")
        self.text.setWordWrap(True)
        self.text.setMaximumWidth(820)
        self.text.setAlignment(Qt.AlignmentFlag.AlignTop)
        hl.addWidget(self.text, 4)
        hl.addStretch(1)
        self.scroll.setWidget(host)
        root.addWidget(self.scroll, 1)

        # Past: sahifa hisoblagichi + navigatsiya
        bottom = QHBoxLayout()
        bottom.setContentsMargins(T.SPACE["page"], 0, T.SPACE["page"], T.SPACE["gap"])
        self.counter = QLabel("")
        self.counter.setObjectName("rCounter")
        self.prev_btn = QPushButton("‹")
        self.next_btn = QPushButton("›")
        for b in (self.prev_btn, self.next_btn):
            b.setObjectName("rNav")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFixedSize(T.s(48), T.s(48))
        self.prev_btn.clicked.connect(lambda: self._go(-1))
        self.next_btn.clicked.connect(lambda: self._go(+1))
        bottom.addWidget(self.counter)
        bottom.addStretch(1)
        bottom.addWidget(self.prev_btn)
        bottom.addWidget(self.next_btn)
        root.addLayout(bottom)

    def start(self):
        self._restyle()
        self.showFullScreen()
        self._loader = track(_TextLoader(self.api, self.item["id"]))
        self._loader.done.connect(self._on_text)
        self._loader.fail.connect(lambda: self.text.setText("Matnni yuklab bo'lmadi"))
        self._loader.start()

    def _on_text(self, data):
        self.pages = paginate(data.get("chapters", []))
        self.idx = 0
        self._render()

    def _go(self, delta):
        new = self.idx + delta
        if 0 <= new < len(self.pages):
            self.idx = new
            self._render()

    def _render(self):
        if not self.pages:
            return
        title, text = self.pages[self.idx]
        self.chapter.setText(title)
        self.text.setText(text)
        self.counter.setText(f"{self.idx + 1} / {len(self.pages)}")
        self.prev_btn.setEnabled(self.idx > 0)
        self.next_btn.setEnabled(self.idx < len(self.pages) - 1)
        self.scroll.verticalScrollBar().setValue(0)

    def close_reader(self):
        self.close()
        self.closed.emit()
        self.deleteLater()

    def _restyle(self):
        c = T.THEMES[self.theme_name]
        self.setStyleSheet(f"background: {c['bg']};")
        self.back.setStyleSheet(
            f"#rBack {{ background: transparent; color: {c['text']};"
            f" border: none; font-size: {T.FONT['nav']}px; font-weight: 600; }}")
        self.chapter.setStyleSheet(
            f"#rChapter {{ color: {c['text']}; font-size: {T.FONT['h2']}px;"
            f" font-weight: 600; }}")
        self.text.setStyleSheet(
            f"#rText {{ color: {c['text']}; font-size: {T.FONT['body'] + 4}px;"
            f" line-height: 180%; }}")
        self.counter.setStyleSheet(
            f"#rCounter {{ color: {c['text_secondary']}; font-size: {T.FONT['body']}px; }}")
        nav = (f"#rNav {{ background: {c['surface']}; color: {c['text']};"
               f" border: 1px solid {c['border']}; border-radius: {T.s(24)}px;"
               f" font-size: {T.s(22)}px; }}"
               f"#rNav:disabled {{ color: {c['border']}; }}")
        self.prev_btn.setStyleSheet(nav)
        self.next_btn.setStyleSheet(nav)
