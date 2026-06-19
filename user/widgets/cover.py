"""
cover.py — Muqova rasmini serverdan yuklab ko'rsatadigan QLabel.

Server muqovani fayl (jpg/png) yoki dinamik SVG sifatida qaytaradi.
Yuklash tarmoq orqali bo'lgani uchun alohida oqimda (UI qotmaydi);
rasm baytlari kelgach, asosiy oqimda QPixmap'ga aylantiriladi.
"""
import logging
from collections import OrderedDict

import requests
from PyQt6.QtWidgets import QLabel, QSizePolicy, QGraphicsOpacityEffect
from PyQt6.QtCore import (Qt, QThread, pyqtSignal, QByteArray, QRectF, QSize,
                          QPropertyAnimation, QEasingCurve, QVariantAnimation)
from PyQt6.QtGui import (QPixmap, QPainter, QColor, QLinearGradient, QBrush,
                         QFont, QPainterPath)
from PyQt6.QtSvg import QSvgRenderer
from core import cache
from core import netpin
from core import theme as T
from core.threads import track

log = logging.getLogger(__name__)

# Xotiradagi LRU kesh: url -> dekodlangan QPixmap. Grid har qayta render
# bo'lganda bir xil muqovalar serverdan qayta tortilmasin (tezroq + kam trafik).
_MEM_CACHE = OrderedDict()
_MEM_CACHE_MAX = 200


def _mem_get(url):
    pm = _MEM_CACHE.get(url)
    if pm is not None:
        _MEM_CACHE.move_to_end(url)
    return pm


def _mem_put(url, pm):
    _MEM_CACHE[url] = pm
    _MEM_CACHE.move_to_end(url)
    while len(_MEM_CACHE) > _MEM_CACHE_MAX:
        _MEM_CACHE.popitem(last=False)


class _Fetcher(QThread):
    done = pyqtSignal(bytes, str)   # (data, content_type)
    fail = pyqtSignal()

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            r = netpin.get(self.url, timeout=8)
            r.raise_for_status()
            cache.save_cover(self.url, r.content)   # oflayn uchun diskka
            self.done.emit(r.content, r.headers.get("content-type", ""))
        except requests.RequestException:
            # Server o'chiq — disk keshidan urinamiz (oflayn rejim)
            data = cache.load_cover(self.url)
            if data is not None:
                self.done.emit(data, "")
                return
            log.debug("Muqova yuklanmadi: %s", self.url)
            self.fail.emit()


class CoverLabel(QLabel):
    """Muqova / thumbnail; manzil berilsa serverdan yuklaydi.

    Ikki rejim:
      - qat'iy: `aspect=None` (default) — width×height qat'iy o'lcham.
      - moslashuvchan: `aspect` berilsa (masalan 16/9) — mavjud kenglikni
        to'ldiradi, balandlik avtomatik (kenglik/aspect), o'lcham o'zgarsa
        rasm qayta miqyoslanadi (grid 3 ustunni to'ldirishi uchun).
    """

    def __init__(self, width=200, height=280, radius=None, aspect=None,
                 round_top_only=False):
        super().__init__()
        self._radius = T.RADIUS["card"] if radius is None else radius
        self._aspect = aspect
        self._round_top_only = round_top_only   # faqat tepa burchaklar (modal header)
        self._orig = None          # yuklangan asl pixmap (qayta miqyoslash uchun)
        self._fetcher = None
        self._music_ph = False     # muqovasiz musiqa: gradient + nota placeholder
        self.fade_on_next = False  # keyingi load() mem-keshdan ham fade bilan
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if aspect is None:
            self._w, self._h = width, height
            self.setFixedSize(width, height)
        else:
            self._w = width
            self._h = max(1, round(width / aspect))
            self.setMinimumWidth(10)
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.setFixedHeight(self._h)
        self._show_placeholder("...")

    def sizeHint(self):
        return QSize(self._w, self._h)

    def music_placeholder(self):
        """Muqovasiz musiqa uchun chiroyli gradient + nota (♪). load() o'rniga
        chaqiriladi; resize'da (aspect rejim) qayta chiziladi."""
        self._music_ph = True
        self._orig = None
        self._draw_music()

    def _draw_music(self):
        if self._w < 2 or self._h < 2:
            return
        base = QPixmap(self._w, self._h)
        base.fill(Qt.GlobalColor.transparent)
        p = QPainter(base)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        g = QLinearGradient(0, 0, self._w, self._h)
        g.setColorAt(0.0, QColor("#6366F1"))
        g.setColorAt(1.0, QColor("#8B5CF6"))
        p.fillRect(0, 0, self._w, self._h, QBrush(g))
        p.setPen(QColor(255, 255, 255, 235))
        f = QFont()
        f.setPixelSize(max(24, min(self._w, self._h) // 2))
        p.setFont(f)
        p.drawText(base.rect(), Qt.AlignmentFlag.AlignCenter, "♪")
        p.end()
        # _rounded burchaklarni (round_top_only ham) hisobga olib kesadi
        self.setPixmap(self._rounded(base))

    def load(self, url):
        self._music_ph = False
        # Avval xotira keshi — bor bo'lsa tarmoqsiz, oqimsiz darhol chizamiz
        # (_render_scaled fade_on_next bo'lsa crossfade'ni o'zi bajaradi)
        pm = _mem_get(url)
        if pm is not None:
            self._orig = pm
            self._render_scaled()
            return
        self._url = url
        # Eski fetcher hali ishlayotgan bo'lsa, uni majburan to'xtatmaymiz
        # (terminate xavfli) — track() uni tugagunicha tirik saqlaydi; oxirgi
        # boshlangan so'rov natijasi ko'rsatiladi.
        fetcher = track(_Fetcher(url))
        fetcher._url = url   # natijani O'Z url'iga bog'laymiz (kesh poisoning'siz)
        self._fetcher = fetcher
        self._fetcher.done.connect(self._on_data)
        self._fetcher.fail.connect(self._on_fail)
        self._fetcher.start()

    def _on_fail(self):
        # Karta allaqachon o'chirilgan bo'lishi mumkin (ro'yxat qayta render
        # bo'lganda) — C++ obyektga chaqiruv RuntimeError beradi, e'tiborsiz.
        try:
            self._show_placeholder("?")
        except RuntimeError:
            pass

    def resizeEvent(self, e):
        # Moslashuvchan rejimda kenglik o'zgarsa — balandlikni 16:9 saqlab,
        # rasmni qayta chizamiz.
        if self._aspect is not None:
            self._w = max(1, self.width())
            h = max(1, round(self._w / self._aspect))
            if h != self.height():
                self.setFixedHeight(h)
            self._h = h
            if self._music_ph:
                self._draw_music()
            elif self._orig is not None:
                self._render_scaled()
            else:
                self._show_placeholder("...")
        super().resizeEvent(e)

    def _on_data(self, data, ctype):
        # Karta ro'yxat qayta render bo'lganda o'chirilgan bo'lishi mumkin —
        # C++ obyektga chaqiruv RuntimeError beradi, butun ilovani crash qilmasin.
        try:
            if not data:
                self._show_placeholder("?")
                return
            if "svg" in ctype or data[:5] == b"<svg " or data[:6] == b"<?xml ":
                renderer = QSvgRenderer(QByteArray(data))
                if not renderer.isValid():
                    self._show_placeholder("?")
                    return
                bw, bh = max(self._w, 480), max(self._h, 270)
                pm = QPixmap(bw, bh)
                pm.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pm)
                renderer.render(painter, QRectF(0, 0, bw, bh))
                painter.end()
                self._orig = pm
            else:
                raw = QPixmap()
                raw.loadFromData(data)
                if raw.isNull():
                    self._show_placeholder("?")
                    return
                self._orig = raw
            # Kesh kalitini fetcher'ning O'Z url'idan olamiz — tez qayta yuklashda
            # eski fetcher natijasi yangi url ostiga yozilib qolmasin.
            src = self.sender()
            key = getattr(src, "_url", None) or getattr(self, "_url", None)
            if key:
                _mem_put(key, self._orig)
            want_cross = self.fade_on_next   # crossfade _render_scaled ichida
            self._render_scaled()
            if not want_cross:
                self._fade_in()   # birinchi yuklanish — yumshoq paydo bo'lish
        except RuntimeError:
            pass

    def _fade_in(self):
        """Yangi yuklangan muqovani yumshoq paydo qiladi (220ms)."""
        eff = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(eff)
        self._fade = QPropertyAnimation(eff, b"opacity", self)
        self._fade.setDuration(220)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade.finished.connect(self._end_fade)
        self._fade.start()

    def _end_fade(self):
        # Effektni olib tashlaymiz — doimiy offscreen bufer scroll'ni sekinlatadi
        try:
            self.setGraphicsEffect(None)
        except RuntimeError:
            pass  # karta ro'yxat qayta renderida o'chirilgan bo'lishi mumkin

    def _compose(self, src):
        """Rasmni qutiga KESMASDAN joylaydi: butun rasm (fit) markazda sharp
        ko'rinadi; nisbat mos kelmasa (portret poster 16:9 kartaga) bo'sh yonlar
        o'sha rasmning XIRA (blur) nusxasi bilan to'ladi. Landshaft rasmlar
        qutini to'liq qoplaydi — blur ko'rinmaydi (avvalgidek)."""
        w, h = self._w, self._h
        canvas = QPixmap(w, h)
        canvas.fill(Qt.GlobalColor.transparent)
        p = QPainter(canvas)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        fit = src.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio,
                         Qt.TransformationMode.SmoothTransformation)
        if fit.width() < w - 1 or fit.height() < h - 1:
            # Bo'sh joy bor — orqaga blurli to'ldirish (arzon: kichraytir-kattalashtir)
            fill = src.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                              Qt.TransformationMode.SmoothTransformation)
            small = fill.scaled(max(1, w // 12), max(1, h // 12),
                                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                Qt.TransformationMode.SmoothTransformation)
            blur = small.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                Qt.TransformationMode.SmoothTransformation)
            p.drawPixmap((w - blur.width()) // 2, (h - blur.height()) // 2, blur)
            p.fillRect(0, 0, w, h, QColor(8, 12, 24, 90))   # yengil qoraytirish
        p.drawPixmap((w - fit.width()) // 2, (h - fit.height()) // 2, fit)
        p.end()
        return canvas

    def _render_scaled(self):
        if self._orig is None or self._w < 2 or self._h < 2:
            return
        out = self._rounded(self._compose(self._orig))
        old = self.pixmap()
        # fade_on_next: eski rasm yangisiga ERIYDI (crossfade) — opacity
        # "blink"isiz, zamonaviy almashinish (aylanma tavsiya uchun).
        if (self.fade_on_next and old is not None and not old.isNull()
                and old.size() == out.size()):
            self.fade_on_next = False
            self._crossfade(old, out)
        else:
            self.fade_on_next = False
            self.setPixmap(out)

    def _crossfade(self, old, new, dur=420):
        anim = QVariantAnimation(self)
        anim.setDuration(dur)
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
            try:
                self.setPixmap(pm)
            except RuntimeError:
                anim.stop()   # widget o'chirilgan bo'lishi mumkin

        anim.valueChanged.connect(_step)
        anim.finished.connect(lambda: self._safe_set(new))
        anim.start()
        self._cross = anim

    def _safe_set(self, pm):
        try:
            self.setPixmap(pm)
        except RuntimeError:
            pass

    def _rounded(self, pm):
        """Rasmni markazlab, burchaklarni yumaloqlab kesadi."""
        out = QPixmap(self._w, self._h)
        out.fill(Qt.GlobalColor.transparent)
        p = QPainter(out)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        from PyQt6.QtGui import QPainterPath
        path = QPainterPath()
        if self._round_top_only:
            r, w, h = self._radius, self._w, self._h
            path.moveTo(0, h)
            path.lineTo(0, r)
            path.arcTo(0, 0, 2 * r, 2 * r, 180, -90)        # tepa-chap
            path.lineTo(w - r, 0)
            path.arcTo(w - 2 * r, 0, 2 * r, 2 * r, 90, -90)  # tepa-o'ng
            path.lineTo(w, h)
            path.closeSubpath()
        else:
            path.addRoundedRect(0, 0, self._w, self._h, self._radius, self._radius)
        p.setClipPath(path)
        x = (self._w - pm.width()) // 2
        y = (self._h - pm.height()) // 2
        p.drawPixmap(x, y, pm)
        p.end()
        return out

    def _show_placeholder(self, text):
        if self._w < 2 or self._h < 2:
            return
        pm = QPixmap(self._w, self._h)
        pm.fill(QColor("#475569"))
        p = QPainter(pm)
        p.setPen(QColor("#FFFFFF"))
        p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, text)
        p.end()
        self.setPixmap(self._rounded(pm))
