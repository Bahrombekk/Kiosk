"""
audio_player.py — Audiokitob pleyeri (TZ 8.11, LibVLC asosida).

To'liq ekran: tepa-chapda "← Ortga"; markazda muqova, nom, muallif;
progress chizig'i, joriy/umumiy vaqt; boshqaruv: 10s orqaga, play/pauza,
10s oldinga, hamda o'qish tezligi (1x → 1.5x → 2x).
"""
import vlc
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QSlider)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
import theme as T
from player import _fmt
from widgets.cover import CoverLabel

SPEEDS = [1.0, 1.5, 2.0]


class AudioPlayer(QWidget):
    closed = pyqtSignal()
    NETWORK_CACHING_MS = 3000

    def __init__(self, api, item, theme_name="light"):
        super().__init__()
        self.api = api
        self.item = item
        self.theme_name = theme_name
        self._dragging = False
        self._speed_i = 0

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)

        self._instance = vlc.Instance(
            "--quiet", f"--network-caching={self.NETWORK_CACHING_MS}")
        self._mp = self._instance.media_player_new()

        self._build()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(500)

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(T.SPACE["page"], T.SPACE["gap"],
                                T.SPACE["page"], T.SPACE["page"])

        # Tepa: Ortga
        top = QHBoxLayout()
        self.back = QPushButton("←  Ortga")
        self.back.setObjectName("aBack")
        self.back.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back.clicked.connect(self.stop_and_close)
        top.addWidget(self.back)
        top.addStretch(1)
        root.addLayout(top)

        root.addStretch(1)

        # Markaz: muqova + nom + muallif
        self.cover = CoverLabel(240, 340)
        self.cover.load(self.api.cover_url(self.item["id"]))
        root.addWidget(self.cover, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.title = QLabel(self.item.get("title", ""))
        self.title.setObjectName("aTitle")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.author = QLabel(self.item.get("author") or "")
        self.author.setObjectName("aAuthor")
        self.author.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.title)
        root.addWidget(self.author)

        # Progress + vaqt
        prow = QHBoxLayout()
        self.cur = QLabel("00:00")
        self.tot = QLabel("00:00")
        self.progress = QSlider(Qt.Orientation.Horizontal)
        self.progress.setRange(0, 1000)
        self.progress.sliderPressed.connect(lambda: setattr(self, "_dragging", True))
        self.progress.sliderReleased.connect(self._on_seek)
        self.cur.setObjectName("aTime")
        self.tot.setObjectName("aTime")
        prow.addWidget(self.cur)
        prow.addWidget(self.progress, 1)
        prow.addWidget(self.tot)
        root.addLayout(prow)

        # Boshqaruv: 10s, play/pauza, 10s, tezlik
        crow = QHBoxLayout()
        crow.addStretch(1)
        self.back10 = self._btn("« 10", 64)
        self.play_btn = self._btn("⏸", 84, accent=True)
        self.fwd10 = self._btn("10 »", 64)
        self.speed_btn = self._btn("1x", 64)
        self.back10.clicked.connect(lambda: self._seek_rel(-10000))
        self.play_btn.clicked.connect(self.toggle_play)
        self.fwd10.clicked.connect(lambda: self._seek_rel(+10000))
        self.speed_btn.clicked.connect(self._cycle_speed)
        for b in (self.back10, self.play_btn, self.fwd10, self.speed_btn):
            crow.addWidget(b)
        crow.addStretch(1)
        root.addLayout(crow)

        root.addStretch(1)

    def _btn(self, text, size, accent=False):
        b = QPushButton(text)
        b.setObjectName("aAccent" if accent else "aBtn")
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setFixedSize(size, size)
        return b

    # --- O'ynatish ---
    def start(self):
        self._restyle()
        self.showFullScreen()
        media = self._instance.media_new(self.api.stream_url(self.item["id"]))
        self._mp.set_media(media)
        self._mp.play()

    def toggle_play(self):
        self._mp.pause()

    def _seek_rel(self, delta):
        t = self._mp.get_time()
        self._mp.set_time(max(0, t + delta))

    def _on_seek(self):
        length = self._mp.get_length()
        if length > 0:
            self._mp.set_time(int(length * self.progress.value() / 1000))
        self._dragging = False

    def _cycle_speed(self):
        self._speed_i = (self._speed_i + 1) % len(SPEEDS)
        rate = SPEEDS[self._speed_i]
        self._mp.set_rate(rate)
        self.speed_btn.setText(f"{rate:g}x")

    def _refresh(self):
        playing = self._mp.get_state() == vlc.State.Playing
        self.play_btn.setText("⏸" if playing else "▶")
        length = self._mp.get_length()
        cur = self._mp.get_time()
        self.cur.setText(_fmt(cur))
        self.tot.setText(_fmt(length))
        if length > 0 and not self._dragging:
            self.progress.setValue(int(1000 * cur / length))

    def stop_and_close(self):
        self._timer.stop()
        self._mp.stop()
        self.close()
        self.closed.emit()
        self.deleteLater()

    def _restyle(self):
        c = T.THEMES[self.theme_name]
        self.setStyleSheet(f"background: {c['bg']};")
        self.back.setStyleSheet(
            f"#aBack {{ background: transparent; color: {c['text']}; border: none;"
            f" font-size: {T.FONT['nav']}px; font-weight: 600; }}")
        self.title.setStyleSheet(
            f"#aTitle {{ color: {c['text']}; font-size: {T.FONT['h2']}px;"
            f" font-weight: 700; }}")
        self.author.setStyleSheet(
            f"#aAuthor {{ color: {c['text_secondary']}; font-size: {T.FONT['body']}px; }}")
        for l in (self.cur, self.tot):
            l.setStyleSheet(f"#aTime {{ color: {c['text_secondary']};"
                            f" font-size: {T.FONT['small']}px; }}")
        self.setStyleSheet(self.styleSheet() + (
            f"#aBtn {{ background: {c['surface']}; color: {c['text']};"
            f" border: 1px solid {c['border']}; border-radius: 32px;"
            f" font-size: 16px; font-weight: 600; }}"
            f"#aBtn:hover {{ background: {c['surface2']}; }}"
            f"#aAccent {{ background: {c['accent']}; color: {c['accent_text']};"
            f" border: none; border-radius: 42px; font-size: 26px; }}"
            f"#aAccent:hover {{ background: #1D4ED8; }}"))
