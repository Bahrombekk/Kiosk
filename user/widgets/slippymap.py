"""
slippymap.py — Lokal OSM plitkalaridan real (offline) xarita.

`map_tiles/` keshidagi plitkalarni o'qib chizadi; marshrut chizig'ini va
bekatlarni ustiga joylaydi. Sichqoncha bilan suriladi (drag) va g'ildirak
bilan zumlanadi (faqat yuklab olingan zoom'lar oralig'ida). Internet kerak emas.

Plitkalarni oldindan yuklash: `py maptiles.py` (internet bor paytda bir marta).
"""
import os
import math

from PyQt6.QtWidgets import QWidget, QPushButton
from PyQt6.QtCore import Qt, QPointF, QRectF, QRect
from PyQt6.QtGui import (QPixmap, QPainter, QPainterPath, QColor, QPen, QBrush,
                         QFont)

import theme as T

TILES_DIR = os.path.join(os.path.dirname(__file__), "..", "map_tiles")
TILE = 256
MIN_Z, MAX_Z = 7, 10


def _deg2px(lat, lon, z):
    """Geo -> global piksel (zoom z)."""
    n = 2 ** z
    x = (lon + 180.0) / 360.0 * n * TILE
    lat_r = math.radians(lat)
    y = (1.0 - math.asinh(math.tan(lat_r)) / math.pi) / 2.0 * n * TILE
    return x, y


def _px2deg(px, py, z):
    """Global piksel -> geo (zoom z)."""
    n = 2 ** z
    lon = px / (n * TILE) * 360.0 - 180.0
    ty = py / (n * TILE)
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * ty))))
    return lat, lon


class SlippyMap(QWidget):
    def __init__(self, radius=28):
        super().__init__()
        self._radius = radius
        self.theme_name = "light"
        self.stops = []
        self.current = 0
        self.zoom = 8
        self.clat, self.clon = 40.5, 68.1     # marshrut markazi (taxminiy)
        self._pixcache = {}                    # (z,x,y) -> QPixmap
        self._drag = None
        self._fitted = False                   # marshrut bir marta sig'dirilganmi
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

        # Zum tugmalari (+/−) — interaktivlik aniq ko'rinsin
        self.btn_in = self._zbtn("+")
        self.btn_out = self._zbtn("−")
        self.btn_in.clicked.connect(lambda: self._zoom_by(+1))
        self.btn_out.clicked.connect(lambda: self._zoom_by(-1))

    def _zbtn(self, ch):
        b = QPushButton(ch, self)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setFixedSize(54, 54)
        b.setStyleSheet(
            "QPushButton { background: rgba(255,255,255,0.95); color: #1c2230;"
            " border: 1px solid #d6dde7; border-radius: 12px;"
            " font-size: 32px; font-weight: 600; }"
            "QPushButton:hover { background: #ffffff; }"
            "QPushButton:pressed { background: #eef2f7; }")
        return b

    def _zoom_by(self, step):
        new_z = max(MIN_Z, min(MAX_Z, self.zoom + step))
        if new_z != self.zoom:
            self.zoom = new_z
            self.update()

    # ---- Tashqi API ----
    def set_route(self, stops, current, theme_name):
        self.stops = stops or []
        self.current = current
        self.theme_name = theme_name
        self._fitted = False
        if self.width() > 10 and self.height() > 10:
            self._fit_route()
            self._fitted = True
        self.update()

    def _fit_route(self):
        """Marshrutni ko'rinishga sig'diradi: markaz + mos zoom."""
        pts = [(s.get("latitude"), s.get("longitude")) for s in self.stops
               if s.get("latitude") is not None and s.get("longitude") is not None]
        if not pts:
            return
        lats = [p[0] for p in pts]
        lons = [p[1] for p in pts]
        self.clat = (min(lats) + max(lats)) / 2
        self.clon = (min(lons) + max(lons)) / 2
        w = max(self.width(), 200)
        h = max(self.height(), 200)
        best = MIN_Z
        for z in range(MIN_Z, MAX_Z + 1):
            x1, y1 = _deg2px(max(lats), min(lons), z)
            x2, y2 = _deg2px(min(lats), max(lons), z)
            if (x2 - x1) <= w * 0.82 and (y2 - y1) <= h * 0.82:
                best = z
            else:
                break
        self.zoom = best

    # ---- Plitka o'qish ----
    def _tile(self, z, x, y):
        key = (z, x, y)
        if key in self._pixcache:
            return self._pixcache[key]
        path = os.path.join(TILES_DIR, str(z), str(x), f"{y}.png")
        pm = QPixmap(path) if os.path.isfile(path) else QPixmap()
        self._pixcache[key] = pm
        return pm

    # ---- Chizish ----
    def paintEvent(self, e):
        c = T.THEMES[self.theme_name]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), self._radius, self._radius)
        p.setClipPath(path)
        p.fillRect(self.rect(), QColor("#DDE6EC"))   # plitkasiz joy uchun suv-rang fon

        W, H = self.width(), self.height()
        cx, cy = _deg2px(self.clat, self.clon, self.zoom)
        left = cx - W / 2.0
        top = cy - H / 2.0
        n = 2 ** self.zoom

        tx0 = int(math.floor(left / TILE))
        ty0 = int(math.floor(top / TILE))
        tx1 = int(math.floor((left + W) / TILE))
        ty1 = int(math.floor((top + H) / TILE))

        for tx in range(tx0, tx1 + 1):
            for ty in range(ty0, ty1 + 1):
                if tx < 0 or ty < 0 or tx >= n or ty >= n:
                    continue
                pm = self._tile(self.zoom, tx, ty)
                dx = int(round(tx * TILE - left))
                dy = int(round(ty * TILE - top))
                if not pm.isNull():
                    p.drawPixmap(dx, dy, pm)

        # --- Marshrut chizig'i va bekatlar ---
        self._draw_route(p, left, top)
        p.end()

    def _draw_route(self, p, left, top):
        pts = []
        for s in self.stops:
            lat, lon = s.get("latitude"), s.get("longitude")
            if lat is None or lon is None:
                pts.append(None)
                continue
            gx, gy = _deg2px(lat, lon, self.zoom)
            pts.append(QPointF(gx - left, gy - top))

        c = T.THEMES[self.theme_name]
        accent = QColor(c["accent"])
        # chiziq (oq hoshiya + ko'k ustki)
        line = [q for q in pts if q is not None]
        if len(line) > 1:
            p.setPen(QPen(QColor("#FFFFFF"), 9, Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.drawPolyline(*line)
            p.setPen(QPen(accent, 5, Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.drawPolyline(*line)

        # bekat nuqtalari + nomlari
        name_font = QFont(); name_font.setPixelSize(26); name_font.setWeight(QFont.Weight.DemiBold)
        for i, q in enumerate(pts):
            if q is None:
                continue
            if i < self.current:
                p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(accent)); r = 9
            elif i == self.current:
                p.setBrush(QBrush(QColor("#FFFFFF"))); p.setPen(QPen(accent, 5)); r = 11
            else:
                p.setBrush(QBrush(QColor("#FFFFFF"))); p.setPen(QPen(QColor("#9AA3B2"), 4)); r = 8
            p.drawEllipse(q, r, r)
            # nom yorlig'i (oq fonli)
            name = self.stops[i].get("name", "")
            p.setFont(name_font)
            fm = p.fontMetrics()
            tw = fm.horizontalAdvance(name)
            bx, by = q.x() + 16, q.y() - 18
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, 220))
            p.drawRoundedRect(QRectF(bx - 6, by - 4, tw + 14, 34), 8, 8)
            p.setPen(QColor(c["text"]))
            p.drawText(QRectF(bx, by, tw + 6, 30),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, name)

    # ---- Interaktiv: surish va zum ----
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag = e.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            d = e.position() - self._drag
            self._drag = e.position()
            cx, cy = _deg2px(self.clat, self.clon, self.zoom)
            self.clat, self.clon = _px2deg(cx - d.x(), cy - d.y(), self.zoom)
            self.update()

    def mouseReleaseEvent(self, e):
        self._drag = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def wheelEvent(self, e):
        self._zoom_by(1 if e.angleDelta().y() > 0 else -1)

    def resizeEvent(self, e):
        m = 16
        self.btn_in.move(self.width() - 54 - m, m)
        self.btn_out.move(self.width() - 54 - m, m + 54 + 10)
        if not self._fitted and self.stops:   # o'lcham kelgach marshrutni sig'diramiz
            self._fit_route()
            self._fitted = True
        super().resizeEvent(e)
