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
from email.utils import formatdate
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response, StreamingResponse, FileResponse

import config
import db
from ws import manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("kiosk.server")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()   # baza yaratiladi va kerak bo'lsa seed qilinadi
    manager.set_loop(asyncio.get_running_loop())
    log.info("Server tayyor — http://%s:%s", config.HOST, config.PORT)
    task = asyncio.create_task(_status_loop())   # holatni davriy tarqatish
    yield
    task.cancel()
    log.info("Server to'xtatilmoqda")


async def _status_loop():
    """Har 3 soniyada barcha userlarga status_update yuboradi (TZ FR-HOME-01)."""
    while True:
        await asyncio.sleep(3)
        if manager.count():
            await manager.broadcast({"type": "status_update", **status_payload()})


app = FastAPI(title="Kiosk Server", version="1.0", lifespan=lifespan)


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
    path = os.path.join(config.COVERS_DIR, item.get("cover_path") or "")
    # Muqova rasmlari kamdan-kam o'zgaradi — kiosk uzoq kesh qilsin (1 kun).
    if item.get("cover_path") and os.path.isfile(path) and not path.endswith(".svg"):
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
    path = os.path.join(config.MEDIA_DIR, item["file_path"])
    if not os.path.isfile(path):
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
    path = os.path.join(config.BOOKS_DIR, item["text_path"])
    if not os.path.isfile(path):
        raise HTTPException(404, "Matn fayli mavjud emas")
    with open(path, encoding="utf-8") as f:
        if path.endswith(".json"):
            return json.load(f)
        return {"chapters": [{"title": item["title"], "text": f.read()}]}


# --- Boshqa ---
@app.get("/api/ads")
def ads():
    return db.get_ads()


@app.get("/api/sites")
def sites():
    return db.get_sites()


@app.get("/api/route")
def route():
    return db.get_route()


@app.get("/api/settings")
def settings():
    return db.get_settings()


def status_payload():
    """Poyezd holati dict'i (REST va WebSocket ikkalasi ishlatadi).

    Tezlik/harorat sozlamadan olinadi (sensor ulanmaguncha — TZ 6.5).
    Joriy bekat joriy vaqtni bekatlar jadvali bilan solishtirib aniqlanadi.
    """
    s = db.get_settings()
    stops = db.get_route()
    now = datetime.now().strftime("%H:%M")
    current = stops[0]["name"] if stops else None
    for st in stops:
        if st.get("arrival_time") and st["arrival_time"] <= now:
            current = st["name"]
    return {
        "speed": int(s.get("speed", 210)),
        "temperature": int(s.get("temperature", 22)),
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
    await manager.connect(ws)
    # Ulanishi bilan joriy holatni darhol yuboramiz
    await ws.send_json({"type": "status_update", **status_payload()})
    try:
        while True:
            data = await ws.receive_json()
            mtype = data.get("type")
            if mtype == "register":
                manager.register(ws, data.get("device_id"), data.get("platform"))
                log.info("Kiosk ulandi: %s (%s) — jami %d",
                         data.get("device_id"), data.get("platform"), manager.count())
            elif mtype == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(ws)
        log.info("Kiosk uzildi — jami %d", manager.count())
    except Exception as e:
        manager.disconnect(ws)
        log.warning("WebSocket xatosi: %s — jami %d", e, manager.count())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=config.HOST, port=config.PORT, reload=False)
