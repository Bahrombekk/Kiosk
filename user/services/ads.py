"""
ads.py — Qalqib chiquvchi reklama tizimi (kiosk).

Server admin kiritgan rasm/video reklamalar belgilangan oraliqda — foydalanuvchi
qaysi bo'limda bo'lishidan qat'i nazar — oyna ustida popup bo'lib chiqadi,
teskari hisob bilan `duration` soniya ko'rinadi va O'ZI yopiladi (X yo'q,
tashqariga bosish ham yopmaydi).

  - MUHIM: popup media TAYYOR bo'lgandagina ochiladi (rasm oldindan yuklanadi,
    video birinchi kadr kelganda ko'rsatiladi). Fayl yo'q/tarmoq xato bo'lsa —
    keyingi reklama uriniladi; foydalanuvchi hech qachon bo'sh qora oynani
    ko'rmaydi.
  - Rasm: `duration` soniya (standart 10 s).
  - Video: ovozsiz; davomiylik admin tomonida fayldan avtomatik olinadi,
    teskari hisob shu vaqtdan boshlanadi; EndOfMedia kelsa ham yopiladi.
  - `start_time`/`end_time` (HH:MM) — faqat shu kunlik oraliqda chiqadi
    (yarim tundan o'tadigan 22:00–06:00 kabi oraliq ham to'g'ri).
  - Har reklamaning O'Z takrorlanish oralig'i bor (`interval_min` — admin
    dialogidagi «Har necha daqiqada»); berilmagan eski yozuvlar uchun umumiy
    `ad_interval_min` sozlamasi. Ikki reklama orasida kamida MIN_GAP_S pauza —
    yo'lovchining "badiga urmasin". Pleyer/o'quvchi/PIN/zastavka ochiq
    bo'lsa chiqmaydi.
"""
import logging
import time
from datetime import datetime

from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt, QThread, QTimer, QUrl, QRectF, QObject, pyqtSignal
from PyQt6.QtGui import QPixmap, QPainter, QPainterPath

from core import cache
from core import theme as T
from core.threads import track
from widgets.modal import Modal
from widgets.cover import _Fetcher

# Video reklamalar uchun (kadrlar QLabel'ga chiziladi). Modul bo'lmasa video
# reklamalar shunchaki o'tkazib yuboriladi.
try:
    from PyQt6.QtMultimedia import QMediaPlayer, QVideoSink
    _HAS_MM = True
except Exception:                                    # noqa: BLE001 — DLL ham
    _HAS_MM = False

log = logging.getLogger(__name__)

DEFAULT_INTERVAL_MIN = 5    # interval_min ham, umumiy sozlama ham bo'lmasa
FIRST_DELAY_S = 45          # ishga tushgandan keyin birinchi reklamagacha
MIN_GAP_S = 60              # ikki reklama orasidagi eng kam pauza
TICK_MS = 20 * 1000         # navbatni tekshirish qadami
IMAGE_DEFAULT_S = 10        # duration berilmagan rasm uchun
VIDEO_CAP_S = 600           # davomiyligi noma'lum video uchun himoya chegarasi
VIDEO_START_TIMEOUT_MS = 8000   # birinchi kadr shu vaqtda kelmasa — o'tkazamiz


class _AdsLoader(QThread):
    """Reklama ro'yxatini serverdan alohida oqimda oladi."""
    done = pyqtSignal(list)

    def __init__(self, api):
        super().__init__()
        self.api = api

    def run(self):
        try:
            self.done.emit(self.api.get_ads())
        except Exception:
            log.debug("Reklamalar yuklanmadi", exc_info=True)


class _AdMedia(QLabel):
    """Reklama media maydoni: rasm yoki video kadrlari, markazdan kesib
    to'ldiriladi, burchaklari yumaloq."""

    def __init__(self, w, h, radius):
        super().__init__()
        self.setFixedSize(w, h)
        self._radius = radius
        self._orig = None
        self.setStyleSheet(f"background: #0c1418; border-radius: {radius}px;")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_image(self, pm):
        self._orig = pm
        self._redraw()

    def _redraw(self):
        if not self._orig:
            return
        w, h = self.width(), self.height()
        scaled = self._orig.scaled(
            w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation)
        out = QPixmap(w, h)
        out.fill(Qt.GlobalColor.transparent)
        p = QPainter(out)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0, 0, w, h), self._radius, self._radius)
        p.setClipPath(clip)
        p.drawPixmap((w - scaled.width()) // 2,
                     (h - scaled.height()) // 2, scaled)
        p.end()
        self.setPixmap(out)


class AdPopup(Modal):
    """Bitta reklamaning qalqib chiquvchi oynasi.

    Yopish tugmasi YO'Q, tashqariga bosish ham yopmaydi — yuqori-o'ngdagi
    «Reklama · N s» teskari hisob tugagach (yoki video oxiriga yetgach)
    o'zi yopiladi.

    Video rejimda popup darhol ko'rsatilmaydi: birinchi kadr kelganda
    `ready` chiqadi (menejer shunda ko'rsatadi); kadr kelmasa `failed`."""

    ready = pyqtSignal()    # video: birinchi kadr keldi — ko'rsatish mumkin
    failed = pyqtSignal()   # video: boshlanmadi (404/tarmoq/kodek)

    def __init__(self, parent, ad, api, pixmap=None):
        # Panel — oyna kengligining ~62%, 16:9 (balandlikka sig'masa kichikroq)
        pw = max(480, int(parent.width() * 0.62))
        ph = int(pw * 9 / 16)
        maxh = int(parent.height() * 0.8)
        if ph > maxh:
            ph = maxh
            pw = int(ph * 16 / 9)
        super().__init__(parent, width=pw, height=ph)
        self.ad = ad
        self._vplayer = None
        self._vsink = None
        self._shown = False
        self._got_frame = False

        # X tugma butunlay olib tashlanadi (reklama yopib bo'lmaydi)
        self.close_btn.hide()

        # Media panelni to'liq egallaydi
        while self.body.count():
            self.body.takeAt(0)
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(0)
        self.media = _AdMedia(pw, ph, T.RADIUS["card"])
        self.body.addWidget(self.media)

        # «Reklama · N s» teskari hisob (media ustida, yuqori-o'ng)
        self.count_lbl = QLabel("", self.panel)
        self.count_lbl.setStyleSheet(
            f"background: rgba(15,20,30,0.62); color: #FFFFFF;"
            f" border-radius: {T.s(14)}px; padding: {T.s(6)}px {T.s(14)}px;"
            f" font-size: {T.s(16)}px; font-weight: 600;")
        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(1000)
        self._tick_timer.timeout.connect(self._tick)

        dur = ad.get("duration") or 0
        if pixmap is not None:                       # rasm (oldindan yuklangan)
            self.media.set_image(pixmap)
            self._total = max(3, dur or IMAGE_DEFAULT_S)
        else:                                        # video
            self._total = dur if dur > 0 else None   # None — hisob ko'rsatilmaydi
            self._play_video(api.ad_media_url(ad["id"]))
            # Birinchi kadr kechiksa — bu reklamani o'tkazib yuboramiz
            QTimer.singleShot(VIDEO_START_TIMEOUT_MS, self._check_started)

    # ---- Ko'rsatish / hisob ----
    def show_over(self, name="light"):
        self._shown = True
        super().show_over(name)
        if self._total:
            self._remaining = self._total
            self._update_count()
            self._tick_timer.start()
        else:
            # Davomiyligi noma'lum video: hisobsiz «Reklama» yorlig'i +
            # himoya chegarasi (EndOfMedia odatda oldin keladi)
            self.count_lbl.setText("Reklama")
            self._place_count()
            QTimer.singleShot(VIDEO_CAP_S * 1000, self.close_modal)

    def _tick(self):
        self._remaining -= 1
        if self._remaining <= 0:
            self.close_modal()
            return
        self._update_count()

    def _update_count(self):
        self.count_lbl.setText(f"Reklama · {self._remaining} s")
        self._place_count()

    def _place_count(self):
        self.count_lbl.adjustSize()
        self.count_lbl.move(
            self.panel.width() - self.count_lbl.width() - T.s(14), T.s(14))
        self.count_lbl.raise_()

    def mouseReleaseEvent(self, e):
        # Tashqariga bosish ham yopmaydi — reklama vaqti tugashini kutadi
        pass

    # ---- Video (QVideoSink kadrlari media maydoniga chiziladi) ----
    def _play_video(self, url):
        self._vplayer = QMediaPlayer(self)
        # Audio chiqish ulanmaydi — reklama ovozsiz (vagonda shovqin bo'lmasin)
        self._vsink = QVideoSink(self)
        self._vplayer.setVideoSink(self._vsink)
        self._vsink.videoFrameChanged.connect(self._on_frame)
        self._vplayer.mediaStatusChanged.connect(self._on_media_status)
        self._vplayer.errorOccurred.connect(self._on_error)
        self._vplayer.setSource(QUrl(url))
        self._vplayer.play()

    def _on_frame(self, frame):
        if not frame.isValid():
            return
        img = frame.toImage()
        if img.isNull():
            return
        self.media.set_image(QPixmap.fromImage(img))
        if not self._got_frame:
            self._got_frame = True
            self.ready.emit()

    def _check_started(self):
        if not self._got_frame and not self._shown:
            self.failed.emit()

    def _on_error(self, *_):
        if self._shown:
            self.close_modal()
        else:
            self.failed.emit()

    def _on_media_status(self, st):
        if _HAS_MM and st == QMediaPlayer.MediaStatus.EndOfMedia:
            if self._shown:
                self.close_modal()

    # ---- Yopish / tozalash ----
    def _stop_video(self):
        if self._vplayer is not None:
            try:
                self._vplayer.stop()
            except Exception:                        # noqa: BLE001
                pass
            self._vplayer.deleteLater()
            self._vplayer = None
            self._vsink = None

    def abort(self):
        """Ko'rsatilmagan popup'ni jim tozalaydi (closed signalisiz)."""
        self._tick_timer.stop()
        self._stop_video()
        self.hide()
        self.deleteLater()

    def close_modal(self):
        self._tick_timer.stop()
        self._stop_video()
        super().close_modal()


class AdManager(QObject):
    """Reklamalarni rejalashtiradi: ro'yxatni davriy yangilab, HAR REKLAMANING
    O'Z `interval_min` oralig'i bo'yicha vaqti kelganini popup qiladi.
    Media tayyor bo'lmasa (fayl yo'q, tarmoq xato) — keyingisini uriniladi."""

    REFRESH_MS = 5 * 60 * 1000     # ro'yxatni yangilash

    def __init__(self, window, api):
        super().__init__(window)
        self.win = window           # MainWindow (parent + holat tekshiruvlari)
        self.api = api
        self.ads = []
        self._last_shown = {}       # ad_id -> monotonic vaqt (oxirgi ko'rsatilgan)
        self._start_ts = None       # start() vaqti (birinchi reklama kechikishi)
        self._last_close_ts = 0     # oxirgi popup yopilgan vaqt (MIN_GAP uchun)
        self._popup = None          # hozir ochiq popup
        self._pending = None        # birinchi kadrini kutayotgan video popup
        self._fetch = None
        self._aloader = None
        self._refresh = QTimer(self)
        self._refresh.setInterval(self.REFRESH_MS)
        self._refresh.timeout.connect(self.reload)
        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(TICK_MS)
        self._tick_timer.timeout.connect(self._maybe_show)

    # ---- Hayot sikli ----
    def start(self):
        self._start_ts = time.monotonic()
        self.reload()
        self._refresh.start()
        self._tick_timer.start()

    def stop(self):
        self._refresh.stop()
        self._tick_timer.stop()
        if self._pending is not None:
            p, self._pending = self._pending, None
            p.abort()
        if self._popup is not None:
            p, self._popup = self._popup, None
            try:
                p.closed.disconnect(self._on_closed)
            except (TypeError, RuntimeError):
                pass
            try:
                p.close_modal()
            except RuntimeError:
                pass   # allaqachon o'chirilgan

    @property
    def _active(self):
        """stop() dan keyin kechikkan signal-callback'lar ish boshlamasin."""
        return self._refresh.isActive()

    def reload(self):
        self._aloader = track(_AdsLoader(self.api))
        self._aloader.done.connect(self._on_ads)
        self._aloader.start()

    def _on_ads(self, ads):
        self.ads = [a for a in ads if a.get("media_path")]

    # ---- Takrorlanish oralig'i ----
    @staticmethod
    def _global_interval_min():
        """Umumiy sozlama (interval_min berilmagan eski reklamalar uchun)."""
        hit = cache.load_json("settings")
        mins = None
        if hit:
            try:
                mins = float(hit[0].get("ad_interval_min"))
            except (TypeError, ValueError):
                mins = None
        if not mins or mins <= 0:
            mins = DEFAULT_INTERVAL_MIN
        return mins

    def _ad_interval_s(self, ad):
        """Shu reklama har necha SONIYADA takrorlanishi kerak."""
        try:
            mins = float(ad.get("interval_min") or 0)
        except (TypeError, ValueError):
            mins = 0
        if mins <= 0:
            mins = self._global_interval_min()
        return mins * 60

    # ---- Vaqt oralig'i ----
    @staticmethod
    def _hhmm(t):
        try:
            h, m = str(t).split(":")
            return int(h) * 60 + int(m)
        except (ValueError, AttributeError):
            return None

    @classmethod
    def _in_window(cls, ad, now_min):
        st = cls._hhmm(ad.get("start_time"))
        en = cls._hhmm(ad.get("end_time"))
        if st is None or en is None:
            return True                       # oraliq berilmagan — doim
        if st <= en:
            return st <= now_min < en
        return now_min >= st or now_min < en  # yarim tundan o'tadi

    def _eligible(self):
        now = datetime.now()
        nm = now.hour * 60 + now.minute
        out = [a for a in self.ads if self._in_window(a, nm)]
        if not _HAS_MM:   # multimedia yo'q — video reklamalarni tashlab ketamiz
            out = [a for a in out if a.get("media_type") != "video"]
        return out

    # ---- Ko'rsatish ----
    def _busy(self):
        """Hozir reklama chiqarish noo'rin: pleyer/o'quvchi ochiq, zastavka,
        PIN oynasi yoki server bilan aloqa yo'q (media yuklab bo'lmaydi)."""
        try:
            media_open = self.win._media_open()
        except Exception:                            # noqa: BLE001
            media_open = False
        return (media_open
                or self.win.saver.isVisible()
                or getattr(self.win, "_pin_open", False)
                or not getattr(self.win, "connected", False))

    def _maybe_show(self):
        """Har TICK: vaqti kelgan reklamalarni topib, eng "qarzdorini" chiqaradi.

        Reklama "vaqti keldi" deyiladi: oxirgi ko'rsatilganidan beri o'zining
        `interval_min` daqiqasi o'tgan bo'lsa (hali ko'rsatilmagani — darhol).
        Ikki popup orasida kamida MIN_GAP_S saqlanadi."""
        if self._popup is not None or self._pending is not None:
            return                       # allaqachon ochiq/tayyorlanmoqda
        now = time.monotonic()
        if self._start_ts is None or now - self._start_ts < FIRST_DELAY_S:
            return                       # endigina ishga tushdi — shoshilmaymiz
        if now - self._last_close_ts < MIN_GAP_S:
            return                       # oldingi reklama endigina yopildi
        if self._busy():
            return
        due = []
        for ad in self._eligible():
            last = self._last_shown.get(ad["id"])
            if last is None or now - last >= self._ad_interval_s(ad):
                due.append((last or 0, ad))
        if not due:
            return
        due.sort(key=lambda t: t[0])     # eng uzoq kutgani birinchi
        self._try_candidates([ad for _, ad in due])

    def _try_candidates(self, cands):
        """Nomzodlarni birma-bir uriniladi; media tayyor bo'lgani ko'rsatiladi."""
        if not self._active:
            return
        if not cands:
            return                       # birortasi ham ochilmadi — keyingi tick
        ad, rest = cands[0], cands[1:]
        if ad.get("media_type") == "video":
            pop = AdPopup(self.win, ad, self.api)
            self._pending = pop
            pop.ready.connect(lambda ad=ad: self._on_video_ready(ad))
            pop.failed.connect(lambda ad=ad, rest=rest:
                               self._on_video_fail(ad, rest))
        else:
            f = track(_Fetcher(self.api.ad_media_url(ad["id"])))
            self._fetch = f
            f.done.connect(lambda data, _c, ad=ad, rest=rest:
                           self._on_image(ad, rest, data))
            f.fail.connect(lambda ad=ad, rest=rest:
                           self._on_media_fail(ad, rest))
            f.start()

    def _on_image(self, ad, rest, data):
        if not self._active:
            return
        pm = QPixmap()
        pm.loadFromData(data)
        if pm.isNull():
            self._on_media_fail(ad, rest)
            return
        self._present(AdPopup(self.win, ad, self.api, pixmap=pm), ad)

    def _on_video_ready(self, ad):
        pop, self._pending = self._pending, None
        if pop is None or not self._active:
            if pop is not None:
                pop.abort()
            return
        self._present(pop, ad)

    def _on_video_fail(self, ad, rest):
        pop, self._pending = self._pending, None
        if pop is not None:
            pop.abort()
        self._on_media_fail(ad, rest)

    def _on_media_fail(self, ad, rest):
        log.warning("Reklama #%s media ochilmadi — keyingisi uriniladi",
                    ad.get("id"))
        # Muvaffaqiyatsiz urinish ham "ko'rsatildi" deb belgilanadi — har 20
        # soniyada qayta-qayta 404 so'ramaslik uchun (o'z oralig'ida qaytadi).
        self._last_shown[ad["id"]] = time.monotonic()
        self._try_candidates(rest)

    def _present(self, pop, ad):
        self._popup = pop
        pop.closed.connect(self._on_closed)
        pop.show_over(self.win.theme_name)
        self._last_shown[ad["id"]] = time.monotonic()
        log.info("Reklama ko'rsatildi: #%s %r (%s s, har %s daq)",
                 ad.get("id"), ad.get("title"), ad.get("duration"),
                 ad.get("interval_min") or "std")

    def _on_closed(self):
        self._popup = None
        self._last_close_ts = time.monotonic()
