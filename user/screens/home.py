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
import logging
import os
from datetime import datetime
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel,
                             QPushButton, QSizePolicy, QGraphicsView,
                             QGraphicsScene)
from PyQt6.QtCore import (Qt, QThread, pyqtSignal, QTimer, QByteArray, QRectF,
                          QSize, QVariantAnimation, QEasingCurve)
from PyQt6.QtGui import QPixmap, QPainter, QPainterPath
from PyQt6.QtSvg import QSvgRenderer

# Asosiy ekran shu qat'iy "sahna" o'lchamida quriladi va QGraphicsView orqali
# ekranga bir tekis miqyoslanadi (Figma fit() kabi) — katta ekranda buzilmaydi.
BASE_W, BASE_H = 1500, 980

from core import theme as T
from core.i18n import tr
from core.threads import track
from services import stats
from widgets.cover import CoverLabel, _Fetcher
from widgets.card import fmt_duration
from widgets.icons import svg_icon
from players.reader import Reader
from players.audio import AudioPlayer

log = logging.getLogger(__name__)

VIDEO_TYPES = ("movie", "cartoon", "music")
BOOK_TYPES = ("book", "audiobook")

ASSETS = os.path.join(os.path.dirname(__file__), "..", "assets", "design")
AD_IMAGE = os.path.join(ASSETS, "ad.png")
IC_SPEED = os.path.join(ASSETS, "ic_speed.png")
IC_TEMP = os.path.join(ASSETS, "ic_temp.png")
IC_TRAIN = os.path.join(ASSETS, "ic_train.png")

# Yo'q assetlar jim bo'sh joy bo'lib qolmasin — startupda bir marta loglaymiz
# (UI baribir ishlayveradi: _tile/set_file null rasmni o'zi ushlaydi).
for _p in (AD_IMAGE, IC_SPEED, IC_TEMP, IC_TRAIN):
    if not os.path.exists(_p):
        logging.getLogger(__name__).warning("Asset topilmadi: %s", _p)


class _Loader(QThread):
    """Status + katalog + reklamalarni (banner uchun) bir martada oladi."""
    done = pyqtSignal(dict, list, list)
    fail = pyqtSignal()

    def __init__(self, api):
        super().__init__()
        self.api = api

    def run(self):
        try:
            status, content = self.api.get_status(), self.api.get_content()
            try:
                ads = self.api.get_ads()   # banner reklamalar (keshli)
            except Exception:              # noqa: BLE001
                ads = []                   # reklamasiz ham sahifa ishlasin
            self.done.emit(status, content, ads)
        except Exception:
            log.warning("Home: status/katalog yuklanmadi", exc_info=True)
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
            log.debug("Home: status olinmadi", exc_info=True)


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
        self._fade_anim = None
        self.fade_on_next = False   # keyingi rasm crossfade bilan chiqsin
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
        # Crossfade: faqat yangi rasm ataylab so'ralganda (fade_on_next) va
        # o'lcham mos kelsa — resizeEvent'dagi oddiy rescale'da animatsiya yo'q.
        old = self.pixmap()
        if (self.fade_on_next and old is not None and not old.isNull()
                and old.size() == out.size()):
            self.fade_on_next = False
            self._start_fade(old, out)
        else:
            self.fade_on_next = False
            self.setPixmap(out)

    def _start_fade(self, old, new):
        """Eski rasmdan yangisiga yumshoq o'tish (~420ms crossfade)."""
        if self._fade_anim is not None:
            self._fade_anim.stop()
        anim = QVariantAnimation(self)
        anim.setDuration(420)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        def _step(v):
            pm = QPixmap(new.size())
            pm.fill(Qt.GlobalColor.transparent)
            p = QPainter(pm)
            p.setOpacity(1.0 - v)
            p.drawPixmap(0, 0, old)
            p.setOpacity(v)
            p.drawPixmap(0, 0, new)
            p.end()
            self.setPixmap(pm)

        anim.valueChanged.connect(_step)
        anim.finished.connect(lambda: self.setPixmap(new))
        anim.start()
        self._fade_anim = anim


class _TitlePill(QFrame):
    """Afisha ostidagi nom pill'i. MUHIM: bosishni o'zi QABUL QILADI (accept) —
    QGraphicsProxyWidget ichida e'tiborsiz (ignore) qilingan bosishning
    release'i qaytib kelmasligi mumkin, shunda bosish "ishlamaydi"."""
    clicked = pyqtSignal()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            e.accept()

    def mouseReleaseEvent(self, e):
        if (e.button() == Qt.MouseButton.LeftButton
                and self.rect().contains(e.position().toPoint())):
            self.clicked.emit()
            e.accept()


class Poster(QFrame):
    """Tavsiya afishasi: muqova (kesib to'ldiriladi) + pastida ‹ nom · meta › pill.

    clicked — afisha (rasm) bosildi: detal modal ochiladi.
    title_clicked — nom yozilgan pill bosildi: namoyish DARHOL boshlanadi."""
    clicked = pyqtSignal()
    title_clicked = pyqtSignal()
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

        # Pastdagi pill (afisha ustida suzadi) — bosilsa namoyish boshlanadi
        self.pill = _TitlePill(self)
        self.pill.clicked.connect(self.title_clicked.emit)
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

        # Yozuvlar va muqova sichqonchaga "shaffof" — bosish to'g'ridan-to'g'ri
        # pill'ga (yoki Poster'ning o'ziga) tushadi, QLabel ichida "yo'qolib"
        # qolmaydi. Strelkalar QPushButton — o'zlari ushlaydi.
        for w in (self.cover, self.name, self.meta):
            w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

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

    def mousePressEvent(self, e):
        # Bosishni qabul qilamiz — proxy ichida release bizga qaytishi uchun
        if e.button() == Qt.MouseButton.LeftButton:
            e.accept()

    def mouseReleaseEvent(self, e):
        # Afisha (rasm) bosilsa — detal modal; pill o'zi title_clicked
        # chiqaradi (namoyish darhol boshlanadi).
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
        self.rec_books = []
        self.book_idx = 0
        self.rec_book = None
        self._loader = None
        self._sloader = None
        self._modal = None
        self._reader = None
        self._audio = None
        # Banner reklamalar (admin: Joylashuv = banner/both) — aylanma
        self.banner_ads = []
        self._banner_idx = -1
        self._banner_cur_id = None
        self._banner_fetch = None
        self.setObjectName("homeCanvas")
        self.setFixedSize(BASE_W, BASE_H)
        self._build()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh_status)
        self.timer.setInterval(3000)

        # Banner rotatsiyasi: har reklama o'z `duration` soniyasicha turadi
        self.banner_timer = QTimer(self)
        self.banner_timer.setSingleShot(True)
        self.banner_timer.timeout.connect(self._rotate_banner)

        # Tavsiyalar avto-almashinishi (film va kitob — bir nechta bo'lsa)
        self.rec_timer = QTimer(self)
        self.rec_timer.setInterval(8000)
        self.rec_timer.timeout.connect(self._auto_cycle)

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
        self.speed_card, self.speed_val = self._metric_card(
            tr("home.speed"), IC_SPEED)
        self.temp_card, self.temp_val = self._metric_card(
            tr("home.temp"), IC_TEMP)
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
        self.loc_title = QLabel(tr("home.location"))
        self.loc_title.setObjectName("tBig")
        self.loc_note = QLabel("")
        self.loc_note.setObjectName("tNote")
        self.loc_note.setWordWrap(True)
        lv.addWidget(self.loc_title)
        lv.addWidget(self.loc_note)
        lh.addLayout(lv, 1)
        left.addWidget(self.loc_card)

        # Reklama banner — chap ustunning qolgan balandligini to'ldiradi
        # (Figma object-fit: cover). Admin «Joylashuv = banner» qilgan
        # reklamalar shu yerda aylanib turadi (_rotate_banner); banner
        # reklama yo'q yoki oflayn bo'lsa — statik bezak rasmi (ad.png).
        self.ad = BannerImage(mode="box", radius=T.RADIUS["card"])
        if not self.ad.set_file(AD_IMAGE):
            self.ad.hide()
        left.addWidget(self.ad, 1)

        # ---- O'ng ustun (oq karta) ----
        self.right = _card()
        rl = QVBoxLayout(self.right)
        rl.setContentsMargins(34, 30, 34, 34)
        rl.setSpacing(0)
        self.rec_head = QLabel(tr("home.recommend"))
        self.rec_head.setObjectName("recHead")
        rl.addWidget(self.rec_head)
        rl.addSpacing(20)

        self.poster = Poster(min_height=300)
        self.poster.clicked.connect(self._open_movie)
        self.poster.title_clicked.connect(self._play_current)
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
        self.listen_btn = QPushButton(tr("common.listen"))
        self.listen_btn.setObjectName("listenBtn")
        self.listen_btn.setIcon(svg_icon("headphones", "#FFFFFF", 48))
        self.read_btn = QPushButton(tr("common.read"))
        self.read_btn.setObjectName("readBtn")
        self.read_btn.setIcon(svg_icon("book-open", "#FFFFFF", 48))
        for b in (self.listen_btn, self.read_btn):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFixedHeight(58)
            b.setIconSize(QSize(24, 24))
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
        self.banner_timer.stop()   # sahifa yopiq — banner aylanmasin
        self.rec_timer.stop()      # tavsiya ham
        super().hideEvent(e)

    def _on_data(self, status, content, ads):
        self._apply_status(status)
        self._set_banner_ads(ads)
        # Tavsiyalar ham joriy interfeys tiliga mos bo'lsin (qat'iy filtr)
        from core.i18n import content_visible
        content = [c for c in content if content_visible(c)]
        recs = [c for c in content if c.get("is_recommended")
                and c.get("type") in VIDEO_TYPES]
        others = [c for c in content if c.get("type") in VIDEO_TYPES
                  and not c.get("is_recommended")]
        self.rec_movies = recs if len(recs) >= 2 else recs + others
        self.movie_idx = 0
        brecs = [c for c in content if c.get("is_recommended")
                 and c.get("type") in BOOK_TYPES]
        bothers = [c for c in content if c.get("type") in BOOK_TYPES
                   and not c.get("is_recommended")]
        self.rec_books = brecs if len(brecs) >= 2 else brecs + bothers
        self.book_idx = 0
        self.rec_book = self.rec_books[0] if self.rec_books else None
        self._render_rec()
        # Bir nechta tavsiya bo'lsa — film ham, kitob ham o'zi aylanib turadi
        if len(self.rec_movies) > 1 or len(self.rec_books) > 1:
            self.rec_timer.start()
        else:
            self.rec_timer.stop()

    def _auto_cycle(self):
        """Avto-aylanish (har 8 s): film va kitob tavsiyalari crossfade bilan."""
        if len(self.rec_movies) > 1:
            self.movie_idx = (self.movie_idx + 1) % len(self.rec_movies)
        if len(self.rec_books) > 1:
            self.book_idx = (self.book_idx + 1) % len(self.rec_books)
            self.rec_book = self.rec_books[self.book_idx]
        self._render_rec()

    def _refresh_status(self):
        self._sloader = track(_StatusLoader(self.api))
        self._sloader.done.connect(self._apply_status)
        self._sloader.start()

    # ---- Banner reklama aylanmasi ----
    def _set_banner_ads(self, ads):
        """Admin «banner»/«both» qilgan RASM reklamalarni oladi va aylanmani
        (qayta) boshlaydi. Banner reklama yo'q bo'lsa statik rasm qoladi."""
        self.banner_ads = [
            a for a in ads if a.get("media_path")
            and a.get("media_type") != "video"   # banner faqat rasm
            and (a.get("placement") or "popup") in ("banner", "both")]
        self.banner_timer.stop()
        if self.banner_ads:
            self._rotate_banner()
        elif self._banner_cur_id is not None:
            # Reklamalar olib tashlandi — statik bezakka qaytamiz
            self._banner_cur_id = None
            self._banner_idx = -1
            if self.ad.set_file(AD_IMAGE):
                self.ad.show()

    def _banner_eligible(self):
        """Kunlik vaqt oralig'i (start/end_time) ichidagi banner reklamalar."""
        from services.ads import AdManager
        now = datetime.now()
        nm = now.hour * 60 + now.minute
        return [a for a in self.banner_ads if AdManager._in_window(a, nm)]

    def _rotate_banner(self):
        elig = self._banner_eligible()
        if not elig:
            # Hozir birortasining vaqti emas — statik rasm; keyinroq qaytamiz
            if self._banner_cur_id is not None:
                self._banner_cur_id = None
                if self.ad.set_file(AD_IMAGE):
                    self.ad.show()
            if self.banner_ads:
                self.banner_timer.start(60_000)
            return
        self._banner_idx = (self._banner_idx + 1) % len(elig)
        ad = elig[self._banner_idx]
        if ad.get("id") == self._banner_cur_id and len(elig) == 1:
            # Yagona reklama allaqachon ekranda — qayta yuklamaymiz, faqat
            # vaqt oralig'i tugashini kuzatib turamiz
            self.banner_timer.start(60_000)
            return
        f = track(_Fetcher(self.api.ad_media_url(ad["id"])))
        self._banner_fetch = f
        f.done.connect(lambda data, _c, ad=ad: self._on_banner_media(ad, data))
        f.fail.connect(lambda: self.banner_timer.start(30_000))  # oflayn/xato
        f.start()

    def _on_banner_media(self, ad, data):
        pm = QPixmap()
        pm.loadFromData(data)
        if pm.isNull():
            self.banner_timer.start(30_000)
            return
        self.ad._orig = pm
        self.ad._rescale()
        self.ad.show()
        changed = ad.get("id") != self._banner_cur_id
        self._banner_cur_id = ad.get("id")
        if changed:
            # Proof-of-play: banner namoyishi ham statistikaga yoziladi
            stats.event("ad_play", ad_id=ad.get("id"), title=ad.get("title"),
                        media_type="image", placement="banner")
        dur = ad.get("duration") or 0
        self.banner_timer.start(max(5, int(dur) if dur else 10) * 1000)

    def _apply_status(self, s):
        self.speed_val.setText(f"{s.get('speed', '—')} km/h")
        self.temp_val.setText(f"+{s.get('temperature', '—')}°C")
        wagon = s.get("wagon")
        self.loc_title.setText(
            tr("home.location_wagon", wagon=wagon) if wagon
            else tr("home.location"))
        self.loc_note.setText(s.get("wagon_note") or "")

    def _cycle_movie(self, delta):
        if len(self.rec_movies) <= 1:
            return
        self.movie_idx = (self.movie_idx + delta) % len(self.rec_movies)
        self._render_rec()
        # Qo'lda yoki avto almashinishdan keyin hisob qaytadan boshlanadi
        if self.rec_timer.isActive():
            self.rec_timer.start()

    def _render_rec(self):
        if self.rec_movies:
            self.poster.show()
            movie = self.rec_movies[self.movie_idx]
            self.poster.cover.fade_on_next = True   # yumshoq crossfade
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
            changed = (self.rec_book.get("id")
                       != getattr(self, "_last_book_id", None))
            self._last_book_id = self.rec_book.get("id")
            self.book_card.show()
            if changed:
                # Faqat muqova crossfade (pixmap asosida) — QGraphicsOpacity
                # effekti QGraphicsView proxy ichida kartani buzib chizadi!
                self.book_cover.fade_on_next = True
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

    def _play_current(self):
        """Pill (nom) bosildi — joriy tavsiya filmini darhol qo'yib beradi."""
        if self.rec_movies:
            self._play_movie(self.rec_movies[self.movie_idx])

    def _play_movie(self, item):
        if self._modal:
            self._modal.close_modal()
        from players.video import VideoPlayer
        old = getattr(self, "_player", None)
        if old is not None:
            old.stop_and_close()
        stats.event("content_open", id=item.get("id"),
                    title=item.get("title"), type=item.get("type"))
        self._player = VideoPlayer(self.api.play_url(item["id"]), item.get("title", ""))
        # "Media" reklama algoritmida kino boshida/o'rtasida/oxirida reklama
        # chiqadi (boshqa rejimlarda hook hech narsa qilmaydi).
        mgr = getattr(self.window(), "ad_manager", None)
        if mgr is not None:
            self._player.ad_hook = mgr.media_ad
        self._player.closed.connect(lambda: setattr(self, "_player", None))
        self._player.start()

    def _read_book(self):
        if self.rec_book:
            stats.event("content_open", id=self.rec_book.get("id"),
                        title=self.rec_book.get("title"),
                        type=self.rec_book.get("type"))
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
            f"#listenBtn:pressed {{ background: #B45309; }}"
            f"#readBtn {{ background: {c['accent']}; color: {c['accent_text']}; border: none;"
            f" border-radius: {T.RADIUS['button']}px; font-size: 24px; font-weight: 600; }}"
            f"#readBtn:hover {{ background: #1D4ED8; }}"
            f"#readBtn:pressed {{ background: #1E40AF; }}"
            f"#pArr:pressed {{ color: {c['accent']}; }}")


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
        # Sahifadan chiqilganda status so'rovi va aylanmalar to'xtaydi
        self.canvas.timer.stop()
        self.canvas.banner_timer.stop()
        self.canvas.rec_timer.stop()
        super().hideEvent(e)

    def _apply_status(self, data):
        # main.py WebSocket status_update'ni shu orqali uzatadi
        self.canvas._apply_status(data)
