"""
audio_player.py — Audiokitob pleyeri (TZ 8.11, LibVLC asosida).

To'liq ekran: tepa-chapda "← Ortga"; markazda muqova, nom, muallif;
progress chizig'i, joriy/umumiy vaqt; boshqaruv: 10s orqaga, play/pauza,
10s oldinga, hamda o'qish tezligi (1x → 1.5x → 2x).
"""
import math
import time
import vlc
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QSizePolicy, QGraphicsDropShadowEffect,
                             QListWidget, QListWidgetItem, QSlider, QFrame,
                             QMenu, QInputDialog, QDialog, QDialogButtonBox,
                             QScrollArea)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize, QByteArray, QRectF
from PyQt6.QtGui import (QColor, QPainter, QLinearGradient, QAction, QPixmap,
                         QPainterPath, QIcon)
from PyQt6.QtSvg import QSvgRenderer
from core import theme as T
from core import cache
from core.i18n import tr
from players.video import _fmt
from widgets.cover import CoverLabel
from widgets.icons import svg_icon, svg_pixmap

SPEEDS = [1.0, 1.5, 2.0]

# Pastki panel/qator ikonkalari (kioskda svg fayli yo'q — inline chizamiz)
_SVG_CLOCK = ("<svg viewBox='0 0 24 24' fill='none'><circle cx='12' cy='12' r='9'"
              " stroke='currentColor' stroke-width='2'/><path d='M12 7v5l3 2'"
              " stroke='currentColor' stroke-width='2' stroke-linecap='round'/></svg>")
_SVG_SHUFFLE = ("<svg viewBox='0 0 24 24' fill='none' stroke='currentColor'"
                " stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>"
                "<path d='M16 3h5v5M4 20 21 3M21 16v5h-5M15 15l6 6M4 4l5 5'/></svg>")
_SVG_HEART = ("<svg viewBox='0 0 24 24' fill='none'><path d='M12 21s-7-4.5-9.5-9"
              "C1 9 2.5 5.5 6 5.5c2 0 3.2 1.2 4 2.3.8-1.1 2-2.3 4-2.3 3.5 0 5 3.5"
              " 3.5 6.5C19 16.5 12 21 12 21Z' stroke='currentColor'"
              " stroke-width='2' stroke-linejoin='round'/></svg>")
_SVG_HEART_FILL = ("<svg viewBox='0 0 24 24'><path d='M12 21s-7-4.5-9.5-9C1 9 2.5"
                   " 5.5 6 5.5c2 0 3.2 1.2 4 2.3.8-1.1 2-2.3 4-2.3 3.5 0 5 3.5 3.5"
                   " 6.5C19 16.5 12 21 12 21Z' fill='currentColor'/></svg>")
_SVG_SLIDERS = ("<svg viewBox='0 0 24 24' fill='none' stroke='currentColor'"
                " stroke-width='2' stroke-linecap='round'>"
                "<path d='M4 6h10M18 6h2M4 12h2M10 12h10M4 18h10M18 18h2'/>"
                "<circle cx='16' cy='6' r='2'/><circle cx='8' cy='12' r='2'/>"
                "<circle cx='16' cy='18' r='2'/></svg>")
_SVG_PLAY = ("<svg viewBox='0 0 24 24'><path d='M8 5v14l11-7z' fill='currentColor'/></svg>")
_SVG_WAVE = ("<svg viewBox='0 0 24 24' fill='currentColor'>"
             "<rect x='3' y='9' width='3' height='6' rx='1.5'/>"
             "<rect x='8' y='5' width='3' height='14' rx='1.5'/>"
             "<rect x='13' y='7' width='3' height='10' rx='1.5'/>"
             "<rect x='18' y='10' width='3' height='4' rx='1.5'/></svg>")
_SVG_LIST = ("<svg viewBox='0 0 24 24' fill='none' stroke='currentColor'"
             " stroke-width='2' stroke-linecap='round'>"
             "<path d='M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01'/></svg>")
_SVG_CAST = ("<svg viewBox='0 0 24 24' fill='none' stroke='currentColor'"
             " stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>"
             "<path d='M2 8V6a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-5'/>"
             "<path d='M2 12a6 6 0 0 1 6 6M2 16a2 2 0 0 1 2 2'/></svg>")
_SVG_PLUS = ("<svg viewBox='0 0 24 24' fill='none' stroke='currentColor'"
             " stroke-width='2.4' stroke-linecap='round'>"
             "<path d='M12 5v14M5 12h14'/></svg>")
_SVG_SKIP_BACK = ("<svg viewBox='0 0 24 24' fill='currentColor'>"
                  "<rect x='6' y='6' width='2.4' height='12' rx='1'/>"
                  "<path d='M20 6.5v11l-9-5.5z'/></svg>")
_SVG_SKIP_FWD = ("<svg viewBox='0 0 24 24' fill='currentColor'>"
                 "<path d='M4 6.5v11l9-5.5z'/>"
                 "<rect x='15.6' y='6' width='2.4' height='12' rx='1'/></svg>")
_SVG_ROT_BACK = ("<svg viewBox='0 0 24 24' fill='none' stroke='currentColor'"
                 " stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>"
                 "<path d='M3 12a9 9 0 1 0 3-6.7L3 8'/><path d='M3 3v5h5'/></svg>")
_SVG_ROT_FWD = ("<svg viewBox='0 0 24 24' fill='none' stroke='currentColor'"
                " stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>"
                "<path d='M21 12a9 9 0 1 1-3-6.7L21 8'/><path d='M21 3v5h-5'/></svg>")


def _inline_icon(svg, color, size):
    """Inline SVG matnini berilgan rangdagi QPixmap qiladi."""
    body = svg.replace("<svg", "<svg xmlns='http://www.w3.org/2000/svg'", 1)
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    QSvgRenderer(QByteArray(body.encode("utf-8"))).render(p, QRectF(0, 0, size, size))
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    p.fillRect(pm.rect(), QColor(color))
    p.end()
    return pm


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
        # Jonli ekvalayzer: ijro paytida ustunlar nafis tebranadi
        self._active = False
        self._phase = 0.0
        self._anim = QTimer(self)
        self._anim.setInterval(80)
        self._anim.timeout.connect(self._tick_anim)

    def set_active(self, on):
        """Ijro holatini bildiradi — animatsiyani yoqadi/o'chiradi (CPU tejash)."""
        on = bool(on)
        if on == self._active:
            return
        self._active = on
        if on:
            self._anim.start()
        else:
            self._anim.stop()
            self.update()   # pauzada "muzlatamiz"

    def _tick_anim(self):
        self._phase += 0.13
        self.update()

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
        """0.18..1.0 oralig'ida determinik balandlik (sinuslar yig'indisi).
        Ijro paytida (_active) faza bo'yicha nafis tebranadi — jonli ekvalayzer."""
        v = (math.sin(i * 0.7) * 0.5 + math.sin(i * 1.7 + 1) * 0.3
             + math.sin(i * 0.33 + 2) * 0.2)
        base = 0.18 + 0.82 * abs(v)
        if self._active:
            wob = 0.10 * math.sin(self._phase + i * 0.45)
            base = max(0.12, min(1.0, base + wob))
        return base

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


class _PlRow(QFrame):
    """Playlist paneldagi bitta bosiladigan qator (musiqa)."""
    clicked = pyqtSignal(int)

    def __init__(self, idx):
        super().__init__()
        self._idx = idx

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._idx)
        super().mouseReleaseEvent(e)


class AudioPlayer(QWidget):
    closed = pyqtSignal()
    NETWORK_CACHING_MS = 3000

    # Tanlangan, odamga yoqadigan duotone fon kombinatsiyalari (HSL hue juftlari).
    # Xunuk sariq/loyqa-yashil oraliqdan qochilgan; orasida silliq crossfade.
    _BG_PALETTES = [
        (255, 315),   # lavanda -> pushti
        (210, 250),   # ko'k -> indigo
        (188, 218),   # okean (cyan -> ko'k)
        (160, 135),   # yalpiz (teal -> yashil)
        (18, 345),    # shafarq (shaftoli -> atirgul)
        (330, 288),   # berry (pushti -> siyohrang)
    ]

    def __init__(self, api, item, theme_name="light", playlist=None, index=0,
                 host=None):
        """item — joriy yozuv; playlist berilsa (musiqa) — qo'shiqlar ro'yxati.
        host — kiosk oynasi (berilsa pleyer SHU oyna ustida ochiladi, butun
        ekranda emas — dev/oynali rejim uchun)."""
        super().__init__()
        self.api = api
        self._host = host
        self.playlist = list(playlist) if playlist else [item]
        self.index = index if (playlist and 0 <= index < len(self.playlist)) else 0
        self.item = self.playlist[self.index]
        self._has_list = len(self.playlist) > 1
        self.theme_name = theme_name
        self._dragging = False
        self._speed_i = 0
        self._ctrl_btns = []     # boshqaruv tugmalari (glassy uslub _restyle'da)
        self._sleep_deadline = None   # uyqu taymeri (monotonic soniya) yoki None
        self.progress = None     # audiokitobda seek slayder; musiqada None
        self._shuffle = False    # Aralash (musiqa)
        self._pl_rows = []       # playlist panel qatorlari (musiqa)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        # Top-level QWidget fonni o'zida bo'yashi uchun (aks holda ortidagi eski
        # ekran ko'rinib qoladi) — Reader bilan bir xil.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # --no-video: bu AUDIO pleyer. Ba'zi "musiqa" fayllari aslida video
        # (mp4 .mp3 deb saqlangan) — video o'chirilmasa VLC alohida video oyna
        # ochib yuboradi. Shu bayroq bilan faqat ovoz chiqadi, oyna ochilmaydi.
        self._instance = vlc.Instance(
            "--quiet", "--no-video",
            f"--network-caching={self.NETWORK_CACHING_MS}")
        self._mp = self._instance.media_player_new()

        # Pleyer OYNA o'lchamiga moslashadi (monitor SCALE'iga emas) — dev/oynali
        # rejimda kichraytirilganda ham buzilmaydi. host (kiosk oynasi) berilsa
        # undan, aks holda ekrandan hisoblanadi. resize'da qayta quriladi.
        self._root_w = None
        self._S = self._calc_scale(host)
        self._build()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(500)

        # Fon — tanlangan chiroyli rang kombinatsiyalari orasida sekin crossfade
        # + ijroda yumshoq "nafas". _pal0 — har trek boshqa kombinatsiyadan boshlanadi.
        self._bg_phase = 0.0
        self._pal0 = 0
        self._playing = False
        self._bg_anim = QTimer(self)
        self._bg_anim.setInterval(50)        # 20 fps — silliq, tinch
        self._bg_anim.timeout.connect(self._tick_bg)

    # ------------------------------------------------ Oyna-nisbiy masshtab
    def _calc_scale(self, ref=None):
        """Pleyer (yoki host oynasi) o'lchamiga qarab masshtab — global
        T.init_scale bilan bir xil formula, lekin EKRAN emas, OYNA bo'yicha."""
        if ref is not None and ref.width() > 0:
            w, h = ref.width(), ref.height()
        elif self.width() > 0:
            w, h = self.width(), self.height()
        else:
            return T.SCALE
        sc = min(w / T.DESIGN_W, h / T.DESIGN_H)
        return max(0.8, min(1.7, sc))

    def k(self, px):
        """Bazaviy pikselni pleyer oynasi masshtabiga moslaydi (paintEvent uchun;
        _build/_restyle ichida T.s ham shu masshtabda — global SCALE vaqtincha
        almashtiriladi)."""
        return max(1, round(px * self._S))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._root_w is not None:
            self._root_w.setGeometry(self.rect())
        if not hasattr(self, "_resize_timer"):
            self._resize_timer = QTimer(self)
            self._resize_timer.setSingleShot(True)
            self._resize_timer.timeout.connect(self._maybe_rescale)
        self._resize_timer.start(160)   # debounce — surish tugagach qayta quramiz

    def _maybe_rescale(self):
        if getattr(self, "_closing", False):
            return
        new_s = self._calc_scale()
        if abs(new_s - self._S) > 0.015:
            self._S = new_s
            self._build()
            self._restyle()
            # _build() yangi vidjetlarni bo'sh holatda quradi (nom/muallif/
            # muqova/progress/vaqt yo'qoladi). Joriy holatni qayta tiklaymiz —
            # ijro davom etadi (set_media/play CHAQIRILMAYDI).
            if getattr(self, "item", None) is not None:
                self._apply_state()

    def _apply_state(self):
        """Joriy item bo'yicha UI'ni tiklaydi (muqova, nom, muallif, playlist,
        sevimli) — ijro pozitsiyasi/holatiga tegmaydi. _build()dan keyin yoki
        trek yuklanganda chaqiriladi. Vaqt/progress keyingi _refresh'da to'ladi."""
        self._set_cover()
        self.title.setText(self.item.get("title", ""))
        self.author.setText(self.item.get("author") or "")
        if self._has_list:
            self.prev_btn.setEnabled(self.index > 0)
            self.next_btn.setEnabled(self.index < len(self.playlist) - 1)
            self._refresh_playlist()
        self._update_fav_btn()

    def _tick_bg(self):
        self._bg_phase += 0.01
        self.update()

    def _pal_colors(self, idx, breath):
        """idx-palitradagi (hue jufti) ikki gradient rangi — nafasga qarab
        yumshoq quyuqlashadi/to'yinadi."""
        h1, h2 = self._BG_PALETTES[idx % len(self._BG_PALETTES)]
        if self.theme_name == "light":
            lv = int(232 - 22 * breath)
            sat = int(160 + 55 * breath)
            return (QColor.fromHsl(h1, sat, lv),
                    QColor.fromHsl(h2, sat, max(150, lv - 12)))
        lv = int(34 + 16 * breath)
        sat = int(80 + 45 * breath)
        return (QColor.fromHsl(h1, sat, lv),
                QColor.fromHsl(h2, sat, max(8, lv - 16)))

    def paintEvent(self, _e):
        """Chetlarda tekis fon + ichida yumaloq KARTA: kartada tanlangan rang
        kombinatsiyalari orasida sekin crossfade + nafas (mockupdagidek)."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        # Sahifa foni (chetlar) — yumshoq lavanda
        if self.theme_name == "light":
            p.fillRect(self.rect(), QColor("#E6E1F3"))
        else:
            p.fillRect(self.rect(), QColor("#11161F"))
        # Karta (yumaloq) — kontent shu ustida (oyna masshtabida)
        mx = self.k(110) if not self._has_list else self.k(16)
        my = self.k(82) if not self._has_list else self.k(16)
        card = QRectF(mx, my, w - 2 * mx, h - 2 * my)
        rad = self.k(30)
        # Karta tagida yumshoq soya (bir necha shaffof qatlam — blur taqlidi)
        p.setPen(Qt.PenStyle.NoPen)
        off = self.k(16)
        sh_base = QColor(70, 55, 120) if self.theme_name == "light" else QColor(0, 0, 0)
        for grow, alpha in ((self.k(3), 16), (self.k(10), 11),
                            (self.k(20), 7), (self.k(32), 4)):
            sh_base.setAlpha(alpha)
            p.setBrush(sh_base)
            sr = QRectF(card).adjusted(-grow, -grow + off, grow, grow + off)
            p.drawRoundedRect(sr, rad + grow, rad + grow)
        clip = QPainterPath(); clip.addRoundedRect(card, rad, rad)
        p.setClipPath(clip)

        breath = ((math.sin(self._bg_phase * 5.2) + 1) / 2) if self._playing else 0.0
        pos = self._pal0 + self._bg_phase * 0.15
        i = int(pos)
        frac = pos - i
        x1 = mx + (w - 2 * mx) * (0.5 + 0.5 * math.cos(self._bg_phase * 0.6))
        y1 = my + (h - 2 * my) * (0.5 + 0.5 * math.sin(self._bg_phase * 0.6))

        def _fill(idx):
            a, b = self._pal_colors(idx, breath)
            g = QLinearGradient(x1, y1, w - x1, h - y1)
            g.setColorAt(0.0, a)
            g.setColorAt(1.0, b)
            p.fillRect(card, g)

        _fill(i)
        if frac > 0.001:
            p.setOpacity(frac)
            _fill(i + 1)
            p.setOpacity(1.0)
        # Tepada nozik shisha yaltirashi (glass sheen) — yengil hajm beradi
        sheen = QLinearGradient(0, my, 0, my + (h - 2 * my) * 0.45)
        sheen.setColorAt(0.0, QColor(255, 255, 255, 46))
        sheen.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.fillRect(card, sheen)
        p.end()

    def _soft_shadow(self, widget, blur, dy, alpha):
        """Widgetga yumshoq soya — frosted tugmalar fondan ko'tarilib tursin."""
        sh = QGraphicsDropShadowEffect(widget)
        sh.setBlurRadius(blur); sh.setOffset(0, dy)
        sh.setColor(QColor(40, 45, 80, alpha))
        widget.setGraphicsEffect(sh)

    # ------------------------------------------------------------------ UI
    def _build(self):
        # Eski kontentni tozalaymiz (resize'da qayta qurish uchun)
        if self._root_w is not None:
            self._root_w.hide()
            self._root_w.deleteLater()
        self._ctrl_btns = []
        self._pl_rows = []
        self._play_icon_name = None
        self._root_w = QWidget(self)
        self._root_w.setGeometry(self.rect())
        # T.s() ni vaqtincha OYNA masshtabiga o'tkazamiz — butun pleyer shu
        # masshtabda quriladi (global SCALE'ga tegmaymiz, finally'da qaytaramiz)
        _old_scale = T.SCALE
        T.SCALE = self._S
        try:
            self._build_content(QVBoxLayout(self._root_w))
        finally:
            T.SCALE = _old_scale
        self._root_w.show()

    def _build_content(self, root):
        # Kontent karta ICHIDA (paintEvent karta chizadi) — padding bilan
        if self._has_list:
            root.setContentsMargins(T.s(40), T.s(34), T.s(40), T.s(34))
        else:
            root.setContentsMargins(T.s(150), T.s(112), T.s(150), T.s(104))
        root.setSpacing(T.s(10))

        top = QHBoxLayout()
        self.back = QPushButton(tr("common.back"))
        self.back.setObjectName("aBack")
        self.back.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back.clicked.connect(self.stop_and_close)
        self._soft_shadow(self.back, T.s(24), T.s(7), 55)
        top.addWidget(self.back)   # har doim yuqori-chapda (musiqa + kitob)
        top.addStretch(1)
        if not self._has_list:   # audiokitob: tepa-o'ngda ⋮ menyu
            self.menu_btn = QPushButton("⋮")
            self.menu_btn.setObjectName("aDots")
            self.menu_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.menu_btn.setFixedSize(T.s(52), T.s(52))
            self.menu_btn.clicked.connect(self._book_menu)
            self._soft_shadow(self.menu_btn, T.s(24), T.s(7), 55)
            top.addWidget(self.menu_btn)
        root.addLayout(top)

        if self._has_list:
            self._build_music(root)
        else:
            self._build_book(root)

    # ---- umumiy bo'laklar ----
    def _make_cover(self, w, h):
        self.cover = CoverLabel(w, h)
        self._set_cover()
        sh = QGraphicsDropShadowEffect(self.cover)
        sh.setBlurRadius(T.s(60)); sh.setOffset(0, T.s(22))
        sh.setColor(QColor(30, 45, 80, 120))
        self.cover.setGraphicsEffect(sh)

    def _make_titles(self, center):
        al = (Qt.AlignmentFlag.AlignHCenter if center
              else Qt.AlignmentFlag.AlignLeft)
        self.title = QLabel(self.item.get("title", ""))
        self.title.setObjectName("aTitle")
        self.title.setWordWrap(True)
        self.title.setAlignment(al)
        self.author = QLabel(self.item.get("author") or "")
        self.author.setObjectName("aAuthor")
        self.author.setAlignment(al)

    def _make_wave(self):
        self.wave = Waveform()
        self.wave.seek.connect(self._on_wave_seek)
        self.cur = QLabel("00:00"); self.tot = QLabel("00:00")
        self.cur.setObjectName("aTime"); self.tot.setObjectName("aTime")

    def _time_row(self):
        row = QHBoxLayout()
        row.addWidget(self.cur); row.addStretch(1); row.addWidget(self.tot)
        return row

    def _time_row_book(self):
        row = QHBoxLayout()
        self.chapter_counter = QLabel(self._book_chapter_label())
        self.chapter_counter.setObjectName("aChapterCounter")
        self.chapter_counter.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(self.cur)
        row.addStretch(1)
        row.addWidget(self.chapter_counter)
        row.addStretch(1)
        row.addWidget(self.tot)
        return row

    def _book_chapter_label(self):
        total = (self.item.get("chapters") or self.item.get("chapter_count")
                 or self.item.get("chapters_count") or 1)
        try:
            total = max(1, int(total))
        except (TypeError, ValueError):
            total = 1
        current = min(total, max(1, int(self.item.get("chapter") or 1)))
        return tr("player.chapter_fmt", cur=current, total=total)

    def _make_transport(self):
        crow = QHBoxLayout()
        small = T.s(62) if not self._has_list else T.s(58)
        skip = T.s(66) if not self._has_list else T.s(62)
        play = T.s(98) if not self._has_list else T.s(92)
        gap = T.s(18) if not self._has_list else T.s(16)
        self.back10 = self._btn(" 10", small, svg=_SVG_ROT_BACK)
        self.prev_btn = self._btn("", skip, svg=_SVG_SKIP_BACK)
        self.play_btn = self._btn("", play, accent=True, icon="pause")
        self.next_btn = self._btn("", skip, svg=_SVG_SKIP_FWD)
        self.fwd10 = self._btn(" 10", small, svg=_SVG_ROT_FWD)
        # Play tugmasiga yumshoq binafsha "glow" — diqqatni tortadi
        accent = "#7C5CF6" if not self._has_list else T.THEMES[self.theme_name]["accent"]
        glow = QGraphicsDropShadowEffect(self.play_btn)
        glow.setBlurRadius(T.s(46)); glow.setOffset(0, T.s(12))
        gc = QColor(accent); gc.setAlpha(150)
        glow.setColor(gc)
        self.play_btn.setGraphicsEffect(glow)
        self.back10.clicked.connect(lambda: self._seek_rel(-10000))
        self.play_btn.clicked.connect(self.toggle_play)
        self.fwd10.clicked.connect(lambda: self._seek_rel(+10000))
        if self._has_list:   # musiqa — oldingi/keyingi trek
            self.prev_btn.clicked.connect(lambda: self._goto(self.index - 1))
            self.next_btn.clicked.connect(lambda: self._goto(self.index + 1))
        else:                # audiokitob — ±60s o'tkazish
            self.prev_btn.clicked.connect(lambda: self._seek_rel(-60000))
            self.next_btn.clicked.connect(lambda: self._seek_rel(+60000))
        crow.addStretch(1)
        if self._has_list:
            crow.addWidget(self.prev_btn); crow.addSpacing(gap)
            crow.addWidget(self.back10); crow.addSpacing(gap)
        else:
            crow.addWidget(self.back10); crow.addSpacing(gap)
            crow.addWidget(self.prev_btn); crow.addSpacing(gap)
        crow.addWidget(self.play_btn)
        if self._has_list:
            crow.addSpacing(gap); crow.addWidget(self.fwd10)
            crow.addSpacing(gap); crow.addWidget(self.next_btn)
        else:
            crow.addSpacing(gap); crow.addWidget(self.next_btn)
            crow.addSpacing(gap); crow.addWidget(self.fwd10)
        crow.addStretch(1)
        return crow

    def _make_speed(self):
        self.speed_btn = self._btn("1x", T.s(46))
        self.speed_btn.clicked.connect(self._cycle_speed)
        srow = QHBoxLayout()
        srow.addStretch(1); srow.addWidget(self.speed_btn); srow.addStretch(1)
        return srow

    def _speed_widget(self):
        """⊕ + [1.0x (qalin) / Tezlik (mayda kulrang)] — bosilganda tezlik aylanadi.
        Mockupdagi ikki tonli tugma (QPushButton bitta shrift beradi)."""
        w = QFrame(); w.setObjectName("aSpeedW")
        w.setCursor(Qt.CursorShape.PointingHandCursor)
        l = QHBoxLayout(w)
        l.setContentsMargins(T.s(16), T.s(6), T.s(18), T.s(6)); l.setSpacing(T.s(10))
        ic = QLabel(); ic.setPixmap(_inline_icon(_SVG_PLUS, "#475569", T.s(20)))
        ic.setStyleSheet("background: transparent;")
        l.addWidget(ic)
        col = QVBoxLayout(); col.setContentsMargins(0, 0, 0, 0); col.setSpacing(0)
        self.speed_val = QLabel(f"{SPEEDS[self._speed_i]:g}x")
        self.speed_val.setObjectName("aSpeedVal")
        cap = QLabel(tr("player.speed")); cap.setObjectName("aSpeedCap")
        col.addWidget(self.speed_val); col.addWidget(cap)
        l.addLayout(col)
        w.mousePressEvent = lambda _e: self._cycle_speed()
        return w

    def _make_times(self):
        """Faqat joriy/umumiy vaqt (to'lqinsiz — audiokitob)."""
        self.wave = None
        self.cur = QLabel("00:00"); self.tot = QLabel("00:00")
        self.cur.setObjectName("aTime"); self.tot.setObjectName("aTime")

    def _pill(self, text, icon_svg=None):
        f = QFrame(); f.setObjectName("aPill")
        l = QHBoxLayout(f)
        l.setContentsMargins(T.s(14), T.s(7), T.s(14), T.s(7)); l.setSpacing(T.s(7))
        if icon_svg:
            ic = QLabel(); ic.setPixmap(_inline_icon(icon_svg, "#64748B", T.s(15)))
            ic.setStyleSheet("background: transparent;"); l.addWidget(ic)
        t = QLabel(text); t.setObjectName("aPillTx"); l.addWidget(t)
        return f

    def _vol_widgets(self, bl):
        vic = QLabel(); vic.setPixmap(svg_pixmap("volume-2", "#64748B", T.s(20)))
        vic.setStyleSheet("background: transparent;")
        bl.addWidget(vic)
        self.vol = QSlider(Qt.Orientation.Horizontal)
        self.vol.setObjectName("aVol")
        self.vol.setRange(0, 100); self.vol.setValue(80)
        self.vol.setFixedWidth(T.s(150))
        self.vol.valueChanged.connect(self._mp.audio_set_volume)
        bl.addWidget(self.vol)

    def _inner_pill(self, buttons):
        """Asbob tugmalarini ajralib turadigan (ichki, aniqroq) pill ichiga
        joylaydi — tashqi bar ochroq qoladi (mockupdagidek)."""
        f = QFrame(); f.setObjectName("aBarInner")
        il = QHBoxLayout(f)
        il.setContentsMargins(T.s(8), T.s(5), T.s(8), T.s(5)); il.setSpacing(T.s(4))
        for b in buttons:
            il.addWidget(b)
        return f

    def _toolbar_music(self):
        bar = QFrame(); bar.setObjectName("aBar")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(T.s(16), T.s(10), T.s(16), T.s(10)); bl.setSpacing(T.s(12))
        self._vol_widgets(bl)
        bl.addStretch(1)
        self.sleep_btn = self._tool_btn(tr("player.timer"), self._sleep_menu, _SVG_CLOCK)
        self.shuffle_btn = self._tool_btn(tr("player.shuffle"), self._toggle_shuffle, _SVG_SHUFFLE)
        self.fav_btn = self._tool_btn(tr("player.favorites"), self._toggle_fav, _SVG_HEART)
        bl.addWidget(self._inner_pill([self.sleep_btn, self.shuffle_btn, self.fav_btn]))
        return bar

    def _toolbar_book(self):
        # Mockup: tekis bar, 4 element teng oraliqda — Ovoz · Taymer · Boblar · Sevimlilar
        bar = QFrame(); bar.setObjectName("aBar")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(T.s(16), T.s(12), T.s(16), T.s(12)); bl.setSpacing(T.s(18))
        speed = self._speed_widget()
        self.sleep_btn = self._tool_btn(tr("player.timer"), self._sleep_menu, _SVG_CLOCK)
        chapters_btn = self._tool_btn(tr("player.chapters"), self._show_notes, _SVG_LIST)
        bl.addWidget(self._inner_pill([speed, chapters_btn, self.sleep_btn]))
        bl.addStretch(1)
        self._vol_widgets(bl)
        bl.addSpacing(T.s(18))
        self.cast_btn = self._icon_btn_inline(_SVG_CAST, None, T.s(44))
        bl.addWidget(self.cast_btn)
        return bar

    # ---- Audiokitob: muqova (chap) | ma'lumot (o'ng) — mockup ----
    def _build_book(self, root):
        main = QHBoxLayout(); main.setSpacing(T.s(48))
        main.setContentsMargins(T.s(80), T.s(56), T.s(80), T.s(48))
        # Muqova — chapda (portret), o'ng ustun qolgan joyni egallaydi
        self._make_cover(T.s(300), T.s(430))
        main.addWidget(self.cover, 0, Qt.AlignmentFlag.AlignVCenter)

        right = QVBoxLayout(); right.setSpacing(0)
        right.addStretch(1)

        badge = QFrame(); badge.setObjectName("aBadge")
        badge_l = QHBoxLayout(badge)
        badge_l.setContentsMargins(T.s(14), T.s(8), T.s(16), T.s(8))
        badge_l.setSpacing(T.s(8))
        badge_ic = QLabel(); badge_ic.setPixmap(_inline_icon(_SVG_WAVE, "#7C5CF6", T.s(16)))
        badge_ic.setStyleSheet("background: transparent;")
        badge_tx = QLabel(tr("player.now_playing")); badge_tx.setObjectName("aBadgeTx")
        badge_l.addWidget(badge_ic); badge_l.addWidget(badge_tx)
        right.addWidget(badge, 0, Qt.AlignmentFlag.AlignLeft)
        right.addSpacing(T.s(20))
        # Nom + muallif
        self._make_titles(center=False)
        right.addWidget(self.title)
        right.addSpacing(T.s(8))
        right.addWidget(self.author)
        right.addSpacing(T.s(22))
        meta = QHBoxLayout(); meta.setSpacing(T.s(12))
        meta.addWidget(self._pill(self.item.get("genre") or "Roman"))
        dur = self.item.get("duration") or 0
        meta.addWidget(self._pill(_fmt(int(dur) * 1000) if dur else "00:00", _SVG_CLOCK))
        meta.addStretch(1)
        right.addLayout(meta)
        right.addSpacing(T.s(28))

        self._make_times()
        self.progress = QSlider(Qt.Orientation.Horizontal)
        self.progress.setObjectName("aSeek")
        self.progress.setRange(0, 1000)
        self.progress.sliderPressed.connect(
            lambda: setattr(self, "_dragging", True))
        self.progress.sliderReleased.connect(self._on_seek)
        right.addWidget(self.progress)
        right.addSpacing(T.s(10))
        right.addLayout(self._time_row_book())
        right.addSpacing(T.s(30))
        right.addLayout(self._make_transport())
        right.addStretch(1)

        main.addLayout(right, 1)
        root.addLayout(main, 1)
        root.addWidget(self._toolbar_book())

    # ---- Musiqa: pleyer (chap) | playlist (o'ng) ----
    def _build_music(self, root):
        body = QHBoxLayout(); body.setSpacing(T.s(28))
        left = QVBoxLayout(); left.setSpacing(0); left.addStretch(1)
        self._make_cover(T.s(300), T.s(300))
        left.addWidget(self.cover, alignment=Qt.AlignmentFlag.AlignHCenter)
        left.addSpacing(T.s(24))
        self._make_titles(center=True)
        left.addWidget(self.title); left.addSpacing(T.s(4)); left.addWidget(self.author)
        left.addSpacing(T.s(28))
        self._make_wave()
        wt = QWidget(); wt.setMaximumWidth(T.s(460))
        wtl = QVBoxLayout(wt)
        wtl.setContentsMargins(0, 0, 0, 0); wtl.setSpacing(T.s(6))
        wtl.addWidget(self.wave); wtl.addLayout(self._time_row())
        left.addWidget(wt, 0, Qt.AlignmentFlag.AlignHCenter)
        left.addSpacing(T.s(20))
        left.addLayout(self._make_transport())
        left.addSpacing(T.s(12))
        left.addLayout(self._make_speed())
        left.addStretch(1)
        lwrap = QVBoxLayout()
        lwrap.addLayout(left, 1)
        lwrap.addWidget(self._toolbar_music())
        body.addLayout(lwrap, 5)
        body.addWidget(self._build_playlist_panel(), 4)
        root.addLayout(body, 1)

    def _build_playlist_panel(self):
        panel = QFrame(); panel.setObjectName("aPanel")
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(T.s(22), T.s(20), T.s(22), T.s(20))
        pl.setSpacing(T.s(14))
        head = QHBoxLayout()
        hdr = QLabel(tr("videos.tab.music")); hdr.setObjectName("aPanelHdr")
        head.addWidget(hdr); head.addStretch(1)
        gear = QLabel(); gear.setObjectName("aPanelGear")
        gear.setPixmap(_inline_icon(_SVG_SLIDERS, "#64748B", T.s(22)))
        gear.setStyleSheet("background: rgba(255,255,255,0.7);"
                           f" border-radius: {T.s(10)}px; padding: {T.s(6)}px;")
        head.addWidget(gear)
        pl.addLayout(head)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background: transparent;")
        host = QWidget(); host.setStyleSheet("background: transparent;")
        rows = QVBoxLayout(host)
        rows.setContentsMargins(0, 0, 0, 0); rows.setSpacing(T.s(12))
        self._pl_rows = []
        for i, it in enumerate(self.playlist):
            r = self._playlist_row(i, it)
            rows.addWidget(r)
            self._pl_rows.append(r)
        rows.addStretch(1)
        scroll.setWidget(host)
        pl.addWidget(scroll, 1)
        return panel

    def _playlist_row(self, i, it):
        row = _PlRow(i)
        row.setObjectName("plRow")
        row.setProperty("active", i == self.index)
        row.setCursor(Qt.CursorShape.PointingHandCursor)
        row.clicked.connect(self._goto)
        rl = QHBoxLayout(row)
        rl.setContentsMargins(T.s(16), T.s(13), T.s(12), T.s(13))
        rl.setSpacing(T.s(13))
        ind = QLabel(); ind.setObjectName("plInd")
        ind.setFixedSize(T.s(36), T.s(36))
        ind.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row._ind = ind
        rl.addWidget(ind)
        title = QLabel(it.get("title") or ""); title.setObjectName("plTitle")
        row._title = title
        rl.addWidget(title, 1)
        dur = it.get("duration") or 0
        dl = QLabel(_fmt(int(dur) * 1000) if dur else "")
        dl.setObjectName("plDur")
        rl.addWidget(dl)
        menu = QPushButton("⋮"); menu.setObjectName("plMenu")
        menu.setCursor(Qt.CursorShape.PointingHandCursor)
        menu.setFixedSize(T.s(30), T.s(36))
        menu.clicked.connect(lambda _c=False, idx=i: self._row_menu(idx))
        rl.addWidget(menu)
        sh = QGraphicsDropShadowEffect(row)
        sh.setBlurRadius(T.s(22)); sh.setOffset(0, T.s(5))
        sh.setColor(QColor(40, 55, 90, 45))
        row.setGraphicsEffect(sh)
        self._style_row(row, i == self.index)
        return row

    def _style_row(self, row, active):
        c = T.THEMES[self.theme_name]; accent = c["accent"]
        ind = row._ind
        if active:
            ind.setText("")
            ind.setPixmap(_inline_icon(_SVG_PLAY, "#FFFFFF", T.s(18)))
            ind.setStyleSheet(f"background: {accent}; border-radius: {T.s(18)}px;")
            row._title.setStyleSheet(
                f"background: transparent; color: {accent};"
                f" font-size: {T.FONT['body']}px; font-weight: 800;")
        else:
            ind.setPixmap(QPixmap())
            ind.setText(str(row._idx + 1) + ".")
            ind.setStyleSheet(
                f"background: transparent; color: {accent};"
                f" font-size: {T.s(16)}px; font-weight: 800;")
            row._title.setStyleSheet(
                f"background: transparent; color: {c['text']};"
                f" font-size: {T.FONT['body']}px; font-weight: 600;")

    def _row_menu(self, idx):
        btn = self.sender()
        it = self.playlist[idx]
        cid = it.get("id")
        m = QMenu(self)
        m.addAction(tr("player.play")).triggered.connect(lambda: self._goto(idx))
        fav = cid in self._fav_ids()
        act = m.addAction(tr("player.fav_remove") if fav
                          else tr("player.fav_add"))

        def _togg():
            ids = self._fav_ids()
            ids.discard(cid) if cid in ids else ids.add(cid)
            cache.save_json("favorites", sorted(x for x in ids if x is not None))
            if idx == self.index:
                self._update_fav_btn()
        act.triggered.connect(_togg)
        pos = (btn.mapToGlobal(btn.rect().bottomLeft()) if btn
               else self.mapToGlobal(self.rect().center()))
        m.exec(pos)

    def _icon_btn_inline(self, svg, slot, size):
        b = QPushButton()
        b.setObjectName("aIconBtn")
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setFixedSize(size, size)
        b.setIcon(QIcon(_inline_icon(svg, "#334155", T.s(22))))
        b.setIconSize(QSize(T.s(22), T.s(22)))
        b._sz = size
        if slot:
            b.clicked.connect(slot)
        return b

    def _tool_btn(self, text, slot, icon_svg=None):
        b = QPushButton("  " + text if icon_svg else text)
        b.setObjectName("aTool")
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setFixedHeight(T.s(58) if "\n" in text else T.s(46))
        if icon_svg:
            b.setIcon(QIcon(_inline_icon(icon_svg, "#475569", T.s(20))))
            b.setIconSize(QSize(T.s(20), T.s(20)))
        b.clicked.connect(slot)
        return b

    def _set_cover(self):
        """Muqova bor bo'lsa serverdan yuklaydi; yo'q bo'lsa — gradient + nota
        (CoverLabel.music_placeholder — kartochkalar bilan bir xil ko'rinish)."""
        if self.item.get("cover_path"):
            self.cover.load(self.api.cover_url(self.item["id"]))
        else:
            self.cover.music_placeholder()

    def _btn(self, text, size, accent=False, icon=None, svg=None):
        b = QPushButton(text)
        b.setObjectName("aAccent" if accent else "aBtn")
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setFixedSize(size, size)
        b._sz = size            # _restyle har tugmaga to'liq uslubni o'zi beradi
        b._accent = accent
        if svg:                 # inline monoxrom ikonka (emoji-glyph emas)
            col = "#FFFFFF" if accent else "#334155"
            b.setIcon(QIcon(_inline_icon(svg, col, T.s(26))))
            b.setIconSize(QSize(T.s(22), T.s(22)))
        elif icon:
            b.setIcon(svg_icon(icon, "#FFFFFF", 64))
            b.setIconSize(QSize(int(size * 0.42), int(size * 0.42)))
        self._ctrl_btns.append(b)
        return b

    def _style_ctrl_btns(self):
        """Boshqaruv tugmalariga 'shisha' (glassy) uslub — har qanday rangli
        fon ustida aniq ko'rinadi. Play — to'la accent doira; qolganlari
        yarim shaffof oq doira (frosted)."""
        c = T.THEMES[self.theme_name]
        accent_override = "#7C5CF6" if not self._has_list else c["accent"]
        for b in self._ctrl_btns:
            r = b._sz // 2
            if b._accent:
                b.setStyleSheet(
                    f"QPushButton {{ background: {accent_override}; color: #FFFFFF;"
                    f" border: none; border-radius: {r}px; font-size: {T.s(24)}px;"
                    f" font-weight: 700; }}"
                    f"QPushButton:hover {{ background: {'#6D4BEF' if not self._has_list else '#1D4ED8'}; }}"
                    f"QPushButton:pressed {{ background: {'#5C3FE0' if not self._has_list else '#1E40AF'}; }}")
            else:
                b.setStyleSheet(
                    f"QPushButton {{ background: rgba(255,255,255,0.80);"
                    f" color: {c['text']}; border: 1px solid rgba(255,255,255,0.65);"
                    f" border-radius: {r}px; font-size: {T.s(15)}px;"
                    f" font-weight: 700; }}"
                    f"QPushButton:hover {{ background: rgba(255,255,255,0.95); }}"
                    f"QPushButton:pressed {{ background: rgba(230,236,245,0.95); }}")

    def _set_play_icon(self, name):
        # _refresh tez-tez chaqiriladi — ikonka faqat o'zgarganda yangilanadi.
        if getattr(self, "_play_icon_name", None) == name:
            return
        self._play_icon_name = name
        self.play_btn.setIcon(svg_icon(name, "#FFFFFF", 64))

    # --- O'ynatish ---
    def start(self):
        self._restyle()
        from core.overlay import show_over_host
        show_over_host(self, self._host)
        self._bg_anim.start()
        self._load_current()
        self._mp.audio_set_volume(self.vol.value())

    def _load_current(self):
        """Joriy index'dagi trekni yuklab o'ynatadi va UI'ni yangilaydi."""
        self.item = self.playlist[self.index]
        self._pal0 = self.index   # har qo'shiq boshqa rang kombinatsiyasidan
        # Lokal keshda bo'lsa — fayldan (oflaynda ham ishlaydi)
        self._media = self._instance.media_new(self.api.play_url(self.item["id"]))
        self._mp.set_media(self._media)
        self._mp.play()
        self._mp.set_rate(SPEEDS[self._speed_i])
        if self.wave is not None:
            self.wave.set_progress(0.0)
        if self.progress is not None:
            self.progress.setValue(0)
        self.cur.setText("00:00")
        self.tot.setText("00:00")
        self._apply_state()

    def _goto(self, idx):
        """Playlistda boshqa trekka o'tadi (chegaradan tashqari — e'tiborsiz)."""
        if 0 <= idx < len(self.playlist) and idx != self.index:
            self.index = idx
            self._load_current()

    def _advance(self):
        """Keyingi trek: Aralash yoqilgan bo'lsa tasodifiy, aks holda ketma-ket."""
        if self._shuffle and len(self.playlist) > 1:
            import random
            nxt = self.index
            while nxt == self.index:
                nxt = random.randint(0, len(self.playlist) - 1)
            self._goto(nxt)
        elif self.index < len(self.playlist) - 1:
            self._goto(self.index + 1)

    def _refresh_playlist(self):
        """Playlist panelda joriy qatorni ajratib ko'rsatadi (▶ doira + accent)."""
        for i, row in enumerate(self._pl_rows):
            active = (i == self.index)
            row.setProperty("active", active)
            self._style_row(row, active)
            row.style().unpolish(row); row.style().polish(row)

    # --- Aralash / Sevimlilar (musiqa) ---
    def _toggle_shuffle(self):
        self._shuffle = not self._shuffle
        self.shuffle_btn.setProperty("on", self._shuffle)
        self.shuffle_btn.setIcon(QIcon(_inline_icon(
            _SVG_SHUFFLE, "#FFFFFF" if self._shuffle else "#475569", T.s(20))))
        self.shuffle_btn.style().unpolish(self.shuffle_btn)
        self.shuffle_btn.style().polish(self.shuffle_btn)

    def _fav_ids(self):
        hit = cache.load_json("favorites")
        return set(hit[0]) if hit and isinstance(hit[0], list) else set()

    def _toggle_fav(self):
        ids = self._fav_ids()
        cid = self.item.get("id")
        ids.discard(cid) if cid in ids else ids.add(cid)
        cache.save_json("favorites", sorted(x for x in ids if x is not None))
        self._update_fav_btn()

    def _update_fav_btn(self):
        if not hasattr(self, "fav_btn"):
            return
        fav = self.item.get("id") in self._fav_ids()
        self.fav_btn.setText("  " + (tr("player.favorite") if fav
                                     else tr("player.favorites")))
        self.fav_btn.setProperty("on", fav)
        self.fav_btn.setIcon(QIcon(_inline_icon(
            _SVG_HEART_FILL if fav else _SVG_HEART,
            "#FFFFFF" if fav else "#475569", T.s(20))))
        self.fav_btn.style().unpolish(self.fav_btn)
        self.fav_btn.style().polish(self.fav_btn)

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
        # Musiqa — kichik doira (speed_btn); kitob — ikki tonli pill (speed_val)
        if self._has_list:
            self.speed_btn.setText(f"{rate:g}x")
        else:
            self.speed_val.setText(f"{rate:g}x")

    def _book_menu(self):
        btn = self.sender()
        m = QMenu(self)
        m.addAction(tr("player.mark_pos")).triggered.connect(self._add_note)
        fav = self.item.get("id") in self._fav_ids()
        a = m.addAction(tr("player.fav_remove") if fav
                        else tr("player.fav_add"))
        a.triggered.connect(self._toggle_fav)
        pos = (btn.mapToGlobal(btn.rect().bottomLeft()) if btn
               else self.mapToGlobal(self.rect().center()))
        m.exec(pos)

    def _on_seek(self):
        """Progress slayderdan istalgan joyga o'tish."""
        length = self._mp.get_length()
        if length > 0:
            self._mp.set_time(int(length * self.progress.value() / 1000))
        self._dragging = False

    # --- Uyqu taymeri ---
    def _sleep_menu(self):
        btn = self.sender()
        m = QMenu(self)
        items = [(tr("player.timer_off"), 0)]
        items += [(tr("dur.min", m=n), n) for n in (15, 30, 45, 60)]
        for label, mins in items:
            act = m.addAction(label)
            act.triggered.connect(
                lambda _c=False, mn=mins: self._set_sleep(mn))
        pos = (btn.mapToGlobal(btn.rect().topLeft()) if btn
               else self.mapToGlobal(self.rect().center()))
        m.exec(pos)

    def _set_sleep(self, minutes):
        if minutes <= 0:
            self._sleep_deadline = None
            self.sleep_btn.setText(tr("player.timer"))
        else:
            self._sleep_deadline = time.monotonic() + minutes * 60
            self.sleep_btn.setText(tr("player.timer_val", t=tr("dur.min", m=minutes)))

    # --- Eslatma / xatcho'p (lokal, har kitob uchun) ---
    def _notes_key(self):
        return f"notes_{self.item.get('id')}"

    def _load_notes(self):
        hit = cache.load_json(self._notes_key())
        return list(hit[0]) if hit and isinstance(hit[0], list) else []

    def _add_note(self):
        t = max(0, self._mp.get_time())
        text, ok = QInputDialog.getText(
            self, tr("player.note_title"),
            tr("player.note_body", t=_fmt(t)))
        if not ok:
            return
        notes = self._load_notes()
        notes.append({"t": int(t), "text": (text or "").strip()})
        notes.sort(key=lambda x: x.get("t", 0))
        cache.save_json(self._notes_key(), notes)

    def _show_notes(self):
        notes = self._load_notes()
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("player.notes"))
        dlg.setMinimumSize(T.s(380), T.s(440))
        lay = QVBoxLayout(dlg)
        lst = QListWidget()
        for nm in notes:
            txt = _fmt(int(nm.get("t", 0)))
            if nm.get("text"):
                txt += "  —  " + nm["text"]
            QListWidgetItem(txt, lst)
        if not notes:
            lst.addItem(tr("player.no_notes"))
            lst.setEnabled(False)
        lay.addWidget(lst)

        def jump():
            row = lst.currentRow()
            if notes and 0 <= row < len(notes):
                self._mp.set_time(int(notes[row].get("t", 0)))
                dlg.accept()
        lst.itemDoubleClicked.connect(lambda _i: jump())
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        go = btns.addButton(tr("player.goto"), QDialogButtonBox.ButtonRole.AcceptRole)
        go.clicked.connect(jump)
        if notes:
            clr = btns.addButton(tr("player.clear"),
                                 QDialogButtonBox.ButtonRole.DestructiveRole)
            clr.clicked.connect(
                lambda: (cache.save_json(self._notes_key(), []), dlg.accept()))
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)
        dlg.exec()

    def _refresh(self):
        if getattr(self, "_closing", False):
            return   # VLC bo'shatilgandan keyin timer signali kelsa — e'tiborsiz
        state = self._mp.get_state()
        # Playlist: trek tugasa keyingisiga (Aralash bo'lsa tasodifiy)
        if state == vlc.State.Ended and self._has_list:
            if self._shuffle or self.index < len(self.playlist) - 1:
                self._advance()
                return
        if state == vlc.State.Ended:
            self._set_play_icon("rotate-ccw")
        elif state == vlc.State.Playing:
            self._set_play_icon("pause")
        else:
            self._set_play_icon("play")
        self._playing = (state == vlc.State.Playing)
        if self.wave is not None:
            self.wave.set_active(self._playing)            # jonli ekvalayzer + puls
        length = self._mp.get_length()
        cur = self._mp.get_time()
        self.cur.setText(_fmt(cur))
        self.tot.setText(_fmt(length))
        wave_drag = self.wave._dragging if self.wave is not None else False
        if length > 0 and not wave_drag:
            pos = 1.0 if state == vlc.State.Ended else cur / length
            if self.wave is not None:
                self.wave.set_progress(pos)
            if self.progress is not None and not self._dragging:
                self.progress.setValue(int(1000 * pos))
        # Uyqu taymeri — vaqt tugasa pauza; aks holda qolgan vaqtni ko'rsatamiz
        if self._sleep_deadline is not None:
            rem = self._sleep_deadline - time.monotonic()
            if rem <= 0:
                self._sleep_deadline = None
                self._mp.pause()
                self.sleep_btn.setText(tr("player.timer"))
            else:
                self.sleep_btn.setText(
                    tr("player.timer_val", t=_fmt(int(rem * 1000))))

    def stop_and_close(self):
        if getattr(self, "_closing", False):
            return
        self._closing = True
        self._sleep_deadline = None
        self._timer.stop()
        self._bg_anim.stop()
        if self.wave is not None:
            self.wave.set_active(False)   # ekvalayzer animatsiyasini to'xtatamiz
        # Ovoz slayderi libVLC C funksiyasiga ulangan — pleyer bo'shatilgach
        # signal yetib bormasin (freed obyektga chaqiruv crash beradi).
        try:
            self.vol.valueChanged.disconnect()
        except (TypeError, RuntimeError):
            pass
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
        # T.s() ni qurilishdagi kabi OYNA masshtabiga o'tkazib uslublaymiz
        _old_scale = T.SCALE
        T.SCALE = self._S
        try:
            self._restyle_impl()
        finally:
            T.SCALE = _old_scale

    def _restyle_impl(self):
        c = T.THEMES[self.theme_name]
        # Fon oq (Reader bilan bir xil); dark mavzuda mavzu foni.
        # MUHIM: yalang'och "background:" selektor bloklari bilan aralashsa Qt
        # stylesheet'ni parse qilolmaydi — shuning uchun klass selektori bilan.
        bg = "#FFFFFF" if self.theme_name == "light" else c["bg"]
        self.setStyleSheet(f"AudioPlayer {{ background: {bg}; }}")
        if self.wave is not None:
            self.wave.set_colors(c["accent"], "#C7CDD8")
        back_ac = "#7C5CF6" if not self._has_list else c["accent"]
        self.back.setStyleSheet(
            f"#aBack {{ background: rgba(255,255,255,0.72); color: {back_ac};"
            f" border: 1px solid rgba(255,255,255,0.65);"
            f" border-radius: {T.s(27)}px;"
            f" padding: {T.s(13)}px {T.s(30)}px {T.s(13)}px {T.s(26)}px;"
            f" font-size: {T.FONT['nav']}px; font-weight: 700;"
            f" letter-spacing: 0.3px; }}"
            f"#aBack:hover {{ background: rgba(255,255,255,0.95); }}"
            f"#aBack:pressed {{ background: rgba(232,236,248,0.95); }}")
        title_size = T.s(54) if not self._has_list else T.FONT["title"]
        author_size = T.s(26) if not self._has_list else T.FONT["body"]
        time_size = T.s(18) if not self._has_list else T.FONT["small"]
        self.title.setStyleSheet(
            f"#aTitle {{ color: {c['text']}; font-size: {title_size}px;"
            f" font-weight: 800; letter-spacing: 0.3px; }}")
        self.author.setStyleSheet(
            f"#aAuthor {{ color: {'#7C5CF6' if not self._has_list else c['accent']};"
            f" font-size: {author_size}px; font-weight: 700; letter-spacing: 0px; }}")
        for l in (self.cur, self.tot):
            l.setStyleSheet(f"#aTime {{ color: {c['text_secondary']};"
                            f" font-size: {time_size}px; }}")
        if hasattr(self, "chapter_counter"):
            self.chapter_counter.setStyleSheet(
                f"#aChapterCounter {{ color: {c['text_secondary']};"
                f" font-size: {time_size}px; font-weight: 600; }}")
        # Boshqaruv tugmalari — glassy (har tugmaga to'liq uslub, o'z radiusi bilan)
        self._style_ctrl_btns()
        accent = "#7C5CF6" if not self._has_list else c["accent"]
        # Badge, ikonka tugma, asboblar paneli, slayderlar
        self.setStyleSheet(self.styleSheet() + (
            f"#aBadge {{ background: rgba(124,92,246,0.13);"
            f" border-radius: {T.s(15)}px; }}"
            f"#aBadgeTx {{ background: transparent; color: {accent};"
            f" font-size: {T.s(14)}px; font-weight: 700; letter-spacing: 0.5px; }}"
            f"#aPill {{ background: rgba(255,255,255,0.46);"
            f" border: 1px solid rgba(124,92,246,0.10); border-radius: {T.s(22)}px; }}"
            f"#aPillTx {{ background: transparent; color: {c['text']};"
            f" font-size: {T.s(16)}px; font-weight: 600; }}"
            f"#aIconBtn {{ background: rgba(255,255,255,0.85); border: none;"
            f" border-radius: {T.s(26)}px; }}"
            f"#aIconBtn:hover {{ background: #FFFFFF; }}"
            f"#aDots {{ background: rgba(255,255,255,0.72);"
            f" border: 1px solid rgba(255,255,255,0.65);"
            f" border-radius: {T.s(26)}px; color: {c['text']};"
            f" font-size: {T.s(26)}px; font-weight: 700; }}"
            f"#aDots:hover {{ background: rgba(255,255,255,0.95); }}"
            f"#aBar {{ background: rgba(255,255,255,0.38);"  # tashqi — ochroq
            f" border-radius: {T.s(28)}px; }}"
            f"#aBarInner {{ background: rgba(255,255,255,0.92);"  # ichki — aniqroq
            f" border: 1px solid rgba(124,92,246,0.10); border-radius: {T.s(22)}px; }}"
            f"#aTool {{ background: transparent; color: {c['text']}; border: none;"
            f" border-radius: {T.s(22)}px; padding: 0 {T.s(24)}px;"
            f" font-size: {T.s(16)}px; font-weight: 600; text-align: left; }}"
            f"#aTool:hover {{ background: rgba(255,255,255,0.92); }}"
            f"#aTool:pressed {{ background: rgba(228,234,244,0.95); }}"
            f"#aTool[on=\"true\"] {{ background: {accent}; color: #FFFFFF; }}"
            # Tezlik — ikki tonli pill (1.0x qalin / Tezlik mayda kulrang)
            f"#aSpeedW {{ background: transparent; border: none;"
            f" border-radius: {T.s(22)}px; }}"
            f"#aSpeedW:hover {{ background: rgba(255,255,255,0.92); }}"
            f"#aSpeedVal {{ background: transparent; color: {c['text']};"
            f" font-size: {T.s(18)}px; font-weight: 800; }}"
            f"#aSpeedCap {{ background: transparent; color: {c['text_secondary']};"
            f" font-size: {T.s(13)}px; font-weight: 600; }}"
            # Playlist panel + qatorlar
            f"#aPanel {{ background: rgba(255,255,255,0.45);"
            f" border-radius: {T.RADIUS['card']}px; }}"
            f"#aPanelHdr {{ background: transparent; color: {c['text']};"
            f" font-size: {T.FONT['h2']}px; font-weight: 800; }}"
            f"#plRow {{ background: rgba(255,255,255,0.92);"
            f" border-radius: {T.s(16)}px; }}"
            f"#plRow:hover {{ background: #FFFFFF; }}"
            f"#plRow[active=\"true\"] {{ background: rgba(124,108,246,0.13); }}"
            f"#plDur {{ background: transparent; color: {c['text_secondary']};"
            f" font-size: {T.s(14)}px; }}"
            f"#plMenu {{ background: transparent; color: {c['text_secondary']};"
            f" border: none; font-size: {T.s(20)}px; font-weight: 700; }}"
            f"#plMenu:hover {{ color: {c['text']}; }}"
            f"#aSeek::groove:horizontal {{ height: {T.s(6)}px;"
            f" border-radius: {T.s(3)}px; background: rgba(120,130,150,0.28); }}"
            f"#aSeek::sub-page:horizontal {{ height: {T.s(6)}px;"
            f" border-radius: {T.s(3)}px; background: {accent}; }}"
            f"#aSeek::handle:horizontal {{ width: {T.s(18)}px; height: {T.s(18)}px;"
            f" margin: -{T.s(6)}px 0; border-radius: {T.s(9)}px;"
            f" background: #FFFFFF; border: {T.s(3)}px solid {accent}; }}"
            f"#aVol::groove:horizontal {{ height: {T.s(5)}px;"
            f" border-radius: {T.s(2)}px; background: rgba(120,130,150,0.28); }}"
            f"#aVol::sub-page:horizontal {{ height: {T.s(5)}px;"
            f" border-radius: {T.s(2)}px; background: {accent}; }}"
            f"#aVol::handle:horizontal {{ width: {T.s(14)}px; height: {T.s(14)}px;"
            f" margin: -{T.s(5)}px 0; border-radius: {T.s(7)}px; background: {accent}; }}"))
        if self._has_list and self._pl_rows:
            self._refresh_playlist()   # qatorlar uslubini joriy mavzuga moslash
