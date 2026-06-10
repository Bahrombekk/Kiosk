"""
routemap.py — Marshrutning toza VEKTOR xaritasi (offline, rasm/plitkasiz).

Bekatlarni geografik joylashuviga (lon/lat) qarab silliq fon ustida chizadi:
  - yumshoq "xarita" foni + faint graticule (to'r) chiziqlari;
  - marshrut chizig'i (o'tilgan qism to'liq ko'k, qolgani uzuq kulrang);
  - bekat nuqtalari (o'tilgan: to'la, joriy: halqa, kelgusi: bo'sh) + nomli pill;
  - joriy bekatda PULSlanuvchi halqa va keyingi bekat sari harakatlanuvchi
    poyezd nuqtasi (animatsiya).

Interfeys SlippyMap bilan bir xil: set_route(stops, current, theme_name).
Geografik koordinatasi noma'lum bekatlar qo'shnilari orasida interpolatsiya
qilinadi; hech biri tanilmasa diagonal bo'ylab teng joylashtiriladi.
"""
import math
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt6.QtGui import (QPainter, QColor, QPen, QBrush, QFont, QFontMetrics,
                         QPainterPath, QLinearGradient)

from core import theme as T

# Asosiy O'zbekiston shaharlari — (lon, lat). Kalitlar normalizatsiya qilingan.
_CITY = {
    "toshkent": (69.24, 41.31), "tashkent": (69.24, 41.31),
    "guliston": (68.79, 40.49), "gulistan": (68.79, 40.49),
    "jizzax": (67.84, 40.12), "jizzakh": (67.84, 40.12),
    "samarqand": (66.96, 39.65), "samarkand": (66.96, 39.65),
    "navoiy": (65.38, 40.10), "navoi": (65.38, 40.10),
    "buxoro": (64.42, 39.77), "bukhara": (64.42, 39.77),
    "qarshi": (65.79, 38.86), "karshi": (65.79, 38.86),
    "termiz": (67.28, 37.22), "termez": (67.28, 37.22),
    "nukus": (59.61, 42.46),
    "urganch": (60.63, 41.55), "urgench": (60.63, 41.55),
    "xiva": (60.36, 41.38), "khiva": (60.36, 41.38),
    "andijon": (72.34, 40.78), "andijan": (72.34, 40.78),
    "fargona": (71.78, 40.39), "fergana": (71.78, 40.39),
    "namangan": (71.67, 40.99),
    "qoqon": (70.94, 40.53), "kokand": (70.94, 40.53),
    "angren": (70.14, 41.02), "chirchiq": (69.58, 41.47),
    "bekobod": (69.27, 40.22), "yangiyer": (68.83, 40.27),
}


def _norm(s):
    """Shahar nomini taqqoslash uchun soddalashtiradi."""
    s = (s or "").lower()
    out = []
    for ch in s:
        if ch.isalnum() and ch.isascii():
            out.append(ch)
        elif ch in "ʻ'’`ʼ":
            continue
        # boshqa belgilar (bo'sh joy, defis) tashlanadi
    return "".join(out)


class RouteMap(QWidget):
    def __init__(self, radius=22):
        super().__init__()
        self._radius = radius
        self.stops = []
        self.current = 0
        self.theme_name = "light"
        self._geo = []          # har bekat uchun (lon, lat) yoki None
        self._phase = 0.0       # animatsiya fazasi [0,1)
        self.setMinimumSize(T.s(360), T.s(320))
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.setInterval(40)

    # ---- Ma'lumot ----
    def set_route(self, stops, current, theme_name):
        self.stops = stops or []
        self.current = max(0, min(current, len(self.stops) - 1)) if self.stops else 0
        self.theme_name = theme_name
        self._geo = [_CITY.get(_norm(s.get("name", ""))) for s in self.stops]
        if self.stops and self.isVisible():
            self.timer.start()
        self.update()

    def _tick(self):
        self._phase = (self._phase + 0.012) % 1.0
        self.update()

    def showEvent(self, e):
        super().showEvent(e)
        if self.stops:
            self.timer.start()

    def hideEvent(self, e):
        self.timer.stop()
        super().hideEvent(e)

    # ---- Geografiyani widget koordinatasiga loyihalash ----
    def _fill_unknown(self):
        pts = list(self._geo)
        kidx = [i for i, p in enumerate(pts) if p]
        if not kidx:
            return None
        for i in range(len(pts)):
            if pts[i] is None:
                prev = max([k for k in kidx if k < i], default=None)
                nxt = min([k for k in kidx if k > i], default=None)
                if prev is not None and nxt is not None:
                    t = (i - prev) / (nxt - prev)
                    a, b = self._geo[prev], self._geo[nxt]
                    pts[i] = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
                else:
                    pts[i] = self._geo[prev if prev is not None else nxt]
        return pts

    def _points(self, rect, pad):
        n = len(self.stops)
        geo = self._fill_unknown()
        if not geo:   # hech qaysi shahar tanilmadi — diagonal bo'ylab
            return [QPointF(rect.left() + pad + (rect.width() - 2 * pad) * (i / max(1, n - 1)),
                            rect.top() + pad + (rect.height() - 2 * pad) * (i / max(1, n - 1)))
                    for i in range(n)]
        lons = [g[0] for g in geo]
        lats = [g[1] for g in geo]
        lon0, lon1 = min(lons), max(lons)
        lat0, lat1 = min(lats), max(lats)
        dlon = max(1e-3, lon1 - lon0)
        dlat = max(1e-3, lat1 - lat0)
        aw = rect.width() - 2 * pad
        ah = rect.height() - 2 * pad
        s = min(aw / dlon, ah / dlat)        # nisbatni saqlovchi yagona miqyos
        used_w, used_h = dlon * s, dlat * s
        ox = rect.left() + pad + (aw - used_w) / 2
        oy = rect.top() + pad + (ah - used_h) / 2
        return [QPointF(ox + (lon - lon0) * s, oy + (lat1 - lat) * s)
                for lon, lat in geo]

    # ---- Chizish ----
    def paintEvent(self, e):
        c = T.THEMES[self.theme_name]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self._radius
        full = QRectF(0, 0, self.width(), self.height())

        # Fon (yumaloq) + clip
        path = QPainterPath()
        path.addRoundedRect(full, r, r)
        p.setClipPath(path)
        grad = QLinearGradient(0, 0, 0, self.height())
        if self.theme_name == "light":
            grad.setColorAt(0, QColor("#EEF3F9"))
            grad.setColorAt(1, QColor("#E1E8F1"))
            grid_col = QColor(150, 165, 190, 40)
            land = QColor(255, 255, 255, 70)
        else:
            grad.setColorAt(0, QColor("#243042"))
            grad.setColorAt(1, QColor("#1B2533"))
            grid_col = QColor(150, 165, 190, 30)
            land = QColor(255, 255, 255, 18)
        p.fillRect(full, QBrush(grad))

        # Faint graticule (to'r) — xarita hissi uchun
        step = T.s(64)
        p.setPen(QPen(grid_col, 1))
        x = step
        while x < self.width():
            p.drawLine(int(x), 0, int(x), self.height())
            x += step
        y = step
        while y < self.height():
            p.drawLine(0, int(y), self.width(), int(y))
            y += step

        if not self.stops:
            p.end()
            return

        pad = T.s(64)
        pts = self._points(full, pad)
        accent = QColor(c["accent"])
        gray = QColor("#AEB7C6")
        cur = self.current
        n = len(pts)

        # Marshrut atrofiga yumshoq "yo'lak" (land) — ozgina kenglik bilan
        if n >= 2:
            land_path = QPainterPath(pts[0])
            for pt in pts[1:]:
                land_path.lineTo(pt)
            p.setPen(QPen(land, T.s(26), Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.drawPath(land_path)

        # Segmentlar
        for i in range(n - 1):
            a, b = pts[i], pts[i + 1]
            if i < cur:                       # o'tilgan — to'liq ko'k
                p.setPen(QPen(accent, T.s(6), Qt.PenStyle.SolidLine,
                              Qt.PenCapStyle.RoundCap))
                p.drawLine(a, b)
            elif i == cur:                    # joriy segment — ko'k (animatsiya ustida)
                p.setPen(QPen(accent, T.s(6), Qt.PenStyle.SolidLine,
                              Qt.PenCapStyle.RoundCap))
                p.drawLine(a, b)
            else:                             # kelgusi — uzuq kulrang
                p.setPen(QPen(gray, T.s(4), Qt.PenStyle.DashLine,
                              Qt.PenCapStyle.RoundCap))
                p.drawLine(a, b)

        # Harakatlanuvchi poyezd nuqtasi (joriy segment bo'ylab) yoki oxirgi bekatda pulse
        if cur < n - 1:
            a, b = pts[cur], pts[cur + 1]
            t = self._phase
            mx = a.x() + (b.x() - a.x()) * t
            my = a.y() + (b.y() - a.y()) * t
            glow = QColor(accent); glow.setAlpha(70)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(glow)); p.drawEllipse(QPointF(mx, my), T.s(13), T.s(13))
            p.setBrush(QBrush(accent)); p.drawEllipse(QPointF(mx, my), T.s(6), T.s(6))

        # Bekat nuqtalari + nomli pill
        name_font = QFont(); name_font.setPixelSize(T.s(19)); name_font.setWeight(QFont.Weight.DemiBold)
        fm = QFontMetrics(name_font)
        for i, pt in enumerate(pts):
            # Pulslanuvchi halqa (joriy bekat)
            if i == cur:
                pulse = 0.5 + 0.5 * math.sin(self._phase * 2 * math.pi)
                pr = T.s(14) + T.s(12) * pulse
                ring = QColor(accent); ring.setAlpha(int(90 * (1 - pulse)))
                p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(ring))
                p.drawEllipse(pt, pr, pr)

            if i < cur:
                p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(accent))
                p.drawEllipse(pt, T.s(8), T.s(8))
            elif i == cur:
                p.setBrush(QBrush(QColor("#FFFFFF"))); p.setPen(QPen(accent, T.s(5)))
                p.drawEllipse(pt, T.s(9), T.s(9))
            else:
                p.setBrush(QBrush(QColor("#FFFFFF"))); p.setPen(QPen(gray, T.s(4)))
                p.drawEllipse(pt, T.s(7), T.s(7))

            # Nom pill — nuqtaning o'ng/chap tomonida (chetga yaqin bo'lsa aksincha)
            name = self.stops[i].get("name", "")
            if not name:
                continue
            tw = fm.horizontalAdvance(name)
            th = fm.height()
            padx, pady = T.s(12), T.s(6)
            bw, bh = tw + 2 * padx, th + 2 * pady
            gap = T.s(16)
            left_side = pt.x() > self.width() * 0.62
            bx = pt.x() - gap - bw if left_side else pt.x() + gap
            by = pt.y() - bh / 2
            bx = max(T.s(6), min(bx, self.width() - bw - T.s(6)))
            by = max(T.s(6), min(by, self.height() - bh - T.s(6)))
            brect = QRectF(bx, by, bw, bh)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(255, 255, 255, 235)))
            p.drawRoundedRect(brect, T.s(10), T.s(10))
            p.setFont(name_font)
            p.setPen(accent if i == cur else QColor(c["text"]))
            p.drawText(brect, Qt.AlignmentFlag.AlignCenter, name)

        p.end()
