"""
main.py — FastAPI server (2-bosqich poydevori).

Endpointlar (TZ 11.1):
  GET /api/health                 — server tirikligi
  GET /api/content[?type=...]     — katalog ro'yxati
  GET /api/content/{id}           — bitta kontent
  GET /api/content/{id}/cover     — muqova (fayl bo'lmasa dinamik SVG)
  GET /api/stream/{id}            — video/audio striming (HTTP Range bilan)
  GET /api/book/{id}/text         — kitob matni (boblar bilan)
  GET /api/ads                    — reklama bannerlari
  GET /api/sites                  — saytlar
  GET /api/route                  — yo'nalish bekatlari
  GET /api/settings               — server sozlamalari (vagon, poyezd, yo'nalish)

Ishga tushirish:
  pip install -r requirements.txt
  python main.py
"""
import os
import json
import time
import hashlib
import asyncio
import logging
import mimetypes
import secrets
from email.utils import formatdate
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response, StreamingResponse, FileResponse, JSONResponse

import config
import db
import licensing
import security
import discovery
import weather
from ws import manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("kiosk.server")


# Umumiy API kalit (db settings'da; birinchi ishga tushishda yaratiladi).
# lifespan'gacha ham kerak bo'lishi mumkin, shuning uchun lazy o'qiladi.
_API_KEY = None


def _api_key():
    global _API_KEY
    if _API_KEY is None:
        db.init_db()
        _API_KEY = db.get_or_create_api_key()
    return _API_KEY


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()   # baza yaratiladi va kerak bo'lsa seed qilinadi
    _api_key()     # kalit tayyor bo'lsin (birinchi so'rovda emas)
    security.ensure_identity()   # imzo kaliti + TLS sertifikat (yo'q bo'lsa)
    manager.set_loop(asyncio.get_running_loop())
    scheme = "https" if config.USE_TLS else "http"
    log.info("Server tayyor — %s://%s:%s", scheme, config.HOST, config.PORT)
    discovery.start()   # imzolangan beacon — kiosklar serverni topadi
    weather.start_refresher()   # internet ob-havoni fonda yuklab/yangilab turadi
    task = asyncio.create_task(_status_loop())   # holatni davriy tarqatish
    yield
    discovery.stop()
    task.cancel()
    log.info("Server to'xtatilmoqda")


async def _status_loop():
    """Har 3 soniyada barcha userlarga status_update yuboradi (TZ FR-HOME-01)."""
    last_err = None
    while True:
        await asyncio.sleep(3)
        # Bitta xato (masalan sozlamadagi noto'g'ri qiymat) butun sikilni
        # to'xtatib qo'ymasin — har iteratsiya o'zini himoyalaydi.
        try:
            if manager.count():
                # Litsenziya kiosk-limitidan ORTGAN qurilmalarga blocked=True
                # bilan yuboriladi (faqat o'sha qurilmalar qulflanadi).
                await manager.broadcast(
                    {"type": "status_update", **status_payload()},
                    blocked_ids=licensing.over_limit_devices())
            last_err = None
        except Exception as e:                           # noqa: BLE001
            # Bir xil xato har 3 soniyada logni to'ldirmasin — faqat xato
            # O'ZGARGANDA to'liq traceback yozamiz.
            msg = f"{type(e).__name__}: {e}"
            if msg != last_err:
                last_err = msg
                log.exception("status sikilida xato — keyingi iteratsiyada davom etamiz")


def _safe_join(base, name):
    """`name`ni `base` katalogi ichida ekanini tekshirib to'liq yo'l qaytaradi.
    `../`, absolyut yo'l yoki boshqa diskka chiqib ketsa None (path traversal
    himoyasi — admin kiritgan yoki buzilgan qiymatlardan)."""
    if not name:
        return None
    base_real = os.path.realpath(base)
    full = os.path.realpath(os.path.join(base_real, name))
    try:
        if os.path.commonpath([base_real, full]) != base_real:
            return None
    except ValueError:
        return None   # turli disklar (Windows) — chiqib ketgan
    return full


app = FastAPI(title="Kiosk Server", version="1.0", lifespan=lifespan)

# Kalitsiz ruxsat etilgan yo'llar: health faqat {"status":"ok"} qaytaradi —
# ulanish ekrani va o'rnatish diagnostikasi uchun ochiq qoladi.
_EXEMPT_PATHS = {"/api/health"}


@app.middleware("http")
async def require_api_key(request: Request, call_next):
    """Barcha /api yo'llari uchun API kalit talab qilinadi.

    Kalit ikki usulda beriladi:
      - `X-API-Key` header (oddiy REST so'rovlar)
      - `?k=` query param (VLC stream va muqova URL'lari — header qo'yib
        bo'lmaydigan joylar uchun)
    Solishtirish timing-safe (secrets.compare_digest)."""
    p = request.url.path
    if p.startswith("/api") and p not in _EXEMPT_PATHS:
        supplied = (request.headers.get("x-api-key")
                    or request.query_params.get("k", ""))
        if not secrets.compare_digest(supplied, _api_key()):
            return JSONResponse({"detail": "API kalit noto'g'ri yoki yo'q"},
                                status_code=401)
    return await call_next(request)


# --- Ulanish ---
@app.get("/api/health")
def health():
    return {"status": "ok"}


# --- Katalog ---
@app.get("/api/content")
def content(type: str | None = None):
    if type and type not in db.CONTENT_TYPES:
        raise HTTPException(400, f"Noma'lum tur: {type}")
    # Kioskka faqat KO'RINADIGAN kontent beriladi (admin "Kiosklarda
    # ko'rsatilsin"ni olib tashlagan bo'lsa — ro'yxatda umuman chiqmaydi).
    # Faqat ANIQ 0 yashiriladi: NULL (eski yozuvlar / DEFAULTsiz insert)
    # KO'RINADI deb hisoblanadi (visible DEFAULT 1 niyati).
    def _visible(c):
        v = c.get("visible", 1)
        return v is None or str(v) != "0"
    return [c for c in db.get_content(type) if _visible(c)]


@app.get("/api/content/{content_id}")
def content_detail(content_id: int):
    item = db.get_content_by_id(content_id)
    if not item:
        raise HTTPException(404, "Kontent topilmadi")
    return item


# --- Muqova: fayl bo'lsa beradi, bo'lmasa dinamik SVG placeholder ---
@app.get("/api/content/{content_id}/cover")
def cover(content_id: int):
    item = db.get_content_by_id(content_id)
    if not item:
        raise HTTPException(404, "Kontent topilmadi")
    path = _safe_join(config.COVERS_DIR, item.get("cover_path"))
    # Muqova rasmlari kamdan-kam o'zgaradi — kiosk uzoq kesh qilsin (1 kun).
    if path and os.path.isfile(path) and not path.endswith(".svg"):
        return FileResponse(path, headers={"Cache-Control": "public, max-age=86400"})
    return Response(content=_placeholder_svg(item["title"], item["type"]),
                    media_type="image/svg+xml",
                    headers={"Cache-Control": "public, max-age=86400"})


def _placeholder_svg(title, type_):
    """Muqova fayli bo'lmaganida ko'rsatiladigan oddiy SVG (offline, kutubxonasiz)."""
    colors = {
        "movie": "#2563EB", "cartoon": "#F59E0B", "music": "#8B5CF6",
        "book": "#0EA5E9", "audiobook": "#10B981",
    }
    bg = colors.get(type_, "#475569")
    safe = (title or "").replace("&", "&amp;").replace("<", "&lt;")
    return f"""<svg xmlns='http://www.w3.org/2000/svg' width='300' height='420'>
  <rect width='100%' height='100%' rx='18' fill='{bg}'/>
  <text x='50%' y='50%' fill='#FFFFFF' font-family='Segoe UI, Arial'
        font-size='22' font-weight='700' text-anchor='middle'>{safe}</text>
  <text x='50%' y='92%' fill='#FFFFFFAA' font-family='Segoe UI, Arial'
        font-size='14' text-anchor='middle'>{type_}</text>
</svg>""".encode("utf-8")


# --- Striming (HTTP Range qo'llab-quvvatlanadi — TZ 11.1 SHART) ---
@app.get("/api/stream/{content_id}")
def stream(content_id: int, request: Request):
    item = db.get_content_by_id(content_id)
    if not item or not item.get("file_path"):
        raise HTTPException(404, "Media topilmadi")
    path = _safe_join(config.MEDIA_DIR, item["file_path"])
    if not path or not os.path.isfile(path):
        raise HTTPException(404, "Media fayli mavjud emas (admin yuklashi kerak)")
    return _range_response(path, request)


def _file_tag(path, file_size):
    """Fayl uchun barqaror ETag (o'lcham + o'zgartirilgan vaqtdan)."""
    mtime = os.path.getmtime(path)
    raw = f"{file_size}-{mtime}".encode()
    return '"' + hashlib.md5(raw).hexdigest() + '"'


def _parse_range(range_header, file_size):
    """'bytes=START-END' ni (start, end) ga aylantiradi. Qo'llab-quvvatlaydi:
       bytes=500-      (500-dan oxirigacha)
       bytes=500-999   (oraliq)
       bytes=-500      (oxirgi 500 bayt)
    Noto'g'ri yoki chegaradan tashqari bo'lsa ValueError ko'taradi (-> 416)."""
    units, _, rng = range_header.partition("=")
    if units.strip() != "bytes" or "," in rng:
        # Bir nechta oraliq qo'llab-quvvatlanmaydi — butun faylni qaytaramiz
        raise ValueError("qo'llab-quvvatlanmaydigan range")
    s, _, e = rng.partition("-")
    s, e = s.strip(), e.strip()
    if s == "" and e == "":
        raise ValueError("bo'sh range")
    if s == "":                       # suffix: oxirgi N bayt
        length = int(e)
        if length <= 0:
            raise ValueError("noto'g'ri suffix")
        start = max(0, file_size - length)
        end = file_size - 1
    else:
        start = int(s)
        end = int(e) if e else file_size - 1
        end = min(end, file_size - 1)
    if start > end or start >= file_size:
        raise ValueError("chegaradan tashqari")
    return start, end


def _range_response(path, request: Request, chunk=1024 * 1024):
    """Faylni HTTP Range (206 Partial Content) bilan oqim qilib beradi."""
    file_size = os.path.getsize(path)
    media_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
    range_header = request.headers.get("range")
    etag = _file_tag(path, file_size)
    last_modified = formatdate(os.path.getmtime(path), usegmt=True)

    base_headers = {
        "Accept-Ranges": "bytes",
        "ETag": etag,
        "Last-Modified": last_modified,
        "Cache-Control": "public, max-age=3600",
    }

    start, end = 0, file_size - 1
    status = 200
    if range_header:
        try:
            start, end = _parse_range(range_header, file_size)
            status = 206
        except ValueError:
            # 416: so'ralgan oraliq qoniqtirilmaydi — joriy o'lchamni bildiramiz
            return Response(
                status_code=416,
                headers={**base_headers, "Content-Range": f"bytes */{file_size}"})

    length = end - start + 1

    def body():
        with open(path, "rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                data = f.read(min(chunk, remaining))
                if not data:
                    break
                remaining -= len(data)
                yield data

    headers = {**base_headers, "Content-Length": str(length)}
    if status == 206:
        headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
    return StreamingResponse(body(), status_code=status,
                             media_type=media_type, headers=headers)


# --- Kitob matni ---
@app.get("/api/book/{content_id}/text")
def book_text(content_id: int):
    item = db.get_content_by_id(content_id)
    if not item or not item.get("text_path"):
        raise HTTPException(404, "Kitob matni topilmadi")
    path = _safe_join(config.BOOKS_DIR, item["text_path"])
    if not path or not os.path.isfile(path):
        raise HTTPException(404, "Matn fayli mavjud emas")
    # Buzilgan/ulkan fayl xotirani to'ldirmasin (kitob matni odatda < birnecha MB)
    if os.path.getsize(path) > 25 * 1024 * 1024:
        raise HTTPException(413, "Matn fayli juda katta")
    try:
        with open(path, encoding="utf-8") as f:
            if path.endswith(".json"):
                return json.load(f)
            return {"chapters": [{"title": item["title"], "text": f.read()}]}
    except (OSError, json.JSONDecodeError) as e:
        raise HTTPException(500, f"Matn faylini o'qib bo'lmadi: {e}")


# --- Reklama ---
_AD_VIDEO_EXT = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v"}


def _ad_media_type(name):
    """Fayl kengaytmasidan reklama turi: video | image | None."""
    if not name:
        return None
    ext = os.path.splitext(name)[1].lower()
    return "video" if ext in _AD_VIDEO_EXT else "image"


@app.get("/api/ads")
def ads():
    """Faol reklamalar. Har biriga media_type qo'shiladi; vaqt oralig'i
    (start_time/end_time) kioskda tekshiriladi — oflayn keshda ham to'g'ri
    ishlashi uchun filtr mijoz tomonda."""
    out = []
    for ad in db.get_ads():
        ad["media_type"] = _ad_media_type(ad.get("media_path"))
        out.append(ad)
    return out


@app.get("/api/ads/{ad_id}/media")
def ad_media(ad_id: int, request: Request):
    """Reklama fayli (rasm yoki video; video HTTP Range bilan)."""
    ad = db.get_ad_by_id(ad_id)
    if not ad or not ad.get("media_path"):
        raise HTTPException(404, "Reklama topilmadi")
    path = _safe_join(config.ADS_DIR, ad["media_path"])
    if not path or not os.path.isfile(path):
        raise HTTPException(404, "Reklama fayli mavjud emas")
    return _range_response(path, request)


@app.get("/api/sites")
def sites():
    return db.get_sites()


# --- Foydalanish statistikasi (kiosk batch yuboradi — services/stats.py) ---
@app.post("/api/stats")
def stats_in(payload: dict):
    """Kioskdan event to'plami: {"device_id": ..., "events": [...]}.
    Validatsiya db.insert_stats ichida (noma'lum eventlar jim tashlanadi)."""
    events = payload.get("events")
    if not isinstance(events, list):
        raise HTTPException(400, "events ro'yxati kerak")
    saved = db.insert_stats(payload.get("device_id"), events[:1000])
    return {"saved": saved}


# --- Kiosk heartbeat: qurilma o'zini tanitadi (admin "Kiosklar" jadvali) ---
@app.post("/api/heartbeat")
def heartbeat(payload: dict, request: Request):
    """Kiosk har 5 soniyada yuboradi: device_id, kiosk raqami/xonasi
    (server.txt'dan), platforma va lokal keshlangan media soni. Ro'yxat
    doimiy — oflayn bo'lib qolgan kiosk ham jadvalda ko'rinadi."""
    device_id = str(payload.get("device_id") or "").strip()[:128]
    if not device_id:
        raise HTTPException(400, "device_id kerak")
    def _i(v):
        try:
            return max(0, int(v))
        except (TypeError, ValueError):
            return 0

    ids = payload.get("cached_ids")
    if not isinstance(ids, list):
        ids = []
    ids = [i for i in ids[:1000] if isinstance(i, int)]
    # Hozir yuklanayotgan media (ixtiyoriy): {id, pct, title} — admin jonli ko'radi
    cg = payload.get("caching")
    if isinstance(cg, dict) and isinstance(cg.get("id"), int):
        caching = json.dumps({
            "id": cg["id"],
            "pct": _i(cg.get("pct")) if isinstance(cg.get("pct"), int)
                   and cg.get("pct") >= 0 else -1,
            "title": str(cg.get("title") or "")[:200],
        })
    else:
        caching = None   # yuklash yo'q — bo'shatamiz
    db.upsert_kiosk(
        device_id,
        kiosk_no=str(payload.get("kiosk_no") or "").strip()[:32],
        room=str(payload.get("room") or "").strip()[:64],
        platform=str(payload.get("platform") or "").strip()[:64],
        cached_n=_i(payload.get("cached")),
        cached_ids=json.dumps(ids),
        disk_total=_i(payload.get("disk_total")),
        disk_free=_i(payload.get("disk_free")),
        caching=caching,
        ip=(request.client.host if request.client else ""),
        last_seen=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    # Kioskка JAVOBда shu qurilmaning lokal-kesh ruxsatini qaytaramiz —
    # admin xotirasiz kiosklarда keshni o'chirib qo'yishi mumkin.
    # `blocked` — GLOBAL blok (litsenziya yaroqsiz/muddati o'tgan/qo'lda blok,
    # status_payload bilan bir xil — WS bilan zid kelib "flap" qilmasin) YOKI
    # per-device kiosk-limiti (50 talik shartnomaga 51-kiosk ulansa).
    return {
        "ok": True,
        "cache": db.get_kiosk_cache_enabled(device_id),
        "blocked": (status_payload()["blocked"]
                    or not licensing.device_allowed(device_id)),
    }


@app.get("/api/route")
def route():
    return db.get_route()


# Kiosk klientlarga beriladigan sozlamalar OQ RO'YXATI. Qora ro'yxat o'rniga
# oq ro'yxat: keyinchalik qo'shiladigan istalgan maxfiy kalit (api_key,
# parol xeshlari, trial_*, ...) javobga avtomatik TUSHMAYDI.
#
# `exit_pin_hash` ATAYLAB beriladi: kiosk chiqish PIN'ini oflayn (keshdan)
# tekshiradi; endpoint API kalit bilan yopiq — bu xesh faqat ishonchli
# (kalitli) klientlarga ketadi. Uni kalitsiz kanalga (masalan, veb-proksi)
# uzatish TAQIQLANADI — kiosk/server/api/settings.ts o'z, yanada tor oq
# ro'yxatini qo'llaydi.
_KIOSK_SETTINGS = {
    "train_name", "route", "depart_time",
    "wagon_number", "wagon_note",
    "default_theme",
    "ad_interval_min", "ad_algorithm", "media_ad_slots",
    "media_cache", "cache_limit_gb",
    "sos_enabled", "sos_numbers", "kiosk_location",
    "saver_facts", "active_route_direction",
    "exit_pin_hash",
}


@app.get("/api/settings")
def settings():
    s = db.get_settings()
    return {k: v for k, v in s.items() if k in _KIOSK_SETTINGS}


def _safe_int(v, default):
    """Sozlama qiymati (erkin matn) butun songa o'girilmasa default qaytaradi."""
    try:
        return int(float(str(v).strip()))
    except (TypeError, ValueError):
        return default


def _hhmm_to_min(t):
    """'HH:MM' ni daqiqaga o'giradi; noto'g'ri format — None.
    Nuqtali variant ('2.21') ham qabul qilinadi (ba'zi jadval yozuvlari)."""
    try:
        h, m = str(t).replace(".", ":").split(":")[:2]
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return None


def _current_stop_index(stops, now_min):
    """Joriy bekat INDEKSINI aniqlaydi — YARIM TUNDAN O'TADIGAN reyslarda ham
    to'g'ri.

    Oddiy 'HH:MM <= now' string solishtirish 22:34 da jo'nab 01:01 da keyingi
    bekatga yetadigan poyezdda buziladi. Yechim: bekat vaqtlarini ketma-ket
    yurib, kamaygan joyda +24 soat qo'shamiz (kun aylanishi); so'ng joriy
    vaqtni shu o'qda joylashtiramiz."""
    if not stops:
        return None
    seq, prev = [], None
    for st in stops:
        t = _hhmm_to_min(st.get("arrival_time") or st.get("departure_time"))
        if t is not None and prev is not None and t < prev:
            t += 1440  # yarim tundan o'tdi
        seq.append(t)
        if t is not None:
            prev = t
    valid = [(i, t) for i, t in enumerate(seq) if t is not None]
    if not valid or now_min is None:
        return 0
    start, end = valid[0][1], valid[-1][1]
    cand = now_min
    if cand < start and cand + 1440 <= end + 60:
        cand += 1440   # joriy vaqt safarning "ertasi kun" qismida
    cur_idx = valid[0][0]
    for i, t in valid:
        if t <= cand:
            cur_idx = i
    return cur_idx


def _current_stop(stops, now_min):
    """Joriy bekat YOZUVI (dict) yoki None — nom va koordinata uchun."""
    idx = _current_stop_index(stops, now_min)
    if idx is None:
        return None
    return stops[idx]


def _segment_speed(stops, now_min):
    """Joriy segment (joriy bekat -> keyingi bekat) o'rtacha tezligi km/h.
    Jadvaldagi masofa (distance_km) va vaqt farqidan hisoblanadi. Oxirgi
    bekatda 0 (yetib keldi); ma'lumot yetarli bo'lmasa None."""
    idx = _current_stop_index(stops, now_min)
    if idx is None:
        return None
    if idx >= len(stops) - 1:
        return 0
    cur, nxt = stops[idx], stops[idx + 1]
    d0, d1 = cur.get("distance_km"), nxt.get("distance_km")
    t_dep = _hhmm_to_min(cur.get("departure_time") or cur.get("arrival_time"))
    t_arr = _hhmm_to_min(nxt.get("arrival_time") or nxt.get("departure_time"))
    if d0 is None or d1 is None or t_dep is None or t_arr is None:
        return None
    dist = d1 - d0
    mins = (t_arr - t_dep) % 1440
    if dist <= 0 or mins <= 0:
        return None
    return round(dist / (mins / 60.0))


# status_payload uchun qisqa TTL kesh: har 3s broadcast + har WS-connect +
# /api/status hammasi DB'ni (settings+route) qayta o'qimasin. 2s — broadcast
# oralig'idan (3s) kichik: reconnect bo'roni DB'ni bombardimon qilmaydi, admin
# o'zgarishi esa baribir keyingi broadcast'da yetadi.
_STATUS_TTL_S = 2.0
_status_cache = {"ts": 0.0, "data": None}


def status_payload():
    """Poyezd holati dict'i (REST va WebSocket ikkalasi ishlatadi).

    Tezlik/harorat sozlamadan olinadi (sensor ulanmaguncha — TZ 6.5).
    Joriy bekat joriy vaqtni bekatlar jadvali bilan solishtirib aniqlanadi.
    Natija ~2 soniya keshlanadi (yuqoridagi izohga qarang).
    """
    now_mono = time.monotonic()
    cached = _status_cache["data"]
    if cached is not None and now_mono - _status_cache["ts"] < _STATUS_TTL_S:
        return cached
    s = db.get_settings()
    stops = db.get_route()
    now = datetime.now()
    now_min = now.hour * 60 + now.minute
    cur_stop = _current_stop(stops, now_min)
    current = cur_stop["name"] if cur_stop else None
    # Tezlik: avto (jadvaldan segment o'rtacha) yoki qo'lda kiritilgan qiymat.
    speed = _safe_int(s.get("speed"), 210)
    if s.get("speed_auto", "1") != "0":
        sp = _segment_speed(stops, now_min)
        if sp is not None:
            speed = sp
    # Harorat: internet ob-havo yoqilgan bo'lsa joriy bekat hududi + joriy vaqt
    # bo'yicha keshdan; topilmasa (kesh yo'q/eskirgan) qo'lda kiritilgan qiymat.
    temperature = _safe_int(s.get("temperature"), 22)
    if s.get("weather_auto", "1") != "0" and cur_stop:
        wt = weather.temp_for(cur_stop.get("latitude"),
                              cur_stop.get("longitude"), now)
        if wt is not None:
            temperature = wt
    payload = {
        "speed": speed,
        "temperature": temperature,
        "wagon": s.get("wagon_number"),
        "wagon_note": s.get("wagon_note"),
        "current_stop": current,
        "train_name": s.get("train_name"),
        "route": s.get("route"),
        # Blok = IMZOLANGAN litsenziya holati (yo'q/yaroqsiz/muddati o'tgan/
        # boshqa kompyuter) YOKI eski qo'lda blok (trial_blocked — vendor
        # admin paneldan darhol qulflashi uchun saqlangan).
        "blocked": (licensing.state()["blocked"]
                    or db.trial_state(s)["blocked"]),
    }
    _status_cache["data"] = payload
    _status_cache["ts"] = now_mono
    return payload


@app.get("/api/status")
def status():
    return status_payload()


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """Real vaqt kanal (TZ 11.2): register qabul qiladi, status/announcement yuboradi."""
    # Kalit tekshiruvi (?k=...): begona qurilmalar broadcast'larni eshitmasin,
    # soxta device_id bilan ro'yxatdan o'tmasin.
    if not secrets.compare_digest(ws.query_params.get("k", ""), _api_key()):
        await ws.close(code=4401)
        return
    await manager.connect(ws)
    # Ulanishi bilan joriy holatni darhol yuboramiz. MUHIM: status_loop bilan
    # bir socketда bir vaqtda yuborilmasin — manager qulfi serializatsiya qiladi
    # (aks holda Starlette "Concurrent call to send" beradi).
    await manager.send_personal(ws, {"type": "status_update", **status_payload()})
    try:
        while True:
            # Xom matnni avval o'qib, hajmini cheklaymiz — buzilgan/zararli kiosk
            # ulkan freym yuborib serverни xotira bilan bosib qo'ymasin.
            raw = await ws.receive_text()
            if len(raw) > 64 * 1024:
                log.warning("WS: juda katta freym (%d bayt) — e'tiborsiz", len(raw))
                continue
            try:
                data = json.loads(raw)
            except (ValueError, TypeError):
                continue
            if not isinstance(data, dict):
                continue
            mtype = data.get("type")
            if mtype == "register":
                manager.register(ws, data.get("device_id"), data.get("platform"))
                log.info("Kiosk ulandi: %s (%s) — jami %d",
                         data.get("device_id"), data.get("platform"), manager.count())
            elif mtype == "ping":
                await manager.send_personal(ws, {"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(ws)
        log.info("Kiosk uzildi — jami %d", manager.count())
    except Exception as e:
        manager.disconnect(ws)
        log.warning("WebSocket xatosi: %s — jami %d", e, manager.count())


if __name__ == "__main__":
    import uvicorn
    security.ensure_identity()   # TLS sertifikat uvicorn'gacha tayyor bo'lsin
    ssl_kw = ({"ssl_certfile": security.TLS_CERT_PATH,
               "ssl_keyfile": security.TLS_KEY_PATH} if config.USE_TLS else {})
    uvicorn.run("main:app", host=config.HOST, port=config.PORT,
                reload=False, **ssl_kw)
