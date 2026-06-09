"""
map.py — Xarita (Map) bo'limi (TZ 8.3).

Tepada: poyezd nomi, yo'nalish, jo'nash/davomiylik teglari.
Chapda: bekatlar timeline'i (o'tilgan / joriy / kelgusi).
O'ngda: sxematik offline xarita (yo'nalish chizig'i + bekatlar + joriy nuqta).
Joriy bekat /api/status'dan olinadi (GPS bo'lmasa jadval asosida).
"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel,
                             QScrollArea)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPointF
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush

import theme as T


class _Loader(QThread):
    done = pyqtSignal(list, dict)
    fail = pyqtSignal()

    def __init__(self, api):
        super().__init__()
        self.api = api

    def run(self):
        try:
            self.done.emit(self.api.get_route(), self.api.get_status())
        except Exception:
            self.fail.emit()


class MapView(QWidget):
    """Bekatlarni koordinatalari bo'yicha sxematik chizadi (tiles o'rniga)."""

    def __init__(self):
        super().__init__()
        self.stops = []
        self.current = 0
        self.theme_name = "light"
        self.setMinimumSize(360, 300)

    def set_data(self, stops, current, theme_name):
        self.stops = stops
        self.current = current
        self.theme_name = theme_name
        self.update()

    def paintEvent(self, e):
        if not self.stops:
            return
        c = T.THEMES[self.theme_name]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(c["surface2"]))

        m = 50
        w, h = self.width() - 2 * m, self.height() - 2 * m
        lats = [s.get("latitude") or 0 for s in self.stops]
        lngs = [s.get("longitude") or 0 for s in self.stops]
        lat0, lat1 = min(lats), max(lats)
        lng0, lng1 = min(lngs), max(lngs)
        dlat = (lat1 - lat0) or 1
        dlng = (lng1 - lng0) or 1

        def pt(s):
            x = m + ((s.get("longitude") or 0) - lng0) / dlng * w
            y = m + (lat1 - (s.get("latitude") or 0)) / dlat * h  # shimol tepada
            return QPointF(x, y)

        pts = [pt(s) for s in self.stops]

        # Yo'nalish chizig'i
        p.setPen(QPen(QColor(c["accent"]), 4))
        for i in range(len(pts) - 1):
            p.drawLine(pts[i], pts[i + 1])

        # Bekat nuqtalari
        for i, q in enumerate(pts):
            if i < self.current:
                p.setBrush(QBrush(QColor(c["accent"])))
                p.setPen(Qt.PenStyle.NoPen)
                r = 7
            elif i == self.current:
                p.setBrush(QBrush(QColor(c["accent"])))
                p.setPen(QPen(QColor(c["accent_text"]), 3))
                r = 12
            else:
                p.setBrush(QBrush(QColor(c["surface"])))
                p.setPen(QPen(QColor(c["nav_inactive"]), 3))
                r = 7
            p.drawEllipse(q, r, r)
            # nom
            p.setPen(QColor(c["text"]))
            p.drawText(QPointF(q.x() + 12, q.y() + 4), self.stops[i].get("name", ""))
        p.end()


class MapScreen(QWidget):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self.theme_name = "light"
        self.stops = []
        self.current = 0
        self._loader = None
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(T.SPACE["page"], 0, T.SPACE["page"], T.SPACE["page"])
        root.setSpacing(T.SPACE["gap"])

        # Tepa panel: poyezd + yo'nalish + teglar
        self.head = QFrame()
        self.head.setObjectName("card")
        hl = QVBoxLayout(self.head)
        hl.setContentsMargins(20, 16, 20, 16)
        self.train = QLabel("—")
        self.train.setObjectName("mTrain")
        self.route = QLabel("—")
        self.route.setObjectName("mRoute")
        self.tags = QLabel("")
        self.tags.setObjectName("mTags")
        hl.addWidget(self.train)
        hl.addWidget(self.route)
        hl.addWidget(self.tags)
        root.addWidget(self.head)

        # Pastki qism: timeline (chap) + xarita (o'ng)
        body = QHBoxLayout()
        body.setSpacing(T.SPACE["page"])

        self.tl_scroll = QScrollArea()
        self.tl_scroll.setWidgetResizable(True)
        self.tl_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.tl_scroll.setFixedWidth(320)
        self.tl_host = QWidget()
        self.tl = QVBoxLayout(self.tl_host)
        self.tl.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.tl.setSpacing(4)
        self.tl_scroll.setWidget(self.tl_host)
        body.addWidget(self.tl_scroll)

        self.mapview = MapView()
        map_frame = QFrame()
        map_frame.setObjectName("card")
        mf = QVBoxLayout(map_frame)
        mf.setContentsMargins(8, 8, 8, 8)
        mf.addWidget(self.mapview)
        body.addWidget(map_frame, 1)

        root.addLayout(body, 1)

    # ---- Yuklash ----
    def on_show(self):
        self._loader = _Loader(self.api)
        self._loader.done.connect(self._on_data)
        self._loader.start()

    def _on_data(self, stops, status):
        self.stops = stops
        cur_name = status.get("current_stop")
        self.current = next((i for i, s in enumerate(stops)
                             if s.get("name") == cur_name), 0)
        self.train.setText(status.get("train_name") or "")
        self.route.setText(status.get("route") or "")
        self._render_timeline()
        self.mapview.set_data(stops, self.current, self.theme_name)

    def _render_timeline(self):
        while self.tl.count():
            w = self.tl.takeAt(0).widget()
            if w:
                w.deleteLater()
        c = T.THEMES[self.theme_name]
        for i, s in enumerate(self.stops):
            row = QFrame()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(8, 8, 8, 8)
            state = "passed" if i < self.current else ("current" if i == self.current else "next")
            dot = QLabel("●" if state != "next" else "○")
            dot.setStyleSheet(
                f"color: {c['accent'] if state != 'next' else c['nav_inactive']};"
                f" font-size: {22 if state == 'current' else 16}px;")
            name = QLabel(s.get("name", ""))
            weight = "700" if state == "current" else "500"
            color = c["text"] if state != "next" else c["text_secondary"]
            name.setStyleSheet(f"color:{color}; font-size:{T.FONT['body']}px; font-weight:{weight};")
            time = QLabel(s.get("arrival_time", ""))
            time.setStyleSheet(f"color:{c['text_secondary']}; font-size:{T.FONT['small']}px;")
            rl.addWidget(dot)
            rl.addWidget(name, 1)
            rl.addWidget(time)
            self.tl.addWidget(row)

    # ---- Mavzu ----
    def apply_theme(self, name):
        self.theme_name = name
        c = T.THEMES[name]
        self.setStyleSheet(
            f"#card {{ background: {c['surface']}; border-radius: {T.RADIUS['card']}px; }}"
            f"#mTrain {{ color: {c['text']}; font-size: {T.FONT['title']}px; font-weight: 700; }}"
            f"#mRoute {{ color: {c['accent']}; font-size: {T.FONT['h2']}px; font-weight: 600; }}"
            f"#mTags {{ color: {c['text_secondary']}; font-size: {T.FONT['body']}px; }}")
        if self.stops:
            self._render_timeline()
            self.mapview.set_data(self.stops, self.current, name)
