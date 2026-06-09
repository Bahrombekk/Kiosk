"""
reader.py — Kitob matn o'quvchi (TZ 8.10).

To'liq ekran: tepa-chapda "← Ortga", markazda bob nomi; o'rtada matn;
past-chapda sahifa hisoblagichi (45/560). Sahifalar matnni belgilangan
hajmga bo'lish orqali hosil qilinadi.
"""
import requests
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QScrollArea, QFrame, QScroller,
                             QGraphicsDropShadowEffect)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor
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
        # MUHIM: oddiy QWidget stylesheet `background`ni o'zida bo'yamaydi —
        # WA_StyledBackground bo'lmasa fon bo'yalmay, ortidagi eski ekran (satin)
        # ko'rinib qoladi. Shu bayroq bilan fon ishonchli bo'yaladi.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Tepa: Ortga (pill) + bob nomi
        top = QHBoxLayout()
        top.setContentsMargins(T.SPACE["page"], T.SPACE["gap"],
                               T.SPACE["page"], T.SPACE["gap"])
        self.back = QPushButton("←  Ortga")
        self.back.setObjectName("rBack")
        self.back.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back.clicked.connect(self.close_reader)
        self.chapter = QLabel("")
        self.chapter.setObjectName("rChapter")
        self.chapter.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top.addWidget(self.back)
        top.addWidget(self.chapter, 1)
        top.addSpacing(T.s(150))   # chap "Ortga" pill bilan muvozanat (markazlash)
        root.addLayout(top)

        # Matn — markazda oq "sahifa" karta ustida (kitob varag'i kabi),
        # cheklangan kenglik, yumshoq soya. Skroll sensor barmoq bilan ishlaydi.
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Sensorli ekran: barmoq bilan surib skroll qilish
        QScroller.grabGesture(self.scroll.viewport(),
                              QScroller.ScrollerGestureType.LeftMouseButtonGesture)
        host = QWidget()
        host.setObjectName("rHost")
        hl = QHBoxLayout(host)
        hl.setContentsMargins(T.SPACE["page"], T.s(8), T.SPACE["page"], T.s(32))
        hl.addStretch(1)
        self.page = QFrame()
        self.page.setObjectName("rPage")
        self.page.setMaximumWidth(T.s(880))
        psh = QGraphicsDropShadowEffect(self.page)
        psh.setBlurRadius(T.s(50))
        psh.setOffset(0, T.s(16))
        psh.setColor(QColor(40, 55, 90, 55))
        self.page.setGraphicsEffect(psh)
        pl = QVBoxLayout(self.page)
        pl.setContentsMargins(T.s(54), T.s(48), T.s(54), T.s(54))
        self.text = QLabel("Yuklanmoqda...")
        self.text.setObjectName("rText")
        self.text.setWordWrap(True)
        self.text.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.text.setAlignment(Qt.AlignmentFlag.AlignTop)
        pl.addWidget(self.text)
        hl.addWidget(self.page, 6)
        hl.addStretch(1)
        self.scroll.setWidget(host)
        root.addWidget(self.scroll, 1)

        # Past: ‹ sahifa hisoblagichi › — markazda
        bottom = QHBoxLayout()
        bottom.setContentsMargins(T.SPACE["page"], T.s(6), T.SPACE["page"], T.SPACE["gap"])
        self.counter = QLabel("")
        self.counter.setObjectName("rCounter")
        self.counter.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.counter.setMinimumWidth(T.s(140))
        self.prev_btn = QPushButton("‹")
        self.next_btn = QPushButton("›")
        for b in (self.prev_btn, self.next_btn):
            b.setObjectName("rNav")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFixedSize(T.s(56), T.s(56))
        self.prev_btn.clicked.connect(lambda: self._go(-1))
        self.next_btn.clicked.connect(lambda: self._go(+1))
        bottom.addStretch(1)
        bottom.addWidget(self.prev_btn)
        bottom.addWidget(self.counter)
        bottom.addWidget(self.next_btn)
        bottom.addStretch(1)
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
        # Fon oq (o'qishga qulay); dark mavzuda mavzu foni
        page_bg = "#FFFFFF" if self.theme_name == "light" else c["bg"]
        self.setStyleSheet(
            f"background: {page_bg};"
            f"#rHost {{ background: transparent; }}"
            f"QScrollArea {{ background: transparent; border: none; }}")
        self.scroll.viewport().setStyleSheet("background: transparent;")
        self.back.setStyleSheet(
            f"#rBack {{ background: {c['surface']}; color: {c['text']};"
            f" border: none; border-radius: {T.RADIUS['pill']}px;"
            f" padding: {T.s(12)}px {T.s(26)}px; font-size: {T.FONT['nav']}px;"
            f" font-weight: 600; }}"
            f"#rBack:hover {{ background: {c['surface2']}; }}")
        self.chapter.setStyleSheet(
            f"#rChapter {{ color: {c['text']}; font-size: {T.FONT['h2']}px;"
            f" font-weight: 600; }}")
        # Oq sahifa karta + ichidagi matn
        self.page.setStyleSheet(
            f"#rPage {{ background: {c['surface']};"
            f" border-radius: {T.RADIUS['card']}px; }}")
        self.text.setStyleSheet(
            f"#rText {{ background: transparent; color: {c['text']};"
            f" font-size: {T.FONT['body'] + 4}px; line-height: 185%; }}")
        self.counter.setStyleSheet(
            f"#rCounter {{ color: {c['text_secondary']}; font-size: {T.FONT['body']}px;"
            f" font-weight: 600; }}")
        nav = (f"#rNav {{ background: {c['surface']}; color: {c['accent']};"
               f" border: 1px solid {c['border']}; border-radius: {T.s(56) // 2}px;"
               f" font-size: {T.s(26)}px; font-weight: 700; }}"
               f"#rNav:hover {{ background: {c['surface2']}; }}"
               f"#rNav:disabled {{ color: {c['border']}; }}")
        self.prev_btn.setStyleSheet(nav)
        self.next_btn.setStyleSheet(nav)
