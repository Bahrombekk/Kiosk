"""ui/stop_dialog.py — Bekat qo'shish/tahrirlash dialogi.

Yuklovchi koordinatani (lat/lng) qo'lda yozmasin deb:
  - Bekat nomini ichki O'zbekiston temir yo'l bekatlari ro'yxatidan TANLAYDI
    (qidiruvli combo) -> lat/lng AVTOMATIK to'ladi;
  - masofa (km) oldingi bekatdan TAXMINIY hisoblanadi (haversine; admin
    aniqlashtirishi mumkin);
  - tartib raqami avtomatik (oxirgi bekatdan keyingisi);
  - mavjud bo'lsa OFLAYN VEKTOR XARITA ko'rsatiladi: xaritaga bosib yoki
    bekatni tanlab nuqtani aniqlashtirsa bo'ladi.

Xarita QtWebEngine + MapLibre + PMTiles bilan ishlaydi. QtWebEngine yoki xarita
assetlari bo'lmasa dialog xaritasiz, faqat forma + bekat bazasi bilan
ishlayveradi (hech qachon buzilmaydi)."""
import json
import math
import os

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtWidgets import (
    QComboBox, QCompleter, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QSpinBox,
    QVBoxLayout, QWidget
)

import db
from icons import ICON_DIR

# QtWebEngine ixtiyoriy — bo'lmasa xaritasiz ishlaymiz
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    _HAS_WEBENGINE = True
except Exception:                                    # noqa: BLE001 — DLL ham
    _HAS_WEBENGINE = False

ASSETS_DIR = os.path.dirname(ICON_DIR)
STATIONS_PATH = os.path.join(ASSETS_DIR, "uz_stations.json")


def load_stations():
    """assets/uz_stations.json -> [{name, lat, lng}, ...] (xato bo'lsa bo'sh)."""
    try:
        with open(STATIONS_PATH, encoding="utf-8") as f:
            return json.load(f).get("stations", [])
    except (OSError, ValueError):
        return []


def _haversine_km(a_lat, a_lng, b_lat, b_lng):
    """Ikki nuqta orasidagi to'g'ri chiziq masofasi (km). Temir yo'l undan
    uzunroq — shuning uchun bu TAXMINIY boshlang'ich qiymat."""
    r = 6371.0
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dphi = math.radians(b_lat - a_lat)
    dlmb = math.radians(b_lng - a_lng)
    x = (math.sin(dphi / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(x))


class StopDialog(QDialog):
    """Bekat formasi + (mavjud bo'lsa) interaktiv xarita."""

    def __init__(self, parent, item=None):
        super().__init__(parent)
        self._item = item or {}
        # Yo'nalish: tahrirlashda yozuvning o'zinikidan, yangida sahifada
        # tanlangan yo'nalishdan (AdminWindow._route_dir).
        if item and item.get("direction") is not None:
            self._direction = int(item.get("direction") or 0)
        else:
            self._direction = int(getattr(parent, "_route_dir", 0) or 0)
        self._stations = load_stations()
        self._by_name = {s["name"]: s for s in self._stations}
        try:
            # Masofa shu YO'NALISHdagi oldingi bekatdan hisoblanadi
            self._stops = db.get_route(direction=self._direction)
        except Exception:                            # noqa: BLE001
            self._stops = []
        self._web = None
        self._map_ready = False

        self.setWindowTitle("Tahrirlash: bekat" if item else "Yangi: bekat")
        self.setMinimumWidth(980 if _HAS_WEBENGINE else 460)

        root = QHBoxLayout(self)
        root.setSpacing(16)
        root.addWidget(self._build_form(), 0)
        mp = self._build_map()
        if mp is not None:
            root.addWidget(mp, 1)

        self._fill_from_item()

    # ------------------------------------------------------------------ forma
    def _build_form(self):
        box = QWidget()
        box.setMinimumWidth(420)
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(10)

        # Bekat nomi — ro'yxatdan tanlanadi (qidiruvli), qo'lda ham yoziladi
        self.name = QComboBox()
        self.name.setEditable(True)
        self.name.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.name.addItem("")
        self.name.addItems([s["name"] for s in self._stations])
        comp = QCompleter([s["name"] for s in self._stations], self)
        comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        comp.setFilterMode(Qt.MatchFlag.MatchContains)
        self.name.setCompleter(comp)
        self.name.activated.connect(lambda: self._on_station_chosen())
        self.name.lineEdit().editingFinished.connect(self._on_station_chosen)

        self.arrival = QLineEdit()
        self.arrival.setPlaceholderText("HH:MM (masalan 04:20)")
        self.departure = QLineEdit()
        self.departure.setPlaceholderText("HH:MM (masalan 04:34)")

        self.lat = QDoubleSpinBox()
        self.lat.setDecimals(6)
        self.lat.setRange(-90.0, 90.0)
        self.lng = QDoubleSpinBox()
        self.lng.setDecimals(6)
        self.lng.setRange(-180.0, 180.0)
        self.lat.valueChanged.connect(self._on_coords_edited)
        self.lng.valueChanged.connect(self._on_coords_edited)

        self.distance_km = QSpinBox()
        self.distance_km.setRange(0, 100000)
        self.distance_km.setSuffix(" km")

        self.auto_dist = QComboBox()
        self.auto_dist.addItem("Avtomatik (oldingi bekatdan, taxminiy)", True)
        self.auto_dist.addItem("Qo'lda kiritaman", False)
        self.auto_dist.currentIndexChanged.connect(
            lambda: self._recompute_distance())

        self.sort_order = QSpinBox()
        self.sort_order.setRange(0, 100000)
        self.sort_order.valueChanged.connect(lambda: self._recompute_distance())

        form.addRow("Bekat nomi:", self.name)
        form.addRow("Kelish vaqti:", self.arrival)
        form.addRow("Jo'nash vaqti:", self.departure)
        form.addRow("Kenglik (lat):", self.lat)
        form.addRow("Uzunlik (lng):", self.lng)
        form.addRow("Masofa hisobi:", self.auto_dist)
        form.addRow("Masofa (km):", self.distance_km)
        form.addRow("Tartib raqami:", self.sort_order)
        lay.addLayout(form)

        hint = QLabel(
            "Bekat nomini ro'yxatdan tanlang — koordinata avtomatik to'ladi. "
            "Masofa oldingi bekatdan taxminan hisoblanadi (xaritadan yoki "
            "qo'lda aniqlashtiring)."
            + ("" if _HAS_WEBENGINE
               else "\n\nXarita ko'rinishi uchun QtWebEngine kerak "
                    "(pip install PyQt6-WebEngine)."))
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        lay.addStretch(1)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)
        return box

    # ------------------------------------------------------------------ xarita
    def _build_map(self):
        if not _HAS_WEBENGINE:
            return None
        from ui import mapserver
        url = mapserver.map_url("index.html")
        if not url:
            return None     # assets/map yo'q — xaritasiz davom etamiz
        self._web = QWebEngineView()
        self._web.setMinimumWidth(460)
        # Xaritadan tanlangan nuqta document.title orqali keladi: "pick:lat,lng"
        self._web.titleChanged.connect(self._on_map_title)
        self._web.loadFinished.connect(self._on_map_loaded)
        self._web.setUrl(QUrl(url))
        return self._web

    def _on_map_loaded(self, ok):
        self._map_ready = bool(ok)
        if ok:
            self._push_stations()
            self._push_marker()

    def _push_stations(self):
        if not (self._web and self._map_ready):
            return
        data = json.dumps([{"name": s["name"], "lat": s["lat"], "lng": s["lng"]}
                           for s in self._stations])
        self._web.page().runJavaScript(f"window.setStations && setStations({data});")

    def _push_marker(self):
        if not (self._web and self._map_ready):
            return
        lat, lng = self.lat.value(), self.lng.value()
        if lat == 0 and lng == 0:
            return
        self._web.page().runJavaScript(
            f"window.setMarker && setMarker({lat},{lng},true);")

    def _on_map_title(self, title):
        if not title.startswith("pick:"):
            return
        try:
            lat_s, lng_s = title[5:].split(",")
            lat, lng = float(lat_s), float(lng_s)
        except (ValueError, IndexError):
            return
        self._set_coords(lat, lng, fly=False)

    # ------------------------------------------------------------ mantiq/aloqa
    def _on_station_chosen(self):
        st = self._by_name.get(self.name.currentText().strip())
        if st:
            self._set_coords(st["lat"], st["lng"], fly=True)

    def _on_coords_edited(self):
        # Foydalanuvchi spinbox'ni o'zgartirdi — masofa + xarita markerini yangilaymiz
        self._recompute_distance()
        self._push_marker()

    def _set_coords(self, lat, lng, fly):
        self.lat.blockSignals(True)
        self.lng.blockSignals(True)
        self.lat.setValue(lat)
        self.lng.setValue(lng)
        self.lat.blockSignals(False)
        self.lng.blockSignals(False)
        self._recompute_distance()
        if self._web and self._map_ready:
            js = f"window.setMarker && setMarker({lat},{lng},{str(fly).lower()});"
            self._web.page().runJavaScript(js)

    def _previous_stop(self):
        """Joriy bekatdan OLDINGI bekat (tartib bo'yicha) — masofa shundan."""
        others = [s for s in self._stops
                  if s.get("id") != self._item.get("id")]
        before = [s for s in others
                  if (s.get("sort_order") or 0) < self.sort_order.value()]
        if not before:
            return None
        return max(before, key=lambda s: (s.get("sort_order") or 0,
                                          s.get("id") or 0))

    def _recompute_distance(self):
        if not self.auto_dist.currentData():
            return     # qo'lda rejim — tegmaymiz
        lat, lng = self.lat.value(), self.lng.value()
        if lat == 0 and lng == 0:
            return
        prev = self._previous_stop()
        if prev is None:
            self.distance_km.setValue(0)    # birinchi bekat
            return
        if prev.get("latitude") is None or prev.get("longitude") is None:
            return
        d = _haversine_km(prev["latitude"], prev["longitude"], lat, lng)
        self.distance_km.setValue(int(prev.get("distance_km") or 0) + round(d))

    # ------------------------------------------------------- to'ldirish/qiymat
    def _fill_from_item(self):
        it = self._item
        if it:
            self.name.setCurrentText(it.get("name") or "")
            self.arrival.setText(it.get("arrival_time") or "")
            self.departure.setText(it.get("departure_time") or "")
            self.lat.blockSignals(True)
            self.lng.blockSignals(True)
            self.lat.setValue(float(it.get("latitude") or 0))
            self.lng.setValue(float(it.get("longitude") or 0))
            self.lat.blockSignals(False)
            self.lng.blockSignals(False)
            self.distance_km.setValue(int(it.get("distance_km") or 0))
            self.sort_order.setValue(int(it.get("sort_order") or 0))
            # Mavjud yozuvda masofa bor — qo'lda rejimni standart qilamiz
            self.auto_dist.setCurrentIndex(1 if it.get("distance_km") else 0)
        else:
            # Yangi bekat: tartib = oxirgisidan keyingisi, masofa avtomatik
            nxt = max((int(s.get("sort_order") or 0) for s in self._stops),
                      default=-1) + 1
            self.sort_order.setValue(nxt)
            self.auto_dist.setCurrentIndex(0)

    def accept(self):
        if not self.name.currentText().strip():
            QMessageBox.warning(self, "Xato", "Bekat nomi bo'sh bo'lmasin.")
            return
        super().accept()

    def values(self):
        """db.add_route_stop / update_route_stop uchun maydonlar."""
        return {
            "name": self.name.currentText().strip() or None,
            "arrival_time": self.arrival.text().strip() or None,
            "departure_time": self.departure.text().strip() or None,
            "latitude": self.lat.value(),
            "longitude": self.lng.value(),
            "distance_km": self.distance_km.value(),
            "sort_order": self.sort_order.value(),
            "direction": self._direction,
        }
