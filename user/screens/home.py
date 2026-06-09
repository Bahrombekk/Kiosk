"""
home.py — Asosiy (Home) bo'limi.

Figma maketi (Kiosk.html) asosida qurilgan:
  Chap ustun  — Tezlik/Harorat plitkali kartalari, "Joylashuv: 6-vagon",
                reklama banneri.
  O'ng ustun  — "Tavsiya etamiz": afisha (pastida ‹ nom ›  pill overlay) va
                tavsiya kitob (Tinglash/O'qish).
Ikonka plitkalari va reklama Figma eksport rasmlaridan (assets/design/).
Kontent va holat serverdan yuklanadi (dinamik).
"""
import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel,
                             QPushButton, QSizePolicy, QGraphicsView, QGraphicsScene)
from PyQt6.QtCore import (Qt, QThread, pyqtSignal, QTimer, QByteArray, QRectF)
from PyQt6.QtGui import QPixmap, QPainter, QPainterPath
from PyQt6.QtSvg import QSvgRenderer

# Asosiy ekran shu qat'iy "sahna" o'lchamida quriladi va QGraphicsView orqali
# ekranga bir tekis miqyoslanadi (Figma fit() kabi) — katta ekranda buzilmaydi.
BASE_W, BASE_H = 1500, 980

import theme as T
from threads import track
from widgets.cover import CoverLabel, _Fetcher
from widgets.card import fmt_duration
from reader import Reader
from audio_player import AudioPlayer

VIDEO_TYPES = ("movie", "cartoon", "music")
BOOK_TYPES = ("book", "audiobook")

ASSETS = os.path.join(os.path.dirname(__file__), "..", "assets", "design")
AD_IMAGE = os.path.join(ASSETS, "ad.png")
IC_SPEED = os.path.join(ASSETS, "ic_speed.png")
IC_TEMP = os.path.join(ASSETS, "ic_temp.png")
IC_TRAIN = os.path.join(ASSETS, "ic_train.png")


class _Loader(QThread):
    """Status + katalogni bir martada oladi."""
    done = pyqtSignal(dict, list)
    fail = pyqtSignal()

    def __init__(self, api):
        super().__init__()
        self.api = api

    def run(self):
        try:
            self.done.emit(self.api.get_status(), self.api.get_content())
        except Exception:
            self.fail.emit()


class _StatusLoader(QThread):
    done = pyqtSignal(dict)

    def __init__(self, api):
        super().__init__()
        self.api = api

    def run(self):
        try:
            self.done.emit(self.api.get_status())
        except Exception:
            pass


def _card():
    f = QFrame()
    f.setObjectName("card")
    return f


class BannerImage(QLabel):
    """Kenglikka moslashuvchan, burchaklari yumaloq rasm (reklama/afisha).

    "fill" — balandlik qat'iy, kesib to'ldiriladi (afisha).
    "fit"  — kesilmaydi, balandlik rasmga moslashadi, maxh chegarasi (reklama).
    Fayldan yoki serverdan (URL) yuklaydi.
    """

    def __init__(self, height=200, radius=16, mode="fill", maxh=360):
        super().__init__()
        self._orig = None
        self._h = height
        self._radius = radius
        self._mode = mode      # fill | fit | box
        self._maxh = maxh
        self._fetcher = None
        if mode == "fill":
            self.setFixedHeight(height)
        self.setMinimumWidth(10)
        vpol = (QSizePolicy.Policy.Expanding if mode == "box"
                else QSizePolicy.Policy.Fixed)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, vpol)
        self.setStyleSheet("background: transparent;")

    def set_file(self, path):
        pm = QPixmap(path)
        if not pm.isNull():
            self._orig = pm
            self._rescale()
            return True
        return False

    def load_url(self, url):
        # terminate() o'rniga track() — eski fetcher tugagunicha tirik qoladi.
        self._fetcher = track(_Fetcher(url))
        self._fetcher.done.connect(self._on_data)
        self._fetcher.start()

    def _on_data(self, data, ctype):
        if "svg" in ctype or data[:5] == b"<svg " or data[:6] == b"<?xml ":
            pm = QPixmap(600, self._h * 3)
            pm.fill(Qt.GlobalColor.transparent)
            p = QPainter(pm)
            QSvgRenderer(QByteArray(data)).render(p, QRectF(0, 0, pm.width(), pm.height()))
            p.end()
            self._orig = pm
        else:
            pm = QPixmap()
            pm.loadFromData(data)
            if pm.isNull():
                return
            self._orig = pm
        self._rescale()

    def resizeEvent(self, e):
        self._rescale()
        super().resizeEvent(e)

    def _rescale(self):
        if not self._orig or self.width() < 2:
            return
        w = self.width()
        if self._mode == "fit":
            scaled = self._orig.scaled(
                w, self._maxh, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            h = scaled.height()
            self.setFixedHeight(h)
        else:
            # fill — qat'iy balandlik; box — widget allokatsiya qilgan balandlik
            h = self.height() if self._mode == "box" else self._h
            if h < 2:
                return
            scaled = self._orig.scaled(
                w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation)
        out = QPixmap(w, h)
        out.fill(Qt.GlobalColor.transparent)
        p = QPainter(out)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, self._radius, self._radius)
        p.setClipPath(path)
        x = (w - scaled.width()) // 2
        y = (h - scaled.height()) // 2
        p.drawPixmap(x, y, scaled)
        p.end()
        self.setPixmap(out)


class Poster(QFrame):
    """Tavsiya afishasi: muqova (kesib to'ldiriladi) + pastida ‹ nom · meta › pill."""
    clicked = pyqtSignal()
    prev = pyqtSignal()
    next = pyqtSignal()

    def __init__(self, min_height=300):
        super().__init__()
        self.setObjectName("poster")
        self.setMinimumHeight(min_height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.cover = BannerImage(mode="box", radius=T.RADIUS["card"])
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.cover)

        # Pastdagi pill (afisha ustida suzadi)
        self.pill = QFrame(self)
        self.pill.setObjectName("posterPill")
        ph = QHBoxLayout(self.pill)
        ph.setContentsMargins(22, 14, 22, 14)
        self.prev_btn = self._arrow("‹")
        self.next_btn = self._arrow("›")
        self.prev_btn.clicked.connect(self.prev.emit)
        self.next_btn.clicked.connect(self.next.emit)
        mid = QVBoxLayout()
        mid.setSpacing(2)
        self.name = QLabel("—")
        self.name.setObjectName("pName")
        self.name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.meta = QLabel("")
        self.meta.setObjectName("pMeta")
        self.meta.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mid.addWidget(self.name)
        mid.addWidget(self.meta)
        ph.addWidget(self.prev_btn)
        ph.addLayout(mid, 1)
        ph.addWidget(self.next_btn)

    def _arrow(self, ch):
        b = QPushButton(ch)
        b.setObjectName("pArr")
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setFixedSize(56, 56)
        return b

    def resizeEvent(self, e):
        m = 18
        ph = 92
        self.pill.setGeometry(m, self.height() - ph - m,
                              self.width() - 2 * m, ph)
        self.pill.raise_()
        super().resizeEvent(e)

    def mouseReleaseEvent(self, e):
        # Pill tashqarisiga (afishaga) bosilsa — ochiladi
        if e.button() == Qt.MouseButton.LeftButton \
                and not self.pill.geometry().contains(e.pos()):
            self.clicked.emit()


class _HomeCanvas(QWidget):
    """Asosiy ekran tarkibi — qat'iy BASE_W×BASE_H o'lchamda quriladi.
    HomeScreen uni QGraphicsView orqali ekranga bir tekis miqyoslaydi."""

    def __init__(self, api, host):
        super().__init__()
        self.api = api
        self.host = host          # modal/oynalarni biriktirish uchun haqiqiy oyna
        self.theme_name = "light"
        self.rec_movies = []
        self.movie_idx = 0
        self.rec_book = None
        self._loader = None
        self._sloader = None
        self._modal = None
        self._reader = None
        self._audio = None
        self.setObjectName("homeCanvas")
        self.setFixedSize(BASE_W, BASE_H)
        self._build()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh_status)
        self.timer.setInterval(3000)

    def _tile(self, icon_path, icon_px=80):
        tile = QLabel()
        tile.setObjectName("tile")
        tile.setFixedSize(104, 104)
        tile.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pm = QPixmap(icon_path)
        if not pm.isNull():
            tile.setPixmap(pm.scaled(icon_px, icon_px,
                                     Qt.AspectRatioMode.KeepAspectRatio,
                                     Qt.TransformationMode.SmoothTransformation))
        return tile

    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(T.SPACE["page"], 0, T.SPACE["page"], T.SPACE["page"])
        root.setSpacing(T.SPACE["page"])

        # ---- Chap ustun ----
        left = QVBoxLayout()
        left.setSpacing(T.SPACE["gap"])

        metrics = QHBoxLayout()
        metrics.setSpacing(T.SPACE["gap"])
        self.speed_card, self.speed_val = self._metric_card("Tezlik", IC_SPEED)
        self.temp_card, self.temp_val = self._metric_card("Harorat", IC_TEMP)
        metrics.addWidget(self.speed_card)
        metrics.addWidget(self.temp_card)
        left.addLayout(metrics)

        # Joylashuv
        self.loc_card = _card()
        lh = QHBoxLayout(self.loc_card)
        lh.setContentsMargins(26, 22, 26, 22)
        lh.setSpacing(24)
        lh.addWidget(self._tile(IC_TRAIN, 92))
        lv = QVBoxLayout()
        lv.setSpacing(4)
        self.loc_title = QLabel("Joylashuv")
        self.loc_title.setObjectName("tBig")
        self.loc_note = QLabel("")
        self.loc_note.setObjectName("tNote")
        self.loc_note.setWordWrap(True)
        lv.addWidget(self.loc_title)
        lv.addWidget(self.loc_note)
        lh.addLayout(lv, 1)
        left.addWidget(self.loc_card)

        # Reklama banner — chap ustunning qolgan balandligini to'ldiradi
        # (Figma object-fit: cover). Kanvas bilan birga miqyoslanadi.
        self.ad = BannerImage(mode="box", radius=T.RADIUS["card"])
        if not self.ad.set_file(AD_IMAGE):
            self.ad.hide()
        left.addWidget(self.ad, 1)

        # ---- O'ng ustun (oq karta) ----
        self.right = _card()
        rl = QVBoxLayout(self.right)
        rl.setContentsMargins(34, 30, 34, 34)
        rl.setSpacing(0)
        self.rec_head = QLabel("Tavsiya etamiz")
        self.rec_head.setObjectName("recHead")
        rl.addWidget(self.rec_head)
        rl.addSpacing(20)

        self.poster = Poster(min_height=300)
        self.poster.clicked.connect(self._open_movie)
        self.poster.prev.connect(lambda: self._cycle_movie(-1))
        self.poster.next.connect(lambda: self._cycle_movie(+1))
        rl.addWidget(self.poster, 5)
        rl.addSpacing(26)

        # Tavsiya kitob — afisha bilan teng balandlikda, o'ng kartani to'ldiradi
        self.book_card = QFrame()
        self.book_card.setObjectName("bookCard")
        self.book_card.setSizePolicy(QSizePolicy.Policy.Expanding,
                                     QSizePolicy.Policy.Expanding)
        bc = QHBoxLayout(self.book_card)
        bc.setContentsMargins(22, 22, 22, 22)
        bc.setSpacing(24)
        self.book_cover = CoverLabel(180, 250)
        bc.addWidget(self.book_cover, alignment=Qt.AlignmentFlag.AlignVCenter)
        btext = QVBoxLayout()
        btext.setSpacing(6)
        self.book_title = QLabel("—")
        self.book_title.setObjectName("tBig")
        self.book_title.setWordWrap(True)
        self.book_author = QLabel("")
        self.book_author.setObjectName("tNote")
        btext.addWidget(self.book_title)
        btext.addWidget(self.book_author)
        btext.addStretch(1)
        self.listen_btn = QPushButton("🎧  Tinglash")
        self.listen_btn.setObjectName("listenBtn")
        self.read_btn = QPushButton("📖  O'qish")
        self.read_btn.setObjectName("readBtn")
        for b in (self.listen_btn, self.read_btn):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFixedHeight(58)
        self.listen_btn.clicked.connect(self._listen_book)
        self.read_btn.clicked.connect(self._read_book)
        btext.addWidget(self.listen_btn)
        btext.addWidget(self.read_btn)
        bc.addLayout(btext, 1)
        rl.addWidget(self.book_card, 4)

        root.addLayout(left, 1)
        root.addWidget(self.right, 1)

    def _metric_card(self, label, icon_path):
        card = _card()
        h = QHBoxLayout(card)
        h.setContentsMargins(26, 22, 26, 22)
        h.setSpacing(24)
        h.addWidget(self._tile(icon_path, 80))
        v = QVBoxLayout()
        v.setSpacing(4)
        lbl = QLabel(label)
        lbl.setObjectName("tBig")
        val = QLabel("—")
        val.setObjectName("tNote")
        v.addWidget(lbl)
        v.addWidget(val)
        h.addLayout(v)
        h.addStretch(1)
        return card, val

    # ---- Yuklash ----
    def on_show(self):
        self._loader = track(_Loader(self.api))
        self._loader.done.connect(self._on_data)
        self._loader.start()
        self.timer.start()

    def hideEvent(self, e):
        self.timer.stop()
        super().hideEvent(e)

    def _on_data(self, status, content):
        self._apply_status(status)
        recs = [c for c in content if c.get("is_recommended")
                and c.get("type") in VIDEO_TYPES]
        others = [c for c in content if c.get("type") in VIDEO_TYPES
                  and not c.get("is_recommended")]
        self.rec_movies = recs if len(recs) >= 2 else recs + others
        self.movie_idx = 0
        self.rec_book = next((c for c in content if c.get("is_recommended")
                              and c.get("type") in BOOK_TYPES), None)
        if not self.rec_book:
            self.rec_book = next((c for c in content
                                  if c.get("type") in BOOK_TYPES), None)
        self._render_rec()

    def _refresh_status(self):
        self._sloader = track(_StatusLoader(self.api))
        self._sloader.done.connect(self._apply_status)
        self._sloader.start()

    def _apply_status(self, s):
        self.speed_val.setText(f"{s.get('speed', '—')} km/h")
        self.temp_val.setText(f"+{s.get('temperature', '—')}°C")
        wagon = s.get("wagon")
        self.loc_title.setText(f"Joylashuv: {wagon}-vagon" if wagon else "Joylashuv")
        self.loc_note.setText(s.get("wagon_note") or "")

    def _cycle_movie(self, delta):
        if len(self.rec_movies) <= 1:
            return
        self.movie_idx = (self.movie_idx + delta) % len(self.rec_movies)
        self._render_rec()

    def _render_rec(self):
        if self.rec_movies:
            self.poster.show()
            movie = self.rec_movies[self.movie_idx]
            self.poster.cover.load_url(self.api.cover_url(movie["id"]))
            self.poster.name.setText(movie.get("title", ""))
            parts = [p for p in (movie.get("genre"),
                                 fmt_duration(movie.get("duration"))) if p]
            self.poster.meta.setText(" • ".join(parts))
            multi = len(self.rec_movies) > 1
            self.poster.prev_btn.setVisible(multi)
            self.poster.next_btn.setVisible(multi)
        else:
            self.poster.hide()
        if self.rec_book:
            self.book_card.show()
            self.book_cover.load(self.api.cover_url(self.rec_book["id"]))
            self.book_title.setText(self.rec_book.get("title", ""))
            self.book_author.setText(self.rec_book.get("author") or "")
            self.listen_btn.show()
            self.read_btn.show()
        else:
            self.book_card.hide()

    # ---- Harakatlar ----
    def _open_movie(self):
        if not self.rec_movies:
            return
        movie = self.rec_movies[self.movie_idx]
        from screens.videos import _VideoDetail
        self._modal = _VideoDetail(self.host, movie, self.api)
        self._modal.play.connect(self._play_movie)
        self._modal.show_over(self.theme_name)

    def _play_movie(self, item):
        if self._modal:
            self._modal.close_modal()
        from player import VideoPlayer
        old = getattr(self, "_player", None)
        if old is not None:
            old.stop_and_close()
        self._player = VideoPlayer(self.api.stream_url(item["id"]), item.get("title", ""))
        self._player.closed.connect(lambda: setattr(self, "_player", None))
        self._player.start()

    def _read_book(self):
        if self.rec_book:
            self._reader = Reader(self.api, self.rec_book, self.theme_name)
            self._reader.start()

    def _listen_book(self):
        if self.rec_book:
            old = getattr(self, "_audio", None)
            if old is not None:
                old.stop_and_close()
            self._audio = AudioPlayer(self.api, self.rec_book, self.theme_name)
            self._audio.closed.connect(lambda: setattr(self, "_audio", None))
            self._audio.start()

    # ---- Mavzu ----
    def apply_theme(self, name):
        self.theme_name = name
        c = T.THEMES[name]
        self.setStyleSheet(
            f"#homeCanvas {{ background: transparent; }}"
            f"#card {{ background: {c['surface']}; border-radius: {T.RADIUS['card']}px; }}"
            f"#bookCard {{ background: #F6F8FB; border: 1px solid #EAEFF6;"
            f" border-radius: {T.RADIUS['card']}px; }}"
            f"#tile {{ background: {c['surface2']}; border-radius: 22px; }}"
            f"#tBig {{ color: {c['text']}; font-size: 30px; font-weight: 600; }}"
            f"#tNote {{ color: {c['text_secondary']}; font-size: 22px; font-weight: 500; }}"
            f"#recHead {{ color: {c['text']}; font-size: 36px; font-weight: 600; }}"
            f"#poster {{ background: #0c1418; border-radius: {T.RADIUS['card']}px; }}"
            f"#posterPill {{ background: rgba(244,246,249,0.93);"
            f" border-radius: 22px; }}"
            f"#pName {{ color: #1c2230; font-size: 32px; font-weight: 700; }}"
            f"#pMeta {{ color: #7c8595; font-size: 20px; font-weight: 500; }}"
            f"#pArr {{ background: transparent; color: #3a4252; border: none;"
            f" font-size: 40px; font-weight: 400; }}"
            f"#listenBtn {{ background: {c['orange']}; color: #FFFFFF; border: none;"
            f" border-radius: {T.RADIUS['button']}px; font-size: 24px; font-weight: 600; }}"
            f"#listenBtn:hover {{ background: #D97706; }}"
            f"#readBtn {{ background: {c['accent']}; color: {c['accent_text']}; border: none;"
            f" border-radius: {T.RADIUS['button']}px; font-size: 24px; font-weight: 600; }}"
            f"#readBtn:hover {{ background: #1D4ED8; }}")


class HomeScreen(QWidget):
    """Asosiy ekran o'rami: tarkibni (_HomeCanvas) qat'iy o'lchamda saqlab,
    QGraphicsView orqali mavjud joyga bir tekis (nisbatni saqlab) miqyoslaydi.
    Shunday qilib istalgan ekran o'lchamida ko'rinish buzilmaydi (Figma fit()).
    """

    def __init__(self, api, host=None):
        super().__init__()
        self.canvas = _HomeCanvas(api, host or self)

        self.scene = QGraphicsScene(self)
        self.proxy = self.scene.addWidget(self.canvas)
        self.view = QGraphicsView(self.scene, self)
        self.view.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setRenderHints(QPainter.RenderHint.Antialiasing
                                 | QPainter.RenderHint.SmoothPixmapTransform)
        self.view.setStyleSheet("background: transparent; border: none;")
        # Shaffof — orqada turgan oyna foni (satin rasmi) ko'rinsin
        self.view.setBackgroundBrush(Qt.GlobalColor.transparent)
        self.view.viewport().setAutoFillBackground(False)
        self.view.viewport().setStyleSheet("background: transparent;")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.view)

    def _fit(self):
        self.view.fitInView(self.proxy, Qt.AspectRatioMode.KeepAspectRatio)

    def resizeEvent(self, e):
        self._fit()
        super().resizeEvent(e)

    def showEvent(self, e):
        self._fit()
        super().showEvent(e)

    # --- main.py kutadigan interfeys (delegatsiya) ---
    def apply_theme(self, name):
        self.canvas.apply_theme(name)
        # Sahna/ko'rinish shaffof — letterbox ham oyna fonini (satin) ko'rsatadi
        self.view.setBackgroundBrush(Qt.GlobalColor.transparent)
        self.scene.setBackgroundBrush(Qt.GlobalColor.transparent)

    def on_show(self):
        self.canvas.on_show()
        self._fit()

    def hideEvent(self, e):
        self.canvas.timer.stop()    # sahifadan chiqilganda status so'rovini to'xtatamiz
        super().hideEvent(e)

    def _apply_status(self, data):
        # main.py WebSocket status_update'ni shu orqali uzatadi
        self.canvas._apply_status(data)
