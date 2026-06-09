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
from PyQt6.QtCore import Qt, QTimer, pyqtSignal


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

    def __init__(self, stream_url, title=""):
        super().__init__()
        self.stream_url = stream_url
        self.title = title
        self._dragging = False

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

        # Bufer indikatori (markazda)
        self.buffering = QLabel("Yuklanmoqda...", self)
        self.buffering.setStyleSheet(
            "color: #FFFFFF; font-size: 22px; background: transparent;")
        self.buffering.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.buffering.hide()

        # Boshqaruv qatlami (video ustida)
        self.controls = QWidget(self)
        self.controls.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        c = QVBoxLayout(self.controls)
        c.setContentsMargins(24, 16, 24, 24)

        # Yuqori: X + sarlavha
        top = QHBoxLayout()
        self.x_btn = self._round_btn("✕", 44)
        self.x_btn.clicked.connect(self.stop_and_close)
        self.title_lbl = QLabel(self.title)
        self.title_lbl.setStyleSheet(
            "color:#FFFFFF; font-size:20px; font-weight:600; background:transparent;")
        top.addWidget(self.x_btn)
        top.addWidget(self.title_lbl)
        top.addStretch(1)
        c.addLayout(top)

        c.addStretch(1)

        # Markaz: 10s orqaga, play/pauza, 10s oldinga
        center = QHBoxLayout()
        center.addStretch(1)
        self.back_btn = self._round_btn("« 10", 64)
        self.play_btn = self._round_btn("⏸", 84)
        self.fwd_btn = self._round_btn("10 »", 64)
        self.back_btn.clicked.connect(lambda: self._seek_relative(-10000))
        self.play_btn.clicked.connect(self.toggle_play)
        self.fwd_btn.clicked.connect(lambda: self._seek_relative(+10000))
        for b in (self.back_btn, self.play_btn, self.fwd_btn):
            center.addWidget(b)
        center.addStretch(1)
        c.addLayout(center)

        c.addStretch(1)

        # Past: vaqt | progress | umumiy | ovoz
        bottom = QHBoxLayout()
        self.cur_lbl = QLabel("00:00")
        self.tot_lbl = QLabel("00:00")
        for l in (self.cur_lbl, self.tot_lbl):
            l.setStyleSheet("color:#FFFFFF; font-size:15px; background:transparent;")

        self.progress = QSlider(Qt.Orientation.Horizontal)
        self.progress.setRange(0, 1000)
        self.progress.sliderPressed.connect(lambda: setattr(self, "_dragging", True))
        self.progress.sliderReleased.connect(self._on_seek)

        self.vol = QSlider(Qt.Orientation.Horizontal)
        self.vol.setRange(0, 100)
        self.vol.setValue(80)
        self.vol.setFixedWidth(120)
        self.vol.valueChanged.connect(self._mp.audio_set_volume)

        bottom.addWidget(self.cur_lbl)
        bottom.addWidget(self.progress, 1)
        bottom.addWidget(self.tot_lbl)
        bottom.addSpacing(16)
        bottom.addWidget(QLabel("🔊"))
        bottom.addWidget(self.vol)
        c.addLayout(bottom)

        self.controls.setStyleSheet("background: transparent;")

    def _round_btn(self, text, size):
        b = QPushButton(text)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setFixedSize(size, size)
        b.setStyleSheet(
            f"QPushButton {{ background: rgba(255,255,255,0.15); color:#FFFFFF;"
            f" border:none; border-radius:{size // 2}px; font-size:18px;"
            f" font-weight:600; }}"
            f"QPushButton:hover {{ background: rgba(255,255,255,0.30); }}")
        return b

    # ---------- O'ynatish ----------
    def start(self):
        self.showFullScreen()
        media = self._instance.media_new(self.stream_url)
        self._mp.set_media(media)
        # Video chiqarish oynasini ulash (platformaga bog'liq)
        win_id = int(self.video.winId())
        if sys.platform.startswith("win"):
            self._mp.set_hwnd(win_id)
        elif sys.platform == "darwin":
            self._mp.set_nsobject(win_id)
        else:
            self._mp.set_xwindow(win_id)
        self._mp.audio_set_volume(self.vol.value())
        self._mp.play()
        self._show_controls()

    def toggle_play(self):
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
        # Bufer holati
        if state == vlc.State.Buffering:
            self.buffering.show()
        else:
            self.buffering.hide()
        # play/pauza belgisi
        playing = state == vlc.State.Playing
        self.play_btn.setText("⏸" if playing else "▶")

        length = self._mp.get_length()
        cur = self._mp.get_time()
        self.cur_lbl.setText(_fmt(cur))
        self.tot_lbl.setText(_fmt(length))
        if length > 0 and not self._dragging:
            self.progress.setValue(int(1000 * cur / length))

    # ---------- Boshqaruvni ko'rsatish/yashirish ----------
    def _show_controls(self):
        self.controls.show()
        self.controls.raise_()
        self._hide_timer.start(3500)

    def _hide_controls(self):
        self.controls.hide()

    def mouseMoveEvent(self, e):
        self._show_controls()
        super().mouseMoveEvent(e)

    # ---------- Yopish ----------
    def stop_and_close(self):
        self._timer.stop()
        self._mp.stop()
        self.close()
        self.closed.emit()
        self.deleteLater()

    def resizeEvent(self, e):
        self.video.setGeometry(self.rect())
        self.controls.setGeometry(self.rect())
        self.buffering.setGeometry(self.rect())
        super().resizeEvent(e)
