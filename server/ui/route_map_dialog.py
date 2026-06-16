"""ui/route_map_dialog.py — Butun yo'nalishni xaritada ko'rsatuvchi oyna.

Bekatlar sahifasidagi "Xaritada ko'rish" tugmasi ochadi: barcha bekatlar
xaritada chiziq bilan bog'lanib, raqamli markerlar bilan ko'rinadi (oflayn
vektor xarita — index.html dagi setRoute()). QtWebEngine bo'lmasa ochilmaydi
(sahifa buni oldindan tekshiradi: ROUTE_MAP_AVAILABLE)."""
import json

from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import QDialog, QLabel, QVBoxLayout

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    ROUTE_MAP_AVAILABLE = True
except Exception:                                    # noqa: BLE001 — DLL ham
    ROUTE_MAP_AVAILABLE = False


class RouteMapDialog(QDialog):
    def __init__(self, parent, stops, title):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(940, 660)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        # Koordinatasi bor bekatlargina (lat/lng 0 yoki yo'q bo'lsa o'tkazamiz)
        self._stops = [
            {"name": s.get("name"),
             "lat": s.get("latitude"), "lng": s.get("longitude")}
            for s in stops
            if s.get("latitude") not in (None, 0)
            and s.get("longitude") not in (None, 0)]

        from ui import mapserver
        url = mapserver.map_url("index.html")
        if not ROUTE_MAP_AVAILABLE or not url:
            lay.addWidget(QLabel("Xarita mavjud emas (QtWebEngine yoki "
                                 "assets/map yo'q)."))
            return
        self._web = QWebEngineView()
        lay.addWidget(self._web)
        self._web.loadFinished.connect(self._on_loaded)
        self._web.setUrl(QUrl(url))

    def _on_loaded(self, ok):
        if ok and self._stops:
            data = json.dumps(self._stops)
            self._web.page().runJavaScript(f"window.setRoute && setRoute({data});")
