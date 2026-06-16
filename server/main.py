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
import security
import discovery
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
    task = asyncio.create_task(_status_loop())   # holatni davriy tarqatish
    yield
    discovery.stop()
    task.cancel()
    log.info("Server to'xtatilmoqda")


async def _status_loop():
    """Har 3 soniyada barcha userlarga status_update yuboradi (TZ FR-HOME-01)."""
    while True:
        await asyncio.sleep(3)
        # Bitta xato (masalan sozlamadagi noto'g'ri qiymat) butun sikilni
        # to'xtatib qo'ymasin — har iteratsiya o'zini himoyalaydi.
        try:
            if manager.count():
                await manager.broadcast({"type": "status_update", **status_payload()})
        except Exception:
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
    return db.get_content(type)


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
    db.upsert_kiosk(
        device_id,
        kiosk_no=str(payload.get("kiosk_no") or "").strip()[:32],
        room=str(payload.get("room") or "").strip()[:64],
        platform=str(payload.get("platform") or "").strip()[:64],
        cached_n=_i(payload.get("cached")),
        cached_ids=json.dumps(ids),
        disk_total=_i(payload.get("disk_total")),
        disk_free=_i(payload.get("disk_free")),
        ip=(request.client.host if request.client else ""),
        last_seen=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    return {"ok": True}


@app.get("/api/route")
def route():
    return db.get_route()


# Kioskka berilmaydigan maxfiy sozlamalar (himoya qatlami — endpoint kalit
# bilan yopiq bo'lsa ham, sirlar javobda ko'rinmasin).
_PRIVATE_SETTINGS = {"api_key", "admin_password_hash"}


@app.get("/api/settings")
def settings():
    s = db.get_settings()
    return {k: v for k, v in s.items() if k not in _PRIVATE_SETTINGS}


def _safe_int(v, default):
    """Sozlama qiymati (erkin matn) butun songa o'girilmasa default qaytaradi."""
    try:
        return int(float(str(v).strip()))
    except (TypeError, ValueError):
        return default


def _hhmm_to_min(t):
    """'HH:MM' ni daqiqaga o'giradi; noto'g'ri format — None."""
    try:
        h, m = str(t).split(":")
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return None


def _current_stop(stops, now_min):
    """Joriy bekatni aniqlaydi — YARIM TUNDAN O'TADIGAN reyslarda ham to'g'ri.

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
        return stops[0]["name"]
    start, end = valid[0][1], valid[-1][1]
    cand = now_min
    if cand < start and cand + 1440 <= end + 60:
        cand += 1440   # joriy vaqt safarning "ertasi kun" qismida
    cur_idx = valid[0][0]
    for i, t in valid:
        if t <= cand:
            cur_idx = i
    return stops[cur_idx]["name"]


def status_payload():
    """Poyezd holati dict'i (REST va WebSocket ikkalasi ishlatadi).

    Tezlik/harorat sozlamadan olinadi (sensor ulanmaguncha — TZ 6.5).
    Joriy bekat joriy vaqtni bekatlar jadvali bilan solishtirib aniqlanadi.
    """
    s = db.get_settings()
    stops = db.get_route()
    now = datetime.now()
    current = _current_stop(stops, now.hour * 60 + now.minute)
    return {
        "speed": _safe_int(s.get("speed"), 210),
        "temperature": _safe_int(s.get("temperature"), 22),
        "wagon": s.get("wagon_number"),
        "wagon_note": s.get("wagon_note"),
        "current_stop": current,
        "train_name": s.get("train_name"),
        "route": s.get("route"),
    }


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
            data = await ws.receive_json()
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
