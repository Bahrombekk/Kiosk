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

REJALASHTIRISH — "global kadans + adolatli rotatsiya" (yo'lovchining
"badiga urmasin"; reklamalar soni 5 ta ham, 50 ta ham bo'lsin, foydalanuvchi
ko'radigan popup chastotasi O'ZGARMAYDI):

  - Umumiy `ad_interval_min` sozlamasi (standart 5 daq) — popup "slot"lari
    oralig'i. Har slotda faqat BITTA reklama chiqadi; slotlar to'planmaydi
    (band paytda o'tib ketgan slotlar uchun keyin ketma-ket popup yog'maydi).
  - Slotda QAYSI reklama chiqishini admin tanlagan ALGORITM belgilaydi
    (`ad_algorithm` sozlamasi — server Sozlamalar sahifasida):
      * weighted (standart) — "o'z intervaliga nisbatan eng ko'p kutgani":
        score = kutgan_vaqt / interval_min. Har reklamaning `interval_min`i
        (admin dialogidagi «Har necha daqiqada») chastota VAZNI — kichik
        intervalli tez-tez, kattasi kamroq chiqadi; score < 1 bo'lgan
        (yaqinda ko'rsatilgan) reklama qayta chiqmaydi.
      * queue — qat'iy navbat: har slotda ro'yxatdagi keyingi reklama
        ("har N daqiqada navbat bilan bittadan"); reklamalarning o'z
        `interval_min`lari e'tiborga olinmaydi, chastotani faqat global
        kadans belgilaydi.
      * random — navbat kabi, lekin tartib har slotda tasodifiy; hozirgina
        chiqqan reklama ketma-ket takrorlanmaydi.
      * media — popup BOSHQA JOYDA UMUMAN chiqmaydi; reklama faqat kino
        atrofida ko'rsatiladi: boshida (pre-roll — kino reklamadan keyin
        boshlanadi), o'rtasida (mid-roll — kino pauza qilinadi) va oxirida
        (end-roll). Har nuqtada navbatdagi BITTA reklama (aylanma navbat).
        Pleyer ustida alohida to'liq ekran qatlamda chiqadi (VLC videoni
        native oynaga chizadi — oddiy bola-widget ko'rinmasdi). Qarang:
        media_ad() va players/video.py dagi ad_hook.
  - Faollik hurmati: foydalanuvchi ekran bilan faol ishlayotgan bo'lsa
    (oxirgi IDLE_GRACE_S ichida teginish), popup pauzani kutadi; ammo
    MAX_DEFER_S dan ortiq kechiktirilmaydi (uzoq faol seansda ham chiqadi).
  - Yangi tashrif imtiyozi: zastavka yopilib yangi odam kelganda dastlabki
    SESSION_GRACE_S davomida reklama chiqmaydi (window._dismiss_saver ->
    on_session_start).
  - Ikki popup orasida kamida MIN_GAP_S pauza. Pleyer/o'quvchi/PIN/zastavka
    ochiq bo'lsa chiqmaydi.
"""
import logging
import random
import time
from datetime import datetime

from PyQt6.QtWidgets import QLabel, QWidget
from PyQt6.QtCore import Qt, QThread, QTimer, QUrl, QRectF, QObject, pyqtSignal
from PyQt6.QtGui import QPixmap, QPainter, QPainterPath

from core import cache
from core import theme as T
from core.threads import track
from services import stats
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
IDLE_GRACE_S = 25           # oxirgi teginishdan shuncha o'tmagan — kutamiz
MAX_DEFER_S = 180           # faollik tufayli slotni eng ko'p kechiktirish
SESSION_GRACE_S = 60        # zastavkadan keyin yangi odamga "tinch" vaqt
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
            # Sozlamalar keshi ham shu yerda yangilanadi — admin algoritm yoki
            # oraliqni o'zgartirsa, kiosk REFRESH_MS ichida ilg'aydi.
            try:
                self.api.get_settings()
            except Exception:                        # noqa: BLE001
                pass                                 # oflayn — eski kesh qoladi
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
            self._play_video(api.ad_media_play_url(ad["id"]))
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


class _MediaAdLayer(QWidget):
    """Kino pleyeri USTIDA reklama ko'rsatish uchun to'liq ekran qatlam.

    VLC videoni o'z native HWND'iga chizadi — pleyerning bola-widgeti uning
    ostida qolib ketadi (pleyer boshqaruvi ham shu sababdan alohida oyna).
    Shuning uchun reklama popup'i shu mustaqil top-level qatlamga joylanadi;
    qatlam pleyer geometriyasini qoplaydi va ad yopilgach o'chiriladi."""

    def __init__(self, geometry):
        super().__init__(None, Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background: rgba(0, 0, 0, 0.85);")
        self.setGeometry(geometry)


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
        self._next_slot_ts = None   # keyingi popup sloti (monotonic)
        self._last_close_ts = 0     # oxirgi popup yopilgan vaqt (MIN_GAP uchun)
        self._popup = None          # hozir ochiq popup
        self._pending = None        # birinchi kadrini kutayotgan video popup
        self._media_ctx = None      # (qatlam, on_done) — kino atrofidagi ad
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
        self._next_slot_ts = time.monotonic() + FIRST_DELAY_S
        self.reload()
        self._refresh.start()
        self._tick_timer.start()

    def on_session_start(self):
        """Zastavka yopildi — yangi tashrif boshlandi (window chaqiradi).
        Yangi odamga darhol reklama urilmasin: slot kamida SESSION_GRACE_S
        keyinga suriladi (lekin allaqachon undan uzoqroq bo'lsa — tegilmaydi)."""
        if self._next_slot_ts is not None:
            self._next_slot_ts = max(self._next_slot_ts,
                                     time.monotonic() + SESSION_GRACE_S)

    def stop(self):
        self._refresh.stop()
        self._tick_timer.stop()
        self._finish_media_ctx(run_done=False)   # kino baribir yopilmoqda
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
        # Banner-only reklamalar popup bo'lib chiqmaydi — ular bosh sahifa
        # bannerida aylanadi (screens/home.py); "both" ikkala joyda ham.
        self.ads = [a for a in ads if a.get("media_path")
                    and (a.get("placement") or "popup") in ("popup", "both")]

    # ---- Takrorlanish oralig'i ----
    @staticmethod
    def _global_interval_min():
        """Umumiy `ad_interval_min` sozlamasi — ikki vazifada: (1) popup
        slotlari oralig'i (global kadans), (2) interval_min berilmagan eski
        reklamalar uchun standart interval."""
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
        """Har TICK: global slot vaqti kelganida BITTA reklama chiqaradi.

        Slot oralig'i — umumiy `ad_interval_min` sozlamasi; reklamalar soni
        qancha bo'lmasin, popup chastotasi shu bilan chegaralanadi. Slotda
        qaysi reklama chiqishini admin tanlagan algoritm belgilaydi (qarang:
        _pick_candidates — queue/random/weighted). Foydalanuvchi faol bo'lsa,
        popup pauzagacha (eng ko'pi MAX_DEFER_S) kechiktiriladi."""
        if self._popup is not None or self._pending is not None:
            return                       # allaqachon ochiq/tayyorlanmoqda
        if self._popup_algorithm() is None:
            return   # faqat 'media' tanlangan — popup yo'q, reklama kino atrofida
        now = time.monotonic()
        if self._next_slot_ts is None or now < self._next_slot_ts:
            return                       # slot vaqti hali kelmadi
        if now - self._last_close_ts < MIN_GAP_S:
            return                       # oldingi reklama endigina yopildi
        if self._busy():
            return
        # Faollik hurmati: odam hozir ekran bilan ishlayapti — tabiiy pauzani
        # kutamiz; lekin slot MAX_DEFER_S dan ortiq kechikkan bo'lsa chiqamiz
        # (aks holda uzluksiz aylanayotgan odam reklamani umuman ko'rmaydi).
        last_act = getattr(self.win, "last_activity", 0)
        if (now - last_act < IDLE_GRACE_S
                and now - self._next_slot_ts < MAX_DEFER_S):
            return
        cands = self._pick_candidates(now)
        if not cands:
            return                       # hammasi yaqinda ko'rsatilgan
        self._try_candidates(cands)

    # Popup tanlash usullari prioriteti — bir nechtasi belgilangan bo'lsa
    # birinchisi ishlatiladi (`media` alohida joylashuv, bunga kirmaydi).
    _POPUP_ALGOS = ("weighted", "queue", "random")

    @staticmethod
    def _algorithms():
        """Admin tanlagan algoritmlar to'plami (`ad_algorithm` sozlamasi —
        vergul bilan saqlanadi; eski yagona qiymat ham mos keladi)."""
        hit = cache.load_json("settings")
        raw = (hit[0].get("ad_algorithm") or "") if hit else ""
        sel = {x.strip() for x in raw.split(",") if x.strip()}
        return sel & {"weighted", "queue", "random", "media"}

    @classmethod
    def _popup_algorithm(cls):
        """Popup slotida qaysi tanlov usuli ishlaydi (prioritet bo'yicha
        birinchi belgilangani). Faqat 'media' tanlangan bo'lsa None —
        popup butunlay chiqmaydi. Hech narsa tanlanmagan bo'lsa 'weighted'."""
        sel = cls._algorithms()
        for a in cls._POPUP_ALGOS:
            if a in sel:
                return a
        return None if sel else "weighted"

    @classmethod
    def _media_enabled(cls):
        """Kino atrofida (pre/mid/end) reklama ko'rsatilsinmi."""
        return "media" in cls._algorithms()

    def _pick_candidates(self, now):
        """Slot uchun nomzodlar ro'yxati: birinchisi ko'rsatiladi, qolganlari
        media xatosida zaxira. Tartibni admin tanlagan algoritm belgilaydi
        (qarang: modul sarlavhasi — queue / random / weighted)."""
        algo = self._popup_algorithm()
        elig = self._eligible()
        if algo == "queue":
            # Eng uzoq ko'rsatilmagani birinchi (hali ko'rsatilmaganlar — 0 —
            # yuklash, ya'ni id tartibida oldinda) = qat'iy aylanma navbat.
            return sorted(elig, key=lambda a: (self._last_shown.get(a["id"]) or 0,
                                               a.get("id") or 0))
        if algo == "random":
            pool = list(elig)
            random.shuffle(pool)
            if len(pool) > 1 and self._last_shown:
                # Hozirgina chiqqani ketma-ket takrorlanmasin — eng orqaga
                prev = max(self._last_shown, key=self._last_shown.get)
                pool.sort(key=lambda a: a.get("id") == prev)
            return pool
        # weighted (standart): eng "haqdor"i birinchi — score = kutgan vaqt /
        # o'z intervali; score < 1 (o'z oralig'i o'tmagan) chiqarilmaydi.
        fresh, scored = [], []
        for ad in elig:
            last = self._last_shown.get(ad["id"])
            if last is None:
                fresh.append(ad)
                continue
            score = (now - last) / self._ad_interval_s(ad)
            if score >= 1:
                scored.append((score, ad))
        scored.sort(key=lambda t: t[0], reverse=True)
        return fresh + [ad for _, ad in scored]

    # ---- Kino atrofidagi reklama (media rejimi) ----
    def media_ad(self, host, stage, on_done):
        """Kino atrofida BITTA reklama ko'rsatadi (players/video.py chaqiradi).

        host  — pleyer oynasi (qatlam uning geometriyasini qoplaydi);
        stage — "pre" / "mid" / "end" (statistikaga yoziladi);
        on_done — reklama yopilganda YOKI ko'rsatib bo'lmasa (mos reklama
        yo'q, media xato, boshqa rejim) chaqiriladi — kino HECH QACHON
        reklamaga qarab qolib ketmaydi.

        Tanlov — aylanma navbat (eng uzoq ko'rsatilmagani), 'media' algoritmi
        belgilangandagina ishlaydi."""
        if (not self._media_enabled() or not self._active
                or self._popup is not None or self._pending is not None):
            on_done()
            return
        if stage == "pre" and time.monotonic() - self._last_close_ts < MIN_GAP_S:
            # Foydalanuvchi kinolarni ketma-ket ochib-yopsa, har ochilishda
            # pre-roll urilmasin — oxirgi reklamadan kamida MIN_GAP_S o'tsin
            # (mid/end bunga kirmaydi: ular kino davomida tabiiy siyrak).
            on_done()
            return
        cands = sorted(self._eligible(),
                       key=lambda a: (self._last_shown.get(a["id"]) or 0,
                                      a.get("id") or 0))
        if len(cands) < len(self.ads):
            # Diagnostika: nimaga ba'zi reklamalar chiqmayapti? — vaqt
            # oralig'i (start/end_time) yoki video/multimedia filtri.
            log.info("Media reklama (%s): %d/%d mos — qolganlari vaqt "
                     "oralig'i/turi bo'yicha filtrlangan",
                     stage, len(cands), len(self.ads))
        if not cands:
            on_done()
            return
        self._media_ctx = (_MediaAdLayer(host.geometry()), on_done, stage)
        self._try_candidates(cands)

    def _popup_parent(self):
        return self._media_ctx[0] if self._media_ctx else self.win

    def _finish_media_ctx(self, run_done=True):
        """Media kontekstni yopadi: qatlam o'chiriladi, kino davom ettiriladi."""
        if self._media_ctx is None:
            return
        layer, done, _ = self._media_ctx
        self._media_ctx = None
        layer.close()
        layer.deleteLater()
        if run_done:
            try:
                done()
            except RuntimeError:
                pass   # pleyer allaqachon yopilgan bo'lishi mumkin

    def _try_candidates(self, cands):
        """Nomzodlarni birma-bir uriniladi; media tayyor bo'lgani ko'rsatiladi."""
        if not self._active or not cands:
            # Media rejimida kino javob kutmoqda — qo'yib yuboramiz
            self._finish_media_ctx()
            return
        ad, rest = cands[0], cands[1:]
        if ad.get("media_type") == "video":
            pop = AdPopup(self._popup_parent(), ad, self.api)
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
        self._present(AdPopup(self._popup_parent(), ad, self.api, pixmap=pm), ad)

    def _on_video_ready(self, ad):
        pop, self._pending = self._pending, None
        if pop is None or not self._active:
            if pop is not None:
                pop.abort()
            self._finish_media_ctx()
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
        if self._media_ctx is not None:
            # Kino ustidagi qatlam: avval qora fon, ustida popup
            layer = self._media_ctx[0]
            layer.show()
            layer.raise_()
        pop.show_over(self.win.theme_name)
        now = time.monotonic()
        self._last_shown[ad["id"]] = now
        # Keyingi global slot — o'tib ketgan slotlar TO'PLANMAYDI: band davrdan
        # keyin ham bitta popup chiqadi va hisob qaytadan boshlanadi.
        self._next_slot_ts = now + self._global_interval_min() * 60
        # Proof-of-play: har bir namoyish statistikaga yoziladi (admin
        # «Statistika» sahifasida reklama bo'yicha hisobot ko'rinadi).
        placement = self._media_ctx[2] if self._media_ctx else "popup"
        stats.event("ad_play", ad_id=ad.get("id"), title=ad.get("title"),
                    media_type=ad.get("media_type"), placement=placement)
        log.info("Reklama ko'rsatildi: #%s %r (%s s, %s)",
                 ad.get("id"), ad.get("title"), ad.get("duration"), placement)

    def _on_closed(self):
        self._popup = None
        self._last_close_ts = time.monotonic()
        self._finish_media_ctx()   # kino kutayotgan bo'lsa — davom ettiramiz
