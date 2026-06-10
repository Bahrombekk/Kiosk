"""
audio_player.py — Audiokitob pleyeri (TZ 8.11, LibVLC asosida).

To'liq ekran: tepa-chapda "← Ortga"; markazda muqova, nom, muallif;
progress chizig'i, joriy/umumiy vaqt; boshqaruv: 10s orqaga, play/pauza,
10s oldinga, hamda o'qish tezligi (1x → 1.5x → 2x).
"""
import math
import vlc
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QSizePolicy, QGraphicsDropShadowEffect)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QColor, QPainter
from core import theme as T
from core.i18n import tr
from players.video import _fmt
from widgets.cover import CoverLabel
from widgets.icons import svg_icon

SPEEDS = [1.0, 1.5, 2.0]


class Waveform(QWidget):
    """Audio progress'ni to'lqin (vertikal ustunlar) ko'rinishida ko'rsatadi.
    O'tilgan qism urg'u rangda, qolgani kulrang. Bosish/surish bilan seek qiladi.
    Ustun balandliklari determinik (audio to'lqinga o'xshash, lekin barqaror)."""
    seek = pyqtSignal(float)   # 0..1

    def __init__(self):
        super().__init__()
        self._progress = 0.0
        self._dragging = False
        self._accent = QColor("#2f68f4")
        self._gray = QColor("#c7cdd8")
        self._bar_w = T.s(5)
        self._gap = T.s(5)
        self.setMinimumHeight(T.s(72))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_colors(self, accent, gray):
        self._accent = QColor(accent)
        self._gray = QColor(gray)
        self.update()

    def set_progress(self, p):
        p = max(0.0, min(1.0, p))
        if abs(p - self._progress) > 0.0005:
            self._progress = p
            self.update()

    def _bar_height(self, i):
        """0.18..1.0 oralig'ida determinik balandlik (sinuslar yig'indisi)."""
        v = (math.sin(i * 0.7) * 0.5 + math.sin(i * 1.7 + 1) * 0.3
             + math.sin(i * 0.33 + 2) * 0.2)
        return 0.18 + 0.82 * abs(v)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        step = self._bar_w + self._gap
        n = max(1, self.width() // step)
        cy = self.height() / 2
        max_h = self.height() - T.s(6)
        played = self._progress * n
        r = self._bar_w / 2
        for i in range(n):
            h = self._bar_height(i) * max_h
            x = i * step
            p.setBrush(self._accent if i < played else self._gray)
            p.drawRoundedRect(int(x), int(cy - h / 2), self._bar_w, int(h), r, r)
        p.end()

    def _set_from_x(self, e):
        if self.width() > 0:
            self.set_progress(e.position().x() / self.width())

    def mousePressEvent(self, e):
        self._dragging = True
        self._set_from_x(e)

    def mouseMoveEvent(self, e):
        if self._dragging:
            self._set_from_x(e)

    def mouseReleaseEvent(self, e):
        self._dragging = False
        self.seek.emit(self._progress)


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
        # Top-level QWidget fonni o'zida bo'yashi uchun (aks holda ortidagi eski
        # ekran ko'rinib qoladi) — Reader bilan bir xil.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

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
        self.back = QPushButton(tr("common.back"))
        self.back.setObjectName("aBack")
        self.back.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back.clicked.connect(self.stop_and_close)
        top.addWidget(self.back)
        top.addStretch(1)
        root.addLayout(top)

        root.addStretch(1)

        # Markaz: muqova + nom + muallif
        self.cover = CoverLabel(T.s(240), T.s(340))
        self.cover.load(self.api.cover_url(self.item["id"]))
        # Muqovaga yumshoq soya (boshqa kartalar kabi)
        sh = QGraphicsDropShadowEffect(self.cover)
        sh.setBlurRadius(T.s(48))
        sh.setOffset(0, T.s(18))
        sh.setColor(QColor(40, 55, 90, 90))
        self.cover.setGraphicsEffect(sh)
        root.addWidget(self.cover, alignment=Qt.AlignmentFlag.AlignHCenter)
        root.addSpacing(T.s(20))

        self.title = QLabel(self.item.get("title", ""))
        self.title.setObjectName("aTitle")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.author = QLabel(self.item.get("author") or "")
        self.author.setObjectName("aAuthor")
        self.author.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.title)
        root.addWidget(self.author)

        # To'lqin (waveform) — progress; ostida joriy/umumiy vaqt chetlarda
        self.wave = Waveform()
        self.wave.seek.connect(self._on_wave_seek)
        root.addWidget(self.wave)

        trow = QHBoxLayout()
        self.cur = QLabel("00:00")
        self.tot = QLabel("00:00")
        self.cur.setObjectName("aTime")
        self.tot.setObjectName("aTime")
        trow.addWidget(self.cur)
        trow.addStretch(1)
        trow.addWidget(self.tot)
        root.addLayout(trow)
        root.addSpacing(T.s(16))

        # Boshqaruv: markazda [10s, play/pauza, 10s], o'ng chetda tezlik (1x)
        crow = QHBoxLayout()
        self.back10 = self._btn("⟲ 10", T.s(64))
        self.play_btn = self._btn("", T.s(88), accent=True, icon="pause")
        self.fwd10 = self._btn("10 ⟳", T.s(64))
        self.speed_btn = self._btn("1x", T.s(64))
        self.back10.clicked.connect(lambda: self._seek_rel(-10000))
        self.play_btn.clicked.connect(self.toggle_play)
        self.fwd10.clicked.connect(lambda: self._seek_rel(+10000))
        self.speed_btn.clicked.connect(self._cycle_speed)
        crow.addSpacing(T.s(64))          # o'ngdagi tezlik tugmasi bilan muvozanat
        crow.addStretch(1)
        crow.addWidget(self.back10)
        crow.addSpacing(T.s(28))
        crow.addWidget(self.play_btn)
        crow.addSpacing(T.s(28))
        crow.addWidget(self.fwd10)
        crow.addStretch(1)
        crow.addWidget(self.speed_btn)
        root.addLayout(crow)

        root.addStretch(1)

    def _btn(self, text, size, accent=False, icon=None):
        b = QPushButton(text)
        b.setObjectName("aAccent" if accent else "aBtn")
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setFixedSize(size, size)
        if icon:
            b.setIcon(svg_icon(icon, "#FFFFFF", 64))
            b.setIconSize(QSize(int(size * 0.42), int(size * 0.42)))
        return b

    def _set_play_icon(self, name):
        # _refresh tez-tez chaqiriladi — ikonka faqat o'zgarganda yangilanadi.
        if getattr(self, "_play_icon_name", None) == name:
            return
        self._play_icon_name = name
        self.play_btn.setIcon(svg_icon(name, "#FFFFFF", 64))

    # --- O'ynatish ---
    def start(self):
        self._restyle()
        self.showFullScreen()
        self._media = self._instance.media_new(self.api.stream_url(self.item["id"]))
        self._mp.set_media(self._media)
        self._mp.play()

    def toggle_play(self):
        state = self._mp.get_state()
        if state in (vlc.State.Ended, vlc.State.Stopped):
            # Tugagan — boshidan qaytadan
            self._mp.set_media(self._media)
            self._mp.play()
        else:
            self._mp.pause()

    def _seek_rel(self, delta):
        t = self._mp.get_time()
        self._mp.set_time(max(0, t + delta))

    def _on_wave_seek(self, frac):
        length = self._mp.get_length()
        if length > 0:
            self._mp.set_time(int(length * frac))

    def _cycle_speed(self):
        self._speed_i = (self._speed_i + 1) % len(SPEEDS)
        rate = SPEEDS[self._speed_i]
        self._mp.set_rate(rate)
        self.speed_btn.setText(f"{rate:g}x")

    def _refresh(self):
        state = self._mp.get_state()
        if state == vlc.State.Ended:
            self._set_play_icon("rotate-ccw")
        elif state == vlc.State.Playing:
            self._set_play_icon("pause")
        else:
            self._set_play_icon("play")
        length = self._mp.get_length()
        cur = self._mp.get_time()
        self.cur.setText(_fmt(cur))
        self.tot.setText(_fmt(length))
        if length > 0 and not self.wave._dragging:
            pos = 1.0 if state == vlc.State.Ended else cur / length
            self.wave.set_progress(pos)

    def stop_and_close(self):
        if getattr(self, "_closing", False):
            return
        self._closing = True
        self._timer.stop()
        # Native VLC resurslarini bo'shatamiz (video pleyer bilan bir xil) —
        # aks holda har bir audio ochilishi ularni to'plab boradi.
        self._mp.stop()
        self._mp.release()
        self._instance.release()
        self.close()
        self.closed.emit()
        self.deleteLater()

    def closeEvent(self, e):
        self.stop_and_close()
        e.accept()

    def _restyle(self):
        c = T.THEMES[self.theme_name]
        # Fon oq (Reader bilan bir xil); dark mavzuda mavzu foni
        bg = "#FFFFFF" if self.theme_name == "light" else c["bg"]
        self.setStyleSheet(f"background: {bg};")
        self.wave.set_colors(c["accent"], "#C7CDD8")
        self.back.setStyleSheet(
            f"#aBack {{ background: {c['surface']}; color: {c['text']};"
            f" border: none; border-radius: {T.RADIUS['pill']}px;"
            f" padding: {T.s(12)}px {T.s(26)}px; font-size: {T.FONT['nav']}px;"
            f" font-weight: 600; }}"
            f"#aBack:hover {{ background: {c['surface2']}; }}"
            f"#aBack:pressed {{ background: {c['border']}; }}")
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
            f" border: 1px solid {c['border']}; border-radius: {T.s(64) // 2}px;"
            f" font-size: {T.s(16)}px; font-weight: 600; }}"
            f"#aBtn:hover {{ background: {c['surface2']}; }}"
            f"#aBtn:pressed {{ background: {c['border']}; }}"
            f"#aAccent {{ background: {c['accent']}; color: {c['accent_text']};"
            f" border: none; border-radius: {T.s(88) // 2}px; font-size: {T.s(26)}px; }}"
            f"#aAccent:hover {{ background: #1D4ED8; }}"
            f"#aAccent:pressed {{ background: #1E40AF; }}"))
