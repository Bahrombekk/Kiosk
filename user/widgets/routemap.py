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
                         QPainterPath, QLinearGradient, QRadialGradient)

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
    # 076Ф Toshkent—Xiva yo'nalishidagi oraliq bekatlar
    "juma": (66.66, 39.72), "kattaqorgon": (66.26, 39.90),
    "zirabuloq": (66.00, 39.94), "ziyovuddin": (65.68, 39.95),
    "qiziltepa": (64.85, 40.03), "kogon": (64.55, 39.72),
    "jayhun": (63.60, 39.20), "hazorasp": (61.07, 41.32),
    "pitnak": (61.37, 41.21), "beruniy": (60.75, 41.69),
    "tortkol": (61.00, 41.55), "qongirot": (58.85, 43.08),
    "guzor": (66.25, 38.62), "shahrisabz": (66.84, 39.05),
}


def _lookup(name):
    """Bekat nomidan (lon, lat). Aniq mos kelmasa, prefiks bo'yicha urinadi:
    'Toshkent-Janubiy'->toshkent, 'Buxoro-1'->buxoro, 'Samarqand-Passajir'->samarqand."""
    key = _norm(name)
    if not key:
        return None
    if key in _CITY:
        return _CITY[key]
    for ck, val in _CITY.items():
        if len(ck) >= 4 and key.startswith(ck):
            return val
    return None


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
        self._geo = [_lookup(s.get("name", "")) for s in self.stops]
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
        sx, sy = aw / dlon, ah / dlat
        s = min(sx, sy)                      # gorizontal — nisbatni saqlaydi
        # Marshrut keng+past bo'lsa vertikal juda yupqa chiqadi — biroz cho'zib
        # panelni to'ldiramiz (cheklangan: xunuk buzilmasin).
        syy = min(sy, s * 2.4)
        used_w, used_h = dlon * s, dlat * syy
        ox = rect.left() + pad + (aw - used_w) / 2
        oy = rect.top() + pad + (ah - used_h) / 2
        return [QPointF(ox + (lon - lon0) * s, oy + (lat1 - lat) * syy)
                for lon, lat in geo]

    @staticmethod
    def _smooth_path(pts):
        """Nuqtalar orqali silliq egri (Catmull-Rom -> kubik Bezier)."""
        path = QPainterPath(pts[0])
        n = len(pts)
        for i in range(n - 1):
            p0 = pts[i - 1] if i > 0 else pts[0]
            p1, p2 = pts[i], pts[i + 1]
            p3 = pts[i + 2] if i + 2 < n else pts[n - 1]
            c1 = QPointF(p1.x() + (p2.x() - p0.x()) / 6.0,
                         p1.y() + (p2.y() - p0.y()) / 6.0)
            c2 = QPointF(p2.x() - (p3.x() - p1.x()) / 6.0,
                         p2.y() - (p3.y() - p1.y()) / 6.0)
            path.cubicTo(c1, c2, p2)
        return path

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
            grad.setColorAt(0, QColor("#EAF1FA"))
            grad.setColorAt(1, QColor("#DCE6F3"))
            land = QColor(255, 255, 255, 130)
            halo = QColor(255, 255, 255, 150)
        else:
            grad.setColorAt(0, QColor("#243042"))
            grad.setColorAt(1, QColor("#1B2533"))
            land = QColor(255, 255, 255, 24)
            halo = QColor(255, 255, 255, 26)
        p.fillRect(full, QBrush(grad))

        # Markazda yumshoq yorug'lik (to'rsiz — toza "qog'oz" xarita hissi)
        rg = QRadialGradient(self.width() * 0.5, self.height() * 0.42,
                             max(self.width(), self.height()) * 0.72)
        rg.setColorAt(0.0, halo)
        rg.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.fillRect(full, QBrush(rg))

        if not self.stops:
            p.end()
            return

        pad = T.s(64)
        pts = self._points(full, pad)
        accent = QColor(c["accent"])
        gray = QColor("#AEB7C6")
        cur = self.current
        n = len(pts)

        # Silliq egri marshrut: yumshoq yo'lak -> butun yo'l (kulrang) ->
        # o'tilgan qism (accent) joriy bekatgacha.
        if n >= 2:
            full_path = self._smooth_path(pts)
            p.setPen(QPen(land, T.s(22), Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.drawPath(full_path)
            p.setPen(QPen(gray, T.s(5), Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.drawPath(full_path)
            if cur >= 1:
                passed = self._smooth_path(pts[:cur + 1])
                p.setPen(QPen(accent, T.s(6), Qt.PenStyle.SolidLine,
                              Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                p.drawPath(passed)

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

        # --- Bekat nuqtalari (avval hammasi chiziladi) ---
        for i, pt in enumerate(pts):
            if i == cur:   # pulslanuvchi halqa
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

        # --- Nom pill'lari: TO'QNASHUVSIZ joylashtirish ---
        # Marshrut keng+past bo'lsa 15 ta nom bir-biriga yopishadi. Shuning uchun
        # muhim bekatlar (joriy, birinchi, oxirgi) DOIM, qolganlari joy bo'lsa
        # chiziladi; har biri uchun o'ng/chap/tepa/past variantlardan bo'shi tanlanadi.
        name_font = QFont(); name_font.setPixelSize(T.s(18)); name_font.setWeight(QFont.Weight.DemiBold)
        fm = QFontMetrics(name_font)
        p.setFont(name_font)
        placed = []          # joylashtirilgan pill to'rtburchaklari (to'qnashuv uchun)
        W, H = self.width(), self.height()
        m = T.s(6)
        gap = T.s(13)

        def _try_rect(pt, bw, bh):
            for bx, by in ((pt.x() + gap, pt.y() - bh / 2),        # o'ng
                           (pt.x() - gap - bw, pt.y() - bh / 2),   # chap
                           (pt.x() - bw / 2, pt.y() - gap - bh),   # tepa
                           (pt.x() - bw / 2, pt.y() + gap)):       # past
                bx = max(m, min(bx, W - bw - m))
                by = max(m, min(by, H - bh - m))
                rect = QRectF(bx, by, bw, bh)
                if not any(rect.intersects(r) for r in placed):
                    return rect
            return None

        # Tartib: joriy -> birinchi -> oxirgi -> qolganlari (muhimi oldin joy oladi)
        order = []
        for idx in (cur, 0, n - 1):
            if 0 <= idx < n and idx not in order:
                order.append(idx)
        order += [i for i in range(n) if i not in order]
        key = {cur, 0, n - 1}

        for i in order:
            name = self.stops[i].get("name", "")
            if not name:
                continue
            bw = fm.horizontalAdvance(name) + 2 * T.s(12)
            bh = fm.height() + 2 * T.s(6)
            rect = _try_rect(pts[i], bw, bh)
            if rect is None:
                if i not in key:
                    continue            # oddiy bekat — joy yo'q, o'tkazamiz
                # muhim bekat — majburan o'ngga (kichik siljish bilan)
                bx = max(m, min(pts[i].x() + gap, W - bw - m))
                by = max(m, min(pts[i].y() - bh / 2, H - bh - m))
                rect = QRectF(bx, by, bw, bh)
            placed.append(rect)
            p.setPen(Qt.PenStyle.NoPen)
            # yumshoq soya (biroz pastga siljigan to'q yarim shaffof)
            p.setBrush(QColor(40, 55, 90, 42))
            p.drawRoundedRect(rect.translated(0, T.s(2)), T.s(11), T.s(11))
            # pill foni
            p.setBrush(QBrush(QColor(255, 255, 255, 246)))
            p.drawRoundedRect(rect, T.s(11), T.s(11))
            p.setPen(accent if i == cur else QColor(c["text"]))
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, name)

        p.end()
