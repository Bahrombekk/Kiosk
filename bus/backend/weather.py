"""
weather.py — Marshrut hududlari uchun internet ob-havosi (Open-Meteo).

Nega kerak: poyezddagi harorat qo'lda kiritilgan statik son edi. Endi server
internetga ulanganda marshrutdagi BARCHA bekatlar uchun 7 KUNLIK SOATLIK
haroratni yuklab `weather_cache.json` ga saqlaydi. status_payload joriy bekat
koordinatasi + joriy vaqt bo'yicha keshdan haroratni oladi.

Oflayn-bardosh: 7 kunlik ma'lumot bir martalik yuklashda bir hafta yetadi.
Internet yo'q bo'lsa eski kesh ishlatiladi; > 8 kun eskirgan bo'lsa None
qaytaramiz (status_payload qo'lda kiritilgan haroratga qaytadi).

Open-Meteo: bepul, API kalit SHART EMAS. Bir so'rovda ko'p nuqta (vergul bilan)
so'raladi — barcha bekatlar uchun bitta HTTP chaqiruv.
"""
import json
import logging
import os
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime

import config
import db

log = logging.getLogger("kiosk.weather")

CACHE_PATH = os.path.join(config.BASE_DIR, "weather_cache.json")
API_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT_S = 15
FORECAST_DAYS = 7
REFRESH_INTERVAL_S = 3 * 3600        # muvaffaqiyatdan keyin: har 3 soatda yangilab turamiz
RETRY_INTERVAL_S = 20 * 60           # internet yo'q bo'lsa: tezroq qayta urinamiz
MAX_STALE_S = 8 * 86400              # > 8 kun eskirgan kesh ishlatilmaydi
TZ = "Asia/Tashkent"                 # barcha bekatlar O'zbekistonda

_cache = None
_cache_mtime = None


def _key(lat, lng):
    """Koordinata kesh kaliti (yaxlitlangan — kichik farqlar bitta hududga)."""
    return f"{round(float(lat), 3)},{round(float(lng), 3)}"


def _route_points():
    """Marshrutdagi takrorsiz koordinatalar (har ikki yo'nalishdan)."""
    pts = {}
    for direction in (0, 1):
        for st in db.get_route(direction):
            lat, lng = st.get("latitude"), st.get("longitude")
            if lat is None or lng is None:
                continue
            try:
                pts[_key(lat, lng)] = (float(lat), float(lng))
            except (TypeError, ValueError):
                continue
    return pts


def refresh():
    """Internet bo'lsa ob-havoni yangilaydi. True = yangilandi, False = xato/o'tkazildi.
    Xatoda eski kesh teginilmaydi (oflaynda davom etadi)."""
    pts = _route_points()
    if not pts:
        return False
    keys = list(pts)
    query = urllib.parse.urlencode({
        "latitude": ",".join(str(pts[k][0]) for k in keys),
        "longitude": ",".join(str(pts[k][1]) for k in keys),
        "hourly": "temperature_2m",
        "forecast_days": FORECAST_DAYS,
        "timezone": TZ,
    })
    try:
        with urllib.request.urlopen(f"{API_URL}?{query}", timeout=TIMEOUT_S) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as e:                              # noqa: BLE001
        log.info("Ob-havo yangilanmadi (internet yo'q?): %s", e)
        return False
    # Bitta nuqta — dict, ko'p nuqta — list qaytadi: normallashtiramiz
    items = data if isinstance(data, list) else [data]
    points = {}
    for key, item in zip(keys, items):
        if not isinstance(item, dict):
            continue
        h = item.get("hourly") or {}
        times = h.get("time") or []
        temps = h.get("temperature_2m") or []
        if times and temps:
            points[key] = {"time": times, "temp": temps}
    if not points:
        log.warning("Ob-havo javobi bo'sh/kutilmagan formatda")
        return False
    out = {"fetched_at": time.time(), "points": points}
    tmp = CACHE_PATH + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(out, f)
        os.replace(tmp, CACHE_PATH)
    except OSError as e:
        log.warning("Ob-havo keshini yozib bo'lmadi: %s", e)
        return False
    log.info("Ob-havo yangilandi: %d hudud, %d kun", len(points), FORECAST_DAYS)
    return True


def _load():
    """Keshni o'qiydi (mtime o'zgarsa qayta o'qiydi). dict yoki None."""
    global _cache, _cache_mtime
    try:
        mtime = os.path.getmtime(CACHE_PATH)
    except OSError:
        return None
    if mtime != _cache_mtime:
        try:
            with open(CACHE_PATH, encoding="utf-8") as f:
                _cache = json.load(f)
        except (OSError, ValueError):
            _cache = None
        _cache_mtime = mtime
    return _cache


def _closest_index(times, when):
    """`when` (datetime) ga eng yaqin soat indeksi (yoki None)."""
    best_i, best_d = None, None
    for i, t in enumerate(times):
        try:
            dt = datetime.strptime(t, "%Y-%m-%dT%H:%M")
        except (ValueError, TypeError):
            continue
        d = abs((dt - when).total_seconds())
        if best_d is None or d < best_d:
            best_i, best_d = i, d
    return best_i


def temp_for(lat, lng, when=None):
    """Berilgan hudud + vaqt uchun harorat (°C, int) yoki None.

    None qaytsa — kesh yo'q/eskirgan yoki bu hudud kuzatilmagan: chaqiruvchi
    qo'lda kiritilgan haroratga qaytishi kerak."""
    if lat is None or lng is None:
        return None
    cache = _load()
    if not cache:
        return None
    if time.time() - cache.get("fetched_at", 0) > MAX_STALE_S:
        return None     # juda eskirgan — ishonchsiz
    pt = (cache.get("points") or {}).get(_key(lat, lng))
    if not pt:
        return None
    when = when or datetime.now()
    times = pt.get("time") or []
    temps = pt.get("temp") or []
    target = when.strftime("%Y-%m-%dT%H:00")
    idx = times.index(target) if target in times else _closest_index(times, when)
    if idx is None or idx >= len(temps) or temps[idx] is None:
        return None
    return round(temps[idx])


def start_refresher():
    """Fon oqimi: startda urinadi, so'ng moslashuvchan oraliqda yangilab turadi.

    Server internet QACHON paydo bo'lishini bilishi shart emas — muntazam
    urinaveradi:
      - muvaffaqiyatli (internet bor) -> 3 soat kutadi (prognoz yetarlicha yangi);
      - muvaffaqiyatsiz (internet yo'q) -> 20 daqiqada qayta urinadi, shunda
        internet QISQA vaqtga ochilsa ham o'sha oynani ushlab qoladi.
    Daemon — jarayon bilan birga tugaydi (alohida to'xtatish shart emas)."""
    def _loop():
        while True:
            ok = False
            try:
                ok = refresh()
            except Exception:                          # noqa: BLE001
                log.exception("Ob-havo yangilash sikilida xato")
            time.sleep(REFRESH_INTERVAL_S if ok else RETRY_INTERVAL_S)

    threading.Thread(target=_loop, daemon=True, name="weather").start()
