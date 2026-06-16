"""
player.py — To'liq ekran video pleyer (LibVLC asosida, TZ 8.6).

Imkoniyatlari:
  - to'liq ekran o'ynatish (striming, HTTP Range orqali seek)
  - boshqaruv: X, 10s orqaga/oldinga, play/pauza, progress bar, vaqt, ovoz
  - bufer: tarmoq qisqa uzilsa to'xtamasligi uchun network-caching
  - boshqaruv bir necha soniyada avtomatik yashiriladi, sichqoncha tegsa qaytadi

Foydalanish:
  pl = VideoPlayer(stream_url, "Baron")
  pl.start()
"""
import sys
import vlc
from PyQt6.QtWidgets import (QWidget, QFrame, QHBoxLayout, QVBoxLayout,
                             QPushButton, QLabel, QSlider)
from PyQt6.QtCore import Qt, QTimer, QEvent, pyqtSignal, QSize

from core import theme as T
from core.i18n import tr
from widgets.icons import svg_icon, svg_pixmap
from widgets.spinner import Spinner


def _fmt(ms):
    """Millisekundni HH:MM:SS yoki MM:SS ko'rinishiga keltiradi."""
    if ms is None or ms < 0:
        ms = 0
    s = ms // 1000
    h, m, sec = s // 3600, (s % 3600) // 60, s % 60
    return f"{h:02d}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


class VideoPlayer(QWidget):
    closed = pyqtSignal()

    # Bufer: 3 soniyalik tarmoq uzilishiga chidaydi (TZ 6.2 / 12.2)
    NETWORK_CACHING_MS = 3000

    def __init__(self, stream_url, title="", host=None):
        super().__init__()
        self.stream_url = stream_url
        self.title = title
        self._host = host
        self._dragging = False
        # Kino atrofidagi reklama (ixtiyoriy): ochuvchi ekran AdManager.media_ad
        # ni o'rnatadi — callable(host, stage, on_done). "media" algoritmida
        # kino boshida (pre), o'rtasida (mid) va oxirida (end) bitta reklama
        # chiqadi; boshqa rejimlarda on_done darhol qaytadi va hech narsa
        # o'zgarmaydi.
        self.ad_hook = None
        self._ad_open = False       # reklama paytida boshqaruv chiqmasin
        self._ad_mid_done = False   # mid-roll faqat bir marta
        self._ad_end_done = False   # end-roll faqat bir marta

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet("background: #000000;")

        # VLC dvigatel.
        #   --quiet               : info/ogohlantirish loglarini konsolga chiqarmaslik
        #   --no-video-title-show : video boshida nom yozuvini ko'rsatmaslik
        self._instance = vlc.Instance(
            "--quiet", "--no-video-title-show",
            f"--network-caching={self.NETWORK_CACHING_MS}")
        self._mp = self._instance.media_player_new()

        self._build_ui()

        # Boshqaruvni davriy yangilash
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(500)

        # Boshqaruvni avtomatik yashirish
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._hide_controls)
        self.setMouseTracking(True)

    # ---------- UI ----------
    def _build_ui(self):
        # Video yuzasi (VLC shu oynaga chizadi)
        self.video = QFrame(self)
        self.video.setStyleSheet("background: #000000;")
        # Sichqoncha tegsa boshqaruv qaytsin: harakat hodisasi ota-oynaga
        # (player) o'tib, mouseMoveEvent ishga tushadi.
        self.video.setMouseTracking(True)

        # Boshqaruv qatlami — alohida shaffof "ustda turuvchi" oyna.
        # VLC Windows'da videoni o'z native HWND'iga chizadi: agar boshqaruvni
        # oddiy bola-widget qilsak, video uni berkitadi. Shu sabab boshqaruv
        # alohida top-level shaffof oyna (DWM uni video ustiga shaffof
        # joylashtiradi) — video ko'rinadi, tugmalar bosiladi.
        self.controls = QWidget(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool)
        self.controls.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.controls.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        # Esc kabi klavishlar asosiy oynada qolsin (boshqaruv fokus olmasin)
        self.controls.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.controls.setMouseTracking(True)
        self.controls.installEventFilter(self)
        c = QVBoxLayout(self.controls)
        c.setContentsMargins(0, 0, 0, 0)
        c.setSpacing(0)

        # Yuqori panel (X + sarlavha) — ochiq rangli video ustida ham o'qilsin
        # uchun yarim shaffof to'q "scrim" fon.
        self.top_bar = QFrame()
        self.top_bar.setObjectName("topBar")
        top = QHBoxLayout(self.top_bar)
        top.setContentsMargins(T.s(24), T.s(16), T.s(24), T.s(16))
        top.setSpacing(T.s(16))
        self.x_btn = self._round_btn("", T.s(60), icon="x")
        self.x_btn.clicked.connect(self.stop_and_close)
        self.title_lbl = QLabel(self.title)
        self.title_lbl.setStyleSheet(
            f"color:#FFFFFF; font-size:{T.s(22)}px; font-weight:600; background:transparent;")
        top.addWidget(self.x_btn)
        top.addWidget(self.title_lbl)
        top.addStretch(1)
        c.addWidget(self.top_bar)

        c.addStretch(1)

        # Markaz: bufer indikatori (oq spinner + matn) + boshqaruv tugmalari
        self.buffering = QWidget()
        self.buffering.setStyleSheet("background: transparent;")
        _brow = QHBoxLayout(self.buffering)
        _brow.setContentsMargins(0, 0, 0, 0)
        _brow.setSpacing(T.s(12))
        _brow.addStretch(1)
        self._buf_spin = Spinner(size=T.s(28), line=T.s(3), color="#FFFFFF")
        _buf_lbl = QLabel(tr("common.loading"))
        _buf_lbl.setStyleSheet(
            f"color: #FFFFFF; font-size: {T.s(22)}px; font-weight:600;"
            f" background: transparent;")
        _brow.addWidget(self._buf_spin)
        _brow.addWidget(_buf_lbl)
        _brow.addStretch(1)
        self._buf_spin.start()   # parent hide bo'lganda pauza, show'da davom
        self.buffering.hide()
        c.addWidget(self.buffering)

        center = QHBoxLayout()
        center.setSpacing(T.s(28))
        center.addStretch(1)
        self.back_btn = self._round_btn("« 10", T.s(72))
        self.play_btn = self._round_btn("", T.s(96), icon="pause")
        self.fwd_btn = self._round_btn("10 »", T.s(72))
        self.back_btn.clicked.connect(lambda: self._seek_relative(-10000))
        self.play_btn.clicked.connect(self.toggle_play)
        self.fwd_btn.clicked.connect(lambda: self._seek_relative(+10000))
        for b in (self.back_btn, self.play_btn, self.fwd_btn):
            center.addWidget(b)
        center.addStretch(1)
        c.addLayout(center)

        c.addStretch(1)

        # Pastki panel: vaqt | progress | umumiy | ovoz (scrim fon)
        self.bottom_bar = QFrame()
        self.bottom_bar.setObjectName("bottomBar")
        bottom = QHBoxLayout(self.bottom_bar)
        bottom.setContentsMargins(T.s(28), T.s(18), T.s(28), T.s(22))
        bottom.setSpacing(T.s(14))
        self.cur_lbl = QLabel("00:00")
        self.tot_lbl = QLabel("00:00")
        for l in (self.cur_lbl, self.tot_lbl):
            l.setStyleSheet(f"color:#FFFFFF; font-size:{T.s(16)}px; background:transparent;")

        self.progress = QSlider(Qt.Orientation.Horizontal)
        self.progress.setObjectName("seekBar")
        self.progress.setRange(0, 1000)
        self.progress.sliderPressed.connect(lambda: setattr(self, "_dragging", True))
        self.progress.sliderReleased.connect(self._on_seek)

        self.vol_lbl = QLabel()
        self.vol_lbl.setPixmap(svg_pixmap("volume-2", "#FFFFFF", T.s(22)))
        self.vol_lbl.setStyleSheet("background:transparent;")
        self.vol = QSlider(Qt.Orientation.Horizontal)
        self.vol.setObjectName("volBar")
        self.vol.setRange(0, 100)
        self.vol.setValue(80)
        self.vol.setFixedWidth(T.s(140))
        self.vol.valueChanged.connect(self._mp.audio_set_volume)

        bottom.addWidget(self.cur_lbl)
        bottom.addWidget(self.progress, 1)
        bottom.addWidget(self.tot_lbl)
        bottom.addSpacing(T.s(16))
        bottom.addWidget(self.vol_lbl)
        bottom.addWidget(self.vol)
        c.addWidget(self.bottom_bar)

        # Scrim fon + slayder ko'rinishi (sensorli ekran uchun yo'g'onroq).
        gh, hh = T.s(6), T.s(18)   # groove balandligi, handle o'lchami
        self.controls.setStyleSheet(
            "#topBar { background: rgba(0,0,0,0.45); }"
            "#bottomBar { background: rgba(0,0,0,0.55); }"
            f"QSlider::groove:horizontal {{ height: {gh}px; border-radius: {gh // 2}px;"
            "  background: rgba(255,255,255,0.30); }"
            f"QSlider::sub-page:horizontal {{ height: {gh}px; border-radius: {gh // 2}px;"
            "  background: #2563EB; }"
            f"QSlider::handle:horizontal {{ width: {hh}px; height: {hh}px;"
            f"  margin: {-(hh // 2 - gh // 2)}px 0; border-radius: {hh // 2}px;"
            "  background: #FFFFFF; }")

    def _round_btn(self, text, size, icon=None):
        b = QPushButton(text)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setFixedSize(size, size)
        if icon:
            b.setIcon(svg_icon(icon, "#FFFFFF", 64))
            b.setIconSize(QSize(int(size * 0.42), int(size * 0.42)))
        b.setStyleSheet(
            f"QPushButton {{ background: rgba(0,0,0,0.45); color:#FFFFFF;"
            f" border:none; border-radius:{size // 2}px; font-size:{T.s(20)}px;"
            f" font-weight:600; }}"
            f"QPushButton:hover {{ background: rgba(37,99,235,0.85); }}"
            f"QPushButton:pressed {{ background: rgba(37,99,235,1.0); }}")
        return b

    def _set_play_icon(self, name):
        # _refresh har yarim soniyada chaqiriladi — ikonkani keshlaymiz.
        if getattr(self, "_play_icon_name", None) == name:
            return
        self._play_icon_name = name
        self.play_btn.setIcon(svg_icon(name, "#FFFFFF", 64))

    # ---------- O'ynatish ----------
    def start(self):
        from core.overlay import show_over_host
        show_over_host(self, self._host)
        self._media = self._instance.media_new(self.stream_url)
        self._mp.set_media(self._media)
        # Video chiqarish oynasini ulash (platformaga bog'liq)
        win_id = int(self.video.winId())
        if sys.platform.startswith("win"):
            self._mp.set_hwnd(win_id)
        elif sys.platform == "darwin":
            self._mp.set_nsobject(win_id)
        else:
            self._mp.set_xwindow(win_id)
        # VLC video oynasi sichqoncha/klavishlarni o'zi ushlab qolmasin —
        # aks holda event'lar Qt'ga yetmaydi: boshqaruv yashirilgach qaytmaydi
        # va X tugma bosilmaydi (kiosk: chiqib bo'lmay qoladi).
        self._mp.video_set_mouse_input(False)
        self._mp.video_set_key_input(False)
        self._mp.audio_set_volume(self.vol.value())
        if self.ad_hook:
            # Pre-roll: kino reklamadan KEYIN boshlanadi (qora pleyer ustida
            # reklama qatlami). Mos reklama bo'lmasa yoki media ochilmasa
            # on_done darhol chaqiriladi — kino kechikmaydi.
            self._begin_ad("pre", self._begin_play)
        else:
            self._begin_play()

    def _begin_play(self):
        if getattr(self, "_closing", False):
            return
        self._mp.play()
        self.setFocus()
        self._show_controls()

    # ---------- Kino atrofidagi reklama ----------
    def _begin_ad(self, stage, after):
        """Reklamani so'raydi; tugagach (yoki chiqmasa) `after` davom etadi.
        Hook xato bersa ham kino to'xtab qolmaydi."""
        self._ad_open = True
        self.controls.hide()   # reklama ustiga boshqaruv chiqmasin

        def done():
            self._ad_open = False
            after()

        try:
            self.ad_hook(self, stage, done)
        except Exception:                            # noqa: BLE001
            done()

    def _resume_after_ad(self):
        """Mid-roll yopildi — kino pauzadan davom etadi."""
        if not getattr(self, "_closing", False):
            self._mp.set_pause(0)
            self._show_controls()

    def _after_end_ad(self):
        if not getattr(self, "_closing", False):
            self._show_controls()   # tugagan ekran (qayta/chiqish) qaytadi

    def keyPressEvent(self, e):
        # Klaviatura bilan ham chiqish/boshqaruv (kiosk uchun zaxira yo'l).
        if e.key() == Qt.Key.Key_Escape:
            self.stop_and_close()
        elif e.key() == Qt.Key.Key_Space:
            self.toggle_play()
        elif e.key() == Qt.Key.Key_Left:
            self._seek_relative(-10000)
        elif e.key() == Qt.Key.Key_Right:
            self._seek_relative(+10000)
        else:
            super().keyPressEvent(e)

    def toggle_play(self):
        state = self._mp.get_state()
        if state in (vlc.State.Ended, vlc.State.Stopped):
            # Video tugagan/to'xtagan — boshidan qaytadan o'ynatamiz.
            self._mp.set_media(self._media)
            self._mp.play()
        else:
            self._mp.pause()  # play<->pause almashtiradi
        self._show_controls()

    def _seek_relative(self, delta_ms):
        t = self._mp.get_time()
        length = self._mp.get_length()
        new_t = max(0, t + delta_ms)
        if length > 0:
            new_t = min(new_t, length)
        self._mp.set_time(int(new_t))
        self._show_controls()

    def _on_seek(self):
        length = self._mp.get_length()
        if length > 0:
            self._mp.set_time(int(length * self.progress.value() / 1000))
        self._dragging = False

    def _refresh(self):
        state = self._mp.get_state()
        # Yuklanish/bufer holati — indikator ko'rsatamiz va boshqaruv
        # yashirilmasin (foydalanuvchi nimani kutayotganini bilsin).
        loading = state in (vlc.State.Opening, vlc.State.Buffering)
        self.buffering.setVisible(loading)
        if loading:
            self._show_controls()

        # play / pauza / qayta o'ynatish belgisi
        if state == vlc.State.Ended:
            self._set_play_icon("rotate-ccw")
            self._show_controls()           # tugagach — chiqish/qayta uchun
        elif state == vlc.State.Playing:
            self._set_play_icon("pause")
        else:
            self._set_play_icon("play")

        length = self._mp.get_length()
        cur = self._mp.get_time()
        self.cur_lbl.setText(_fmt(cur))
        self.tot_lbl.setText(_fmt(length))
        if length > 0 and not self._dragging:
            pos = 1000 if state == vlc.State.Ended else int(1000 * cur / length)
            self.progress.setValue(pos)

        # Mid-roll / end-roll (faqat ad_hook o'rnatilganda, har biri 1 marta):
        # o'rtaga yetganda kino PAUZA qilinadi, reklama yopilgach davom etadi;
        # tugaganda esa yakuniy reklama chiqadi.
        if self.ad_hook and not self._ad_open:
            if (not self._ad_mid_done and length > 0
                    and state == vlc.State.Playing and cur >= length // 2):
                self._ad_mid_done = True
                self._mp.set_pause(1)
                self._begin_ad("mid", self._resume_after_ad)
            elif not self._ad_end_done and state == vlc.State.Ended:
                self._ad_end_done = True
                self._begin_ad("end", self._after_end_ad)

    # ---------- Boshqaruvni ko'rsatish/yashirish ----------
    def _show_controls(self):
        if self._ad_open:
            return   # reklama qatlami ustida boshqaruv ko'rinmasin
        # Boshqaruv oynasi videoni aniq qoplashi uchun geometriyani moslaymiz.
        self.controls.setGeometry(self.geometry())
        self.controls.show()
        self.controls.raise_()
        self._hide_timer.start(5000)

    def _hide_controls(self):
        self.controls.hide()

    def eventFilter(self, obj, e):
        # Boshqaruv oynasiga tegilsa/sichqoncha qimirlasa — yashirilmasin.
        if obj is self.controls and e.type() in (
                QEvent.Type.MouseButtonPress, QEvent.Type.MouseMove):
            self._show_controls()
        return super().eventFilter(obj, e)

    def mouseMoveEvent(self, e):
        self._show_controls()
        super().mouseMoveEvent(e)

    def mousePressEvent(self, e):
        # Sensorli ekran: tegilganda boshqaruv qaytsin (tap = press, move emas).
        # Boshqaruv yashirin bo'lsa — ko'rsatadi; ko'rinib turgan bo'lsa —
        # taymerni yangilaydi.
        self._show_controls()
        super().mousePressEvent(e)

    # ---------- Yopish ----------
    def stop_and_close(self):
        # Qayta kirishdan himoya (closeEvent ham shu yerga yo'naltiriladi).
        if getattr(self, "_closing", False):
            return
        self._closing = True
        self._timer.stop()
        self._hide_timer.stop()
        # Ovoz slayderi libVLC C funksiyasiga ulangan — pleyer bo'shatilgach
        # signal yetib bormasin (freed obyektga chaqiruv crash beradi).
        try:
            self.vol.valueChanged.disconnect()
        except (TypeError, RuntimeError):
            pass
        # MUHIM: native VLC resurslarini (dekoder, threadlar, soketlar) bo'shatamiz.
        # Aks holda har bir video ochilishi ularni to'plab boradi va uzoq
        # ishlaydigan kioskда oxir-oqibat muzlash/crash bo'ladi.
        self._mp.stop()
        self._mp.release()
        self._instance.release()
        # Boshqaruv alohida top-level oyna — u "arvoh" bo'lib qolmasin.
        self.controls.close()
        self.controls.deleteLater()
        self.close()
        self.closed.emit()
        self.deleteLater()

    def closeEvent(self, e):
        # Oyna boshqa yo'l bilan yopilsa ham (Alt+F4 va h.k.) resurslar bo'shasin
        # va boshqaruv oynasi orqada qolmasin.
        self.stop_and_close()
        e.accept()

    def resizeEvent(self, e):
        self.video.setGeometry(self.rect())
        if self.controls.isVisible():
            self.controls.setGeometry(self.geometry())
        super().resizeEvent(e)
