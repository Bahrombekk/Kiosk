"""
main.py — Bulut (markaziy admin) FastAPI ilovasi.

Ikki xil mijoz bor va ikkisi butunlay boshqacha autentifikatsiya bilan
ishlaydi:

  * **Agent** = poyezd serveri. `/api/enroll` bilan bir martalik token'ni
    doimiy `server_token`ga almashadi, so'ng `/agent` WebSocket'ini doimiy
    ochiq tutadi. Fayllarni `/dl/<imzolangan-token>` dan Range bilan tortadi.
  * **Admin** = brauzerdagi panel (`static/`). Parol bilan kiradi, sessiya
    cookie oladi va `/api/admin/*` bilan ishlaydi.

Ishga tushirish:
    pip install -r requirements.txt
    python main.py                 # http://0.0.0.0:9000
"""
import asyncio
import json
import logging
import logging.handlers
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import (Cookie, Depends, FastAPI, HTTPException, Query, Request,
                     WebSocket, WebSocketDisconnect)
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

import config
import db
import security
import storage
from relay import relay

log = logging.getLogger("cloud")

STATIC_DIR = os.path.join(config.BASE_DIR, "web")   # frontend SPA (cloud/web/)


def _setup_logging():
    os.makedirs(os.path.dirname(config.LOG_PATH), exist_ok=True)
    fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-7s  %(name)s  %(message)s", "%H:%M:%S")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    root.addHandler(sh)
    try:
        fh = logging.handlers.RotatingFileHandler(
            config.LOG_PATH, maxBytes=5 * 1024 * 1024, backupCount=2,
            encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except OSError:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    storage.init()
    security.ensure_identity()
    security.ensure_admin_password()
    log.info("Bulut tayyor — %s://%s:%s",
             "https" if config.USE_TLS else "http", config.HOST, config.PORT)
    watch = asyncio.create_task(_offline_watch())
    ops = asyncio.create_task(_ops_loop())
    yield
    watch.cancel()
    ops.cancel()
    log.info("Bulut to'xtatilmoqda")


async def _ops_loop():
    """Navbatда turgan va vaqti kelgan buyruqlarni yuboradi.

    Shu sikl tufayli "saqlash" hech qachon yo'qolmaydi: server oflayn bo'lsa
    yoki reja qo'yilgan bo'lsa, buyruq bazada turadi va shart bajarilishi bilan
    (server onlayn + vaqti kelgan) o'zi qo'llanadi."""
    while True:
        await asyncio.sleep(10)
        try:
            for op in db.due_ops():
                sid = op["server_id"]
                if not db.is_approved(sid):
                    continue
                try:
                    fields = json.loads(op["payload"] or "{}")
                except ValueError:
                    fields = {}
                srv = db.get_server(sid) or {}

                # BULUT TOMONIDA bajariladigan ish (buyruq emas): rejalashtirilgan
                # tarqatish. Server offlayn bo'lса ham tayinlov qo'yiladi —
                # keyin ulanganда o'zi tortib oladi.
                if op["kind"] == "deploy_apply":
                    cids = [int(i) for i in fields.get("content_ids") or []]
                    if cids:
                        db.assign([sid], cids)
                        job_id = fields.get("job_id")
                        if isinstance(job_id, int):
                            await relay.dispatch_job(job_id, [sid])
                        elif relay.is_online(sid):
                            await relay.push_manifest(sid)
                    db.mark_op_sent(op["id"])
                    db.add_event(f"{srv.get('name', sid)} — rejalashtirilgan "
                                 f"tarqatish qo'llandi ({len(cids)} fayl)", "ok")
                    continue

                if not relay.is_online(sid):
                    continue                      # buyruqlar ulanganда ketadi
                if await relay.send_cmd(sid, op["kind"], **fields):
                    db.mark_op_sent(op["id"])
                    db.add_event(f"{srv.get('name', sid)} — navbatdagi buyruq "
                                 f"qo'llandi: {op['label'] or op['kind']}", "ok")
        except Exception:                                        # noqa: BLE001
            log.exception("navbat siklida xato")


app = FastAPI(title="Kiosk Cloud", version="1.0", lifespan=lifespan)


async def _offline_watch():
    """Uzilgan serverlarni hodisalar oqimiga yozadi (paneldagi "So'nggi
    hodisalar" va mobil "Diqqat talab qiladi" ro'yxati shundan oziqlanadi)."""
    seen_offline = set()
    while True:
        await asyncio.sleep(30)
        try:
            for s in db.get_servers():
                sid = s["id"]
                online = relay.is_online(sid) or db.is_online(s)
                if not online and sid not in seen_offline and s.get("last_seen"):
                    seen_offline.add(sid)
                    db.add_event(f"{s['name']} — aloqa uzildi", "err")
                elif online and sid in seen_offline:
                    seen_offline.discard(sid)
                    db.add_event(f"{s['name']} — aloqa tiklandi", "ok")
        except Exception:                                        # noqa: BLE001
            log.exception("offline kuzatuvida xato")


# =====================================================================
#  AGENT (poyezd serveri) tomoni
# =====================================================================
# Panel (static/app.js) shu qiymatni o'zining UI_BUILD'i bilan solishtiradi.
# API o'zgarganda OSHIRILADI — shunda brauzerdagi yangi UI eski backendga
# urilib "Not Found" bermaydi, balki aniq "qayta ishga tushiring" deb aytadi.
# (Statik fayllar diskdan o'qiladi, ya'ni UI restartsiz yangilanadi; endpointlar
# esa yangilanmaydi — chalkashlik aynan shundan chiqadi.)
# ═══════════════════════════════════════════════════════════════════════════
#  MARSHRUT INDEKSI (navigatsiya — yo'lni qidiring, masalan "/api/enroll")
#    QURILMA (imzosiz/agent):  /api/enroll · /agent (WS) · /dl/{token}
#    ADMIN AUTH:               /api/admin/login  (qolgani `_=A` bilan himoyalangan)
#    SERVERLAR:                /api/admin/servers[...]  approve/reject/patch/command/settings
#    KONTENT:                  /api/admin/content[...]  + assign/unassign
#    REKLAMA/SAYT/BEKAT:       /api/admin/ads · /sites · /servers/{id}/stops
#    BRENDING:                 /api/admin/branding/library · /servers/{id}/branding
#    ISHLAR/STAT:              /api/admin/jobs · /overview · /servers/{id} (stat)
#    PANEL:                    /  (index.html, APP_BUILD bilan kesh-bust)
#  MUHIM: har admin marshruti `_=A` (sessiya) bilan; buyruqlar Ed25519 imzolanadi
#  (send_cmd→sign_command); tasdiqlanmagan serverga kontent/buyruq ketmaydi.
# ═══════════════════════════════════════════════════════════════════════════
APP_BUILD = "2026-08-06.2"


@app.get("/api/health")
def health():
    return {"status": "ok", "build": APP_BUILD}


@app.post("/api/enroll")
def enroll(payload: dict):
    """Serverni ro'yxatga oladi va doimiy `server_token` beradi.

    Ikki yo'l bor:

    1. **Tokensiz (odatiy)** — poyezd serveriga FAQAT bulut manzili (domen)
       yoziladi, boshqa hech narsa kiritilmaydi. Server o'zi ulanadi va
       ro'yxatda "tasdiqlash kerak" bo'lib turadi; admin panelda bir marta
       «Tasdiqlash» bosadi. Tasdiqlanmaguncha unga na kontent, na buyruq
       yuboriladi — ya'ni begona qurilma ulanса ham hech narsa olmaydi.

    2. **Enroll token bilan** — oldindan yaratilgan bir martalik token
       ko'rsatilса, server DARHOL tasdiqlangan bo'ladi (qo'lда bosish kerak
       emas). Bu ko'p serverni bir yo'la o'rnatishda qulay.

    Bir xil qurilma qayta enroll qilса (bazasi tozalangan/qayta o'rnatilgan)
    yangi yozuv yaratilmaydi — eskisi yangi token bilan qayta ishlatiladi.
    """
    token = str(payload.get("enroll_token") or "").strip()
    hw_id = str(payload.get("hw_id") or "")[:128]
    name = str(payload.get("name") or "").strip()
    route = str(payload.get("route") or "").strip()
    row = None

    if token:
        row = db.consume_enroll_token(token)
        if not row:
            raise HTTPException(403, "token yaroqsiz yoki allaqachon ishlatilgan")
        name = name or row.get("label") or "Nomsiz server"
        route = route or (row.get("route") or "")
    name = name or "Nomsiz server"

    server_token = os.urandom(24).hex()
    existing = db.server_by_hw(hw_id)
    if existing:
        # Shu qurilma allaqachon ro'yxatda — yangi token beramiz, dublikat yo'q
        sid = existing["id"]
        db.reissue_token(sid, server_token)
        if token:
            db.approve_server(sid, True)      # token bilan kelsa tasdiqlanadi
        approved = db.is_approved(sid)
        log.info("Server qayta ro'yxatga olindi: %s (%s)", sid, name)
        db.add_event(f"{existing['name']} qayta ulandi (yangi token)", "info")
    else:
        sid = db.create_server(name[:120], route[:160], server_token, hw_id,
                               approved=1 if token else 0)
        approved = bool(token)
        # Qurilma o'z vertikalini bildiradi (avtobus -> 'bus') — YANGI serverга
        # STANDART sifatida saqlaymiz; admin panelda tasdiqlaganda o'zgartira oladi.
        _vhint = str(payload.get("vertical") or "").strip().lower()
        if _vhint in ("train", "bus"):
            db.update_server(sid, vertical=_vhint)
        if token:
            db.mark_enroll_used(row["id"], sid)
            db.add_event(f"{name} bulutga ulandi (kalit bilan)", "ok")
        else:
            db.add_event(f"{name} o'zi ulandi — TASDIQLASH kerak", "warn")
        log.info("Yangi server: %s (%s) tasdiqlangan=%s", sid, name, approved)
    db.update_server(sid, version=str(payload.get("version") or "")[:32])
    return {
        "server_id": sid,
        "server_token": server_token,
        "cloud_pubkey": security.public_key_b64(),
        "heartbeat_s": config.HEARTBEAT_INTERVAL_S,
        "approved": approved,
    }


@app.websocket("/agent")
async def agent_ws(ws: WebSocket, server_id: str = Query(""),
                   token: str = Query("")):
    """Agent kanali. Kelgan xabar turlari:
         register  — ulanish boshida (versiya, kiosklar, applied_rev)
         heartbeat — 30 soniyada holat
         progress  — yuklash jarayoni (job_id bo'yicha)
         applied   — manifest to'liq qo'llanildi (rev)
         stats     — kiosk statistikasi (batch)
         logs      — server loglari (batch)
    """
    if not server_id or not db.server_auth(server_id, token):
        await ws.close(code=4401)      # noto'g'ri token
        return
    await ws.accept()
    await relay.attach(server_id, ws)
    db.touch_server(server_id)
    try:
        # Manifest shu yerda YUBORILMAYDI — agent darhol `register` yuboradi va
        # sinxronizatsiya shunda boshlanadi (aks holda manifest ikki marta
        # ketadi va server ayni ishni ikki marta bajaradi).
        await ws.send_json({"type": "hello",
                            "heartbeat_s": config.HEARTBEAT_INTERVAL_S,
                            "approved": db.is_approved(server_id)})
        while True:
            msg = await ws.receive_json()
            if not isinstance(msg, dict):
                continue
            await _handle_agent_msg(server_id, msg, ws)
    except WebSocketDisconnect:
        pass
    except (json.JSONDecodeError, ValueError):
        log.warning("%s: buzuq xabar — ulanish yopiladi", server_id)
    except Exception:                                            # noqa: BLE001
        log.exception("%s: agent kanalida xato", server_id)
    finally:
        relay.detach(server_id, ws)


async def _handle_agent_msg(server_id, msg, ws):
    kind = msg.get("type")

    if kind in ("register", "heartbeat"):
        fields = {
            "version": str(msg.get("version") or "")[:32],
            "kiosks_total": db.to_int(msg.get("kiosks_total")),
            "kiosks_online": db.to_int(msg.get("kiosks_online")),
            "disk_total": db.to_int(msg.get("disk_total")),
            "disk_free": db.to_int(msg.get("disk_free")),
            "license": str(msg.get("license") or "")[:32],
            "license_note": str(msg.get("license_note") or "")[:120],
            "applied_rev": db.to_int(msg.get("applied_rev")),
            "queue_active": db.to_int(msg.get("queue_active")),
            "queue_pending": db.to_int(msg.get("queue_pending")),
            "stats_pending": db.to_int(msg.get("stats_pending")),
            "stats_total": db.to_int(msg.get("stats_total")),
            "web_running": 1 if msg.get("web_running") else 0,
            "last_seen": db.now(),
        }
        cur = db.get_server(server_id) or {}
        # Nomni FAQAT admin qo'ymagan bo'lsa serverdan olamiz — aks holda har
        # heartbeatда hostname («GPUPC») admin bergan nomni bosib ketardi.
        if msg.get("name") and not cur.get("name_custom"):
            fields["name"] = str(msg["name"])[:120]
        if msg.get("route") and not cur.get("name_custom"):
            fields["route"] = str(msg["route"])[:160]
        if isinstance(msg.get("license_info"), dict):
            fields["license_info"] = json.dumps(msg["license_info"],
                                                ensure_ascii=False)
        if isinstance(msg.get("settings"), dict):
            # Serverning joriy sozlamalari — panel shu qiymatlarni forma
            # sifatida ko'rsatadi (JSON bo'lib saqlanadi)
            fields["settings"] = json.dumps(msg["settings"], ensure_ascii=False)
        if isinstance(msg.get("catalog"), dict):
            # Lokal katalog hisoblari (har heartbeatда keladi — yengil)
            fields["catalog_counts"] = json.dumps(msg["catalog"], ensure_ascii=False)
        db.update_server(server_id, **fields)
        ks = msg.get("kiosks")
        if isinstance(ks, list):
            db.replace_server_kiosks(server_id, ks)
        srv = db.get_server(server_id) or {}
        await ws.send_json({"type": "hb_ack",
                            "desired_rev": srv.get("desired_rev", 0),
                            "approved": bool(srv.get("approved"))})
        if kind == "register":
            await relay.on_register(server_id)
            # Ulanish tiklandi — navbatда turgan buyruqlarni darhol yuboramiz
            # ("saqlash"ni oflaynда bosgan bo'lsa shu yerda qo'llanadi)
            await relay.flush_ops(server_id)
        elif srv.get("applied_rev") != srv.get("desired_rev"):
            # Heartbeatда farq ko'rinsa — manifest yuboramiz (buyruq yo'qolgan
            # yoki server offlaynда o'tkazib yuborgan holat o'zini tuzatadi).
            await relay.push_manifest(server_id)

    elif kind == "progress":
        job_id = msg.get("job_id")
        if isinstance(job_id, int):
            state = str(msg.get("state") or "running")
            if state not in ("running", "done", "error", "queued"):
                state = "running"
            db.set_target(job_id, server_id, state=state,
                          pct=max(0, min(100, db.to_int(msg.get("pct")))),
                          bytes_done=db.to_int(msg.get("bytes")),
                          bytes_total=db.to_int(msg.get("total")),
                          error=str(msg.get("error") or "")[:300] or None)

    elif kind == "applied":
        rev = db.to_int(msg.get("rev"))
        db.update_server(server_id, applied_rev=rev)
        for p in db.pending_targets(server_id):
            db.set_target(p["job_id"], server_id, state="done", pct=100)
        srv = db.get_server(server_id) or {}
        db.add_event(f"{srv.get('name', server_id)} — sinxronizatsiya tugadi "
                     f"(rev {rev})", "ok")

    elif kind == "stats":
        # Tasdiqlanmagan serverdan statistika QABUL QILINMAYDI — begona qurilma
        # bulut hisobotlarini buzib qo'ymasin.
        if not db.is_approved(server_id):
            return
        ev = msg.get("events")
        if isinstance(ev, list):
            n = db.insert_stats(server_id, ev)
            if n:
                await ws.send_json({"type": "stats_ack", "n": n})

    elif kind == "logs":
        if not db.is_approved(server_id):
            return
        en = msg.get("entries")
        if isinstance(en, list):
            n = db.insert_logs(server_id, en)
            if n:
                await ws.send_json({"type": "logs_ack", "n": n})

    elif kind == "local_catalog":
        # Serverning lokal katalogi (poyezdда qo'shilgan kontent/reklama/sayt/
        # bekat) — faqat O'ZGARGANда keladi. Panel KO'RSATISHI uchun saqlaymiz.
        # Tasdiqlanmagan serverdan QABUL QILMAYMIZ (stats/logs bilan bir xil
        # chegara — begona qurilma panel telemetriyasини buzmasин).
        if not db.is_approved(server_id):
            return
        cat = msg.get("catalog")
        if isinstance(cat, dict):
            db.set_local_catalog(server_id, cat)


@app.get("/dl/{token}")
def download(token: str, request: Request):
    """Imzolangan, muddatli fayl havolasi (agent Range bilan tortadi).

    Sessiya ham, API kalit ham kerak emas — tokenning o'zi ruxsat. Ichida
    sha256, server_id va muddat bor; birortasi mos kelmasa 403."""
    body = security.read_dl_token(token)
    if not body:
        raise HTTPException(403, "havola yaroqsiz yoki muddati o'tgan")
    path = storage.blob_path(body.get("s"))
    if not path or not os.path.isfile(path):
        raise HTTPException(404, "fayl topilmadi")
    return storage.range_response(path, request, filename=body.get("n") or None)


# =====================================================================
#  ADMIN (brauzer paneli) tomoni
# =====================================================================
_fails = {}          # ip -> [urinishlar soni, birinchi urinish vaqti]


def _rate_limited(ip):
    n, t0 = _fails.get(ip, (0, 0.0))
    if n >= 8 and time.monotonic() - t0 < 300:
        return True
    if t0 and time.monotonic() - t0 > 600:
        _fails.pop(ip, None)
    return False


def _note_fail(ip):
    n, t0 = _fails.get(ip, (0, 0.0))
    _fails[ip] = (n + 1, t0 or time.monotonic())


def require_admin(cs: str = Cookie(default="")):
    """Admin sessiyasi (cookie). Yo'q bo'lsa 401 — panel login ekraniga o'tadi."""
    if not security.valid_session(cs):
        raise HTTPException(401, "kirish kerak")
    return True


A = Depends(require_admin)


@app.post("/api/admin/login")
def admin_login(payload: dict, request: Request):
    """Login + parol. Login bo'sh bo'lsa `admin` deb qabul qilinadi (eski,
    faqat parolli kirish ham ishlashda davom etadi).

    Xato holatда QAYSI maydon xato ekani aytilmaydi — mavjud loginlarni
    taxmin qilib chiqishning oldi olinadi. Urinish chegarasi IP + login
    juftligi bo'yicha: bitta hisobni tashqaridan bloklab qo'yish qiyinlashadi."""
    ip = request.client.host if request.client else "?"
    username = str(payload.get("username") or "").strip()[:64]
    who = f"{ip}|{username.lower()}"
    if _rate_limited(who) or _rate_limited(ip):
        raise HTTPException(429, "juda ko'p urinish — 5 daqiqadan keyin urinib ko'ring")
    user = security.check_login(username, str(payload.get("password") or ""))
    if not user:
        _note_fail(who)
        _note_fail(ip)
        log.warning("Admin kirish muvaffaqiyatsiz: %s (login=%r)", ip, username)
        raise HTTPException(403, "login yoki parol noto'g'ri")
    _fails.pop(who, None)
    _fails.pop(ip, None)
    remember = bool(payload.get("remember"))
    token = security.new_session(user, remember)
    ttl = (7 * 24 * 3600) if remember else config.SESSION_TTL_S
    r = JSONResponse({"ok": True, "username": user["username"],
                      "role": user.get("role") or "super", "ttl": ttl})
    r.set_cookie("cs", token, httponly=True, samesite="lax",
                 secure=config.USE_TLS, max_age=ttl)
    log.info("Admin kirdi: %s (%s)", user["username"], ip)
    return r


@app.post("/api/admin/logout")
def admin_logout(cs: str = Cookie(default="")):
    security.drop_session(cs)
    r = JSONResponse({"ok": True})
    r.delete_cookie("cs")
    return r


@app.get("/api/admin/me")
def admin_me(cs: str = Cookie(default="")):
    u = security.session_user(cs) if security.valid_session(cs) else None
    return {"auth": bool(u), "user": u,
            "servers_total": len(db.get_servers()) if u else 0}


def _srv_view(s):
    """Server yozuvini panel uchun boyitadi (onlayn holat, sinx foizi)."""
    online = relay.is_online(s["id"]) or db.is_online(s)
    dr, ar = s.get("desired_rev", 0), s.get("applied_rev", 0)
    synced = (dr == ar)
    disk_pct = 0
    if s.get("disk_total"):
        disk_pct = round(100 * (s["disk_total"] - s.get("disk_free", 0))
                         / s["disk_total"])
    def _j(raw):
        try:
            return json.loads(raw or "{}")
        except (ValueError, TypeError):
            return {}
    return {**s, "online": online, "synced": synced, "disk_pct": disk_pct,
            "assigned": len(db.assigned_ids(s["id"])),
            "settings": _j(s.get("settings")),
            "license_info": _j(s.get("license_info")),
            # Serverning lokal katalog hisoblari (poyezdda mavjud kontent)
            "catalog_counts": _j(s.get("catalog_counts")),
            "ops_pending": db.pending_op_count(s["id"])}


@app.get("/api/admin/overview")
def overview(_=A):
    servers = [_srv_view(s) for s in db.get_servers()]
    online = [s for s in servers if s["online"]]
    kiosks_total = sum(s.get("kiosks_total", 0) for s in servers)
    kiosks_online = sum(s.get("kiosks_online", 0) for s in servers)
    n_blobs, used, free = storage.usage()
    jobs = db.get_jobs(limit=6, active_only=True)
    st = db.stats_totals(days=1)
    return {
        "kpis": {
            "servers_online": len(online), "servers_total": len(servers),
            "kiosks_online": kiosks_online, "kiosks_total": kiosks_total,
            "sessions_today": st["sessions"],
            "unsynced": len([s for s in servers if not s["synced"]]),
        },
        "storage": {"files": n_blobs, "used": used, "free": free},
        "servers": servers,
        "jobs": jobs,
        "events": db.recent_events(10),
    }


@app.get("/api/admin/servers")
def servers_list(_=A):
    return [_srv_view(s) for s in db.get_servers()]


@app.get("/api/admin/servers/{server_id}")
def server_detail(server_id: str, _=A):
    s = db.get_server(server_id)
    if not s:
        raise HTTPException(404, "server topilmadi")
    return {
        "server": _srv_view(s),
        "kiosks": db.get_server_kiosks(server_id),
        "content": db.desired_content(server_id),
        "stats": db.stats_totals(days=14, server_id=server_id),
        "daily": db.stats_daily(days=14, server_id=server_id),
        "sessions": db.server_sessions_list(server_id, 30),
        "sessions_today": db.server_sessions_today(server_id),
        # Kiosk kartochkalarida ko'rsatiladigan sessiya hisobi (bugun / 14 kun)
        "kiosk_sessions": db.kiosk_session_counts(server_id, 1),
        "kiosk_sessions_14": db.kiosk_session_counts(server_id, 14),
        "logs": db.get_logs(server_id=server_id, limit=50),
        "ops": db.get_pending_ops(server_id),
        "stops": db.get_stops(server_id),
        "branding": {b["kind"]: b for b in db.get_branding(server_id)},
        # Serverning O'ZIDA (poyezdda) mavjud lokal katalog — panel ko'rsatadi
        "local_catalog": db.get_local_catalog(server_id),
    }


@app.patch("/api/admin/servers/{server_id}")
def server_patch(server_id: str, payload: dict, _=A):
    """Serverga nom / yo'nalish / izoh beradi (bulutdagi ko'rinadigan nom)."""
    if not db.get_server(server_id):
        raise HTTPException(404, "server topilmadi")
    name = payload.get("name")
    if name is not None:
        name = str(name).strip()[:120]
        if not name:
            raise HTTPException(400, "nom bo'sh bo'lmaydi")
    db.rename_server(
        server_id, name=name,
        route=(str(payload["route"])[:160] if "route" in payload else None),
        note=(str(payload["note"])[:500] if "note" in payload else None))
    # Vertikal (poyezd/avtobus) — panel yorliqlari shunga qarab moslanadi.
    if "vertical" in payload:
        v = str(payload["vertical"] or "").strip().lower()
        if v in ("train", "bus"):
            db.update_server(server_id, vertical=v)
    return {"ok": True}


@app.patch("/api/admin/servers/{server_id}/kiosk-label")
def kiosk_label(server_id: str, payload: dict, _=A):
    """Kioskка nom beradi ("1-vagon, o'ng tomon"). Bu nom bulut panelида
    device_id o'rniga ko'rinadi — jadvalda kiosklarni ajratish osonlashadi."""
    device_id = str(payload.get("device_id") or "").strip()
    if not device_id:
        raise HTTPException(400, "device_id kerak")
    if not db.get_server(server_id):
        raise HTTPException(404, "server topilmadi")
    db.set_kiosk_label(server_id, device_id,
                       str(payload.get("label") or "").strip()[:120] or None)
    return {"ok": True}


@app.post("/api/admin/servers/{server_id}/approve")
async def server_approve(server_id: str, payload: dict | None = None, _=A):
    """O'zi ulangan serverni tasdiqlaydi — shundan keyin kontent/buyruq ketadi.
    Ixtiyoriy `vertical` ('train'|'bus') — admin qurilma turini tanlaydi, panel
    yorliqlari shunga qarab moslanadi."""
    s = db.get_server(server_id)
    if not s:
        raise HTTPException(404, "server topilmadi")
    v = str((payload or {}).get("vertical") or "").strip().lower()
    if v in ("train", "bus"):
        db.update_server(server_id, vertical=v)
    db.approve_server(server_id, True)
    db.add_event(f"{s['name']} TASDIQLANDI", "ok")
    # Darhol sinxronizatsiya (tayinlangan kontent bo'lsa yuklab oladi)
    if relay.is_online(server_id):
        await relay.on_register(server_id)
    return {"ok": True}


@app.delete("/api/admin/servers/{server_id}")
def server_delete(server_id: str, _=A):
    s = db.get_server(server_id)
    if not s:
        raise HTTPException(404, "server topilmadi")
    relay.detach(server_id)
    db.delete_server(server_id)
    db.add_event(f"{s['name']} ro'yxatdan o'chirildi", "warn")
    return {"ok": True}


@app.post("/api/admin/servers/{server_id}/command")
async def server_command(server_id: str, payload: dict, _=A):
    """Bitta serverga buyruq: sync_now | cache_clear | announce | reboot.

    `sync_now`dan tashqari hammasi NAVBATGA tushadi (server offlayn bo'lsa yoki
    `apply_at` berilса) — ya'ni bosilgan tugma yo'qolmaydi."""
    kind = str(payload.get("kind") or "")
    if kind not in ("sync_now", "cache_clear", "announce", "reboot"):
        raise HTTPException(400, "noma'lum buyruq")
    srv = db.get_server(server_id)
    if not srv:
        raise HTTPException(404, "server topilmadi")
    if kind == "sync_now":
        # Sinxronizatsiyani navbatga qo'yish keraksiz — server ulanганда
        # `on_register` allaqachon manifestni oladi.
        if not await relay.push_manifest(server_id):
            raise HTTPException(409, "server offlayn — ulanganda o'zi sinxronlanadi")
        return {"ok": True, "queued": False}
    extra = {}
    label = {"cache_clear": "Kesh tozalash", "reboot": "Qayta ishga tushirish"}.get(kind, kind)
    if kind == "announce":
        extra["text"] = str(payload.get("text") or "")[:300]
        if not extra["text"]:
            raise HTTPException(400, "e'lon matni kerak")
        label = f"E'lon: {extra['text'][:40]}"
    r = await _send_or_queue(server_id, kind, extra, label,
                             _parse_apply_at(payload.get("apply_at")))
    db.add_event(f"{srv['name']} — {label}" +
                 (" (navbatда)" if r["queued"] else ""), "info")
    return r


def _parse_apply_at(v):
    """"2026-08-05T03:00" / "2026-08-05 03:00" -> "2026-08-05 03:00:00".
    Bo'sh yoki noto'g'ri bo'lsa None (= imkon bo'lishi bilan)."""
    s = str(v or "").strip().replace("T", " ")
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    raise HTTPException(400, "vaqt formati noto'g'ri (YYYY-MM-DD HH:MM)")


async def _send_or_queue(server_id, kind, fields, label, apply_at=None):
    """Buyruqni YUBORADI yoki navbatga qo'yadi.

    Uch holat bor va uchtasi ham ma'lumotni yo'qotmaydi:
      * reja berilgan       -> navbatда turadi, vaqti kelganda ketadi;
      * server offlayn      -> navbatда turadi, ulangan zahoti ketadi;
      * onlayn va rejasiz   -> darhol yuboriladi.
    """
    if apply_at:
        op = db.queue_op(server_id, kind, fields, label, apply_at)
        return {"ok": True, "queued": True, "op_id": op, "apply_at": apply_at}
    if relay.is_online(server_id) and db.is_approved(server_id):
        if await relay.send_cmd(server_id, kind, **fields):
            return {"ok": True, "queued": False}
    op = db.queue_op(server_id, kind, fields, label, None)
    return {"ok": True, "queued": True, "op_id": op, "apply_at": None,
            "note": "server hozir offlayn — ulangan zahoti qo'llanadi"}


@app.post("/api/admin/servers/{server_id}/settings")
async def server_settings(server_id: str, payload: dict, _=A):
    """Serverning sozlamalarini MASOFADAN o'zgartiradi.

    Ruxsat etilgan kalitlar ro'yxati AGENT tomonida (`REMOTE_SETTINGS`) —
    bulut nimani yuborishidan qat'i nazar, server faqat o'zi ruxsat bergan
    kalitlarni yozadi. Ya'ni oq ro'yxat poyezd tomonida, ishonch chegarasida.

    `apply_at` berilса o'sha sana/vaqtdan keyin qo'llanadi; server offlayn
    bo'lsa xato QAYTARILMAYDI — navbatда turadi va ulanganda qo'llanadi."""
    srv = db.get_server(server_id)
    if not srv:
        raise HTTPException(404, "server topilmadi")
    values = payload.get("values")
    if not isinstance(values, dict) or not values:
        raise HTTPException(400, "values kerak")
    clean = {str(k)[:64]: ("" if v is None else str(v)[:2000])
             for k, v in list(values.items())[:60]}
    apply_at = _parse_apply_at(payload.get("apply_at"))
    r = await _send_or_queue(server_id, "set_settings", {"values": clean},
                             f"{len(clean)} sozlama: {', '.join(list(clean)[:4])}",
                             apply_at)
    db.add_event(
        f"{srv['name']} — sozlamalar " +
        (f"rejaga qo'yildi ({apply_at})" if apply_at
         else "navbatda (offlayn)" if r["queued"] else "o'zgartirildi") +
        f" · {len(clean)} maydon", "info")
    return {**r, "sent": list(clean)}


@app.get("/api/admin/servers/{server_id}/ops")
def server_ops(server_id: str, _=A):
    """Shu server uchun kutayotgan/rejalashtirilgan buyruqlar."""
    return db.get_pending_ops(server_id)


@app.delete("/api/admin/ops/{op_id}")
def op_cancel(op_id: int, _=A):
    db.cancel_op(op_id)
    return {"ok": True}


@app.post("/api/admin/servers/{server_id}/web")
async def server_web(server_id: str, payload: dict, _=A):
    """Veb ilovani (poyezd.uz) masofadan yoqadi/o'chiradi (navbatга tushadi)."""
    action = str(payload.get("action") or "")
    if action not in ("start", "stop"):
        raise HTTPException(400, "action = start | stop")
    srv = db.get_server(server_id)
    if not srv:
        raise HTTPException(404, "server topilmadi")
    r = await _send_or_queue(
        server_id, "web", {"action": action},
        "Veb ilova: " + ("yoqish" if action == "start" else "o'chirish"),
        _parse_apply_at(payload.get("apply_at")))
    db.add_event(f"{srv['name']} — veb ilova "
                 f"{'yoqildi' if action == 'start' else 'ochirildi'}" +
                 (" (navbatда)" if r["queued"] else ""), "info")
    return r


@app.post("/api/admin/servers/{server_id}/kiosk")
async def server_kiosk(server_id: str, payload: dict, _=A):
    """Bitta kioskка buyruq: sync | cache_clear | cache_on | cache_off | forget.
    Server offlayn bo'lsa navbatда turadi va ulanganda qo'llanadi."""
    action = str(payload.get("action") or "")
    device_id = str(payload.get("device_id") or "").strip()
    if action not in ("sync", "cache_clear", "cache_on", "cache_off", "forget"):
        raise HTTPException(400, "noma'lum kiosk buyrug'i")
    if not device_id:
        raise HTTPException(400, "device_id kerak")
    if not db.get_server(server_id):
        raise HTTPException(404, "server topilmadi")
    r = await _send_or_queue(server_id, "kiosk",
                             {"device_id": device_id, "action": action},
                             f"Kiosk {device_id}: {action}",
                             _parse_apply_at(payload.get("apply_at")))
    if action == "forget":
        db.forget_kiosk(server_id, device_id)
    db.add_event(f"Kiosk {device_id}: {action} (bulutdan)" +
                 (" — navbatда" if r["queued"] else ""), "info")
    return r


@app.post("/api/admin/servers/{server_id}/license")
async def server_license(server_id: str, payload: dict, _=A):
    """Litsenziya boshqaruvi: fayl yuborish yoki kiosklarni bloklash/ochish.

        {"text": "<license.key mazmuni>"}   -> faylni serverга o'rnatadi
        {"blocked": true|false}            -> kiosklarni bloklaydi/ochadi
    """
    srv = db.get_server(server_id)
    if not srv:
        raise HTTPException(404, "server topilmadi")
    apply_at = _parse_apply_at(payload.get("apply_at"))
    if "blocked" in payload:
        want = "1" if payload["blocked"] else "0"
        r = await _send_or_queue(
            server_id, "set_settings", {"values": {"trial_blocked": want}},
            "Kiosklarni " + ("BLOKLASH" if want == "1" else "blokdan chiqarish"),
            apply_at)
        db.add_event(f"{srv['name']} — kiosklar "
                     f"{'bloklandi' if want == '1' else 'blokdan chiqarildi'}",
                     "warn" if want == "1" else "ok")
        return r
    text = str(payload.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "license.key mazmuni yoki blocked kerak")
    if len(text) > 20000:
        raise HTTPException(400, "fayl juda katta")
    r = await _send_or_queue(server_id, "set_license", {"text": text},
                             "Litsenziya fayli", apply_at)
    db.add_event(f"{srv['name']} — litsenziya fayli yuborildi", "info")
    return r


# ------------------------------------------------------------- kutubxona
@app.get("/api/admin/content")
def content_list(type: str = "", q: str = "", _=A):
    items = db.get_content(type or None, q or None)
    counts = db.content_deploy_counts()
    for it in items:
        it["deployed"] = counts.get(it["id"], 0)
    return items


@app.get("/api/admin/cover/{content_id}")
def admin_cover(content_id: int, request: Request, _=A):
    """Kutubxona kartochkasidagi muqova rasmi (panel uchun).

    `/dl/<token>` emas — u agentlar uchun. Panelда brauzer sessiya cookie'sini
    o'zi yuboradi (`<img src>` ham), shuning uchun oddiy sessiya yetarli."""
    c = db.get_content_by_id(content_id)
    if not c or not c.get("cover_sha"):
        raise HTTPException(404, "muqova yo'q")
    p = storage.blob_path(c["cover_sha"])
    if not p or not os.path.isfile(p):
        raise HTTPException(404, "fayl topilmadi")
    return storage.range_response(p, request, filename=c.get("cover_name"))


@app.put("/api/admin/blob")
async def blob_upload(request: Request, name: str = Query(""), _=A):
    """Faylni omborga yozadi va sha256 qaytaradi (multipart YO'Q — xom tana).

    Katta kino uchun ataylab shunday: xotirada bufer yo'q, brauzer XHR bilan
    progress ko'rsatadi, `python-multipart` bog'liqligi ham kerak emas."""
    try:
        sha, size, dedup = await storage.save_upload(request)
    except ValueError as e:
        raise HTTPException(413 if "katta" in str(e) else 400, str(e))
    return {"sha256": sha, "size": size, "name": name, "dedup": dedup}


@app.post("/api/admin/content")
def content_create(payload: dict, _=A):
    """Yuklangan bloblardan kutubxona yozuvi yasaydi."""
    ctype = str(payload.get("type") or "")
    if ctype not in db.CONTENT_TYPES:
        raise HTTPException(400, f"turi noto'g'ri: {ctype}")
    title = str(payload.get("title") or "").strip()
    if not title:
        raise HTTPException(400, "sarlavha kerak")

    data = {"type": ctype, "title": title[:200]}
    for k in ("author", "genre", "description", "category_tab"):
        if payload.get(k):
            data[k] = str(payload[k])[:1000]
    lang = str(payload.get("lang") or "").strip()
    data["lang"] = lang if lang in ("uz", "ru", "en") else None
    for k in ("duration", "pages"):
        if payload.get(k) is not None:
            data[k] = db.to_int(payload.get(k))
    data["is_recommended"] = 1 if payload.get("is_recommended") else 0
    data["cache_enabled"] = 0 if payload.get("cache_enabled") is False else 1
    # visible=0 — kontent serverga boradi, lekin kioskda ko'rinmaydi (oldindan
    # tayyorlab qo'yish uchun: fayl joyida, keyin bir tugma bilan yoqiladi)
    data["visible"] = 0 if payload.get("visible") is False else 1

    for part, pre in (("media", "media"), ("cover", "cover"), ("text", "text")):
        p = payload.get(part)
        if not isinstance(p, dict) or not p.get("sha256"):
            continue
        sha = str(p["sha256"])
        if not storage.exists(sha):
            raise HTTPException(400, f"{part}: blob topilmadi (avval yuklang)")
        data[f"{pre}_sha"] = sha
        data[f"{pre}_name"] = str(p.get("name") or "")[:200]
        data[f"{pre}_size"] = storage.size_of(sha)

    if not data.get("media_sha") and not data.get("text_sha"):
        raise HTTPException(400, "media yoki matn fayli kerak")

    cid = db.add_content(data)
    db.add_event(f"Kutubxonaga qo'shildi: {title}", "info")
    return {"id": cid}


@app.patch("/api/admin/content/{content_id}")
def content_patch(content_id: int, payload: dict, _=A):
    """Kontentni tahrirlaydi: metadata VA fayllar (media/muqova/matn).

    Fayl maydonlari uch xil bo'lishi mumkin:
      - berilmagan          -> tegilmaydi (eski fayl qoladi)
      - {"sha256","name"}   -> almashtiriladi (avval blob yuklangan bo'lishi kerak)
      - null                -> olib tashlanadi

    O'zgarishdan keyin shu kontent bor serverlarning `desired_rev`i oshadi —
    ular manifestni qayta oladi va yangi faylni tortadi / eskisini o'chiradi.
    """
    item = db.get_content_by_id(content_id)
    if not item:
        raise HTTPException(404, "kontent topilmadi")

    clean = {}
    if payload.get("type") in db.CONTENT_TYPES:
        clean["type"] = payload["type"]
    if "title" in payload:
        title = str(payload["title"] or "").strip()
        if not title:
            raise HTTPException(400, "sarlavha bo'sh bo'lmaydi")
        clean["title"] = title[:200]
    for k in ("author", "genre", "description", "category_tab"):
        if k in payload:
            clean[k] = (str(payload[k])[:1000] if payload[k] is not None else None)
    if "lang" in payload:
        lang = str(payload["lang"] or "").strip()
        clean["lang"] = lang if lang in ("uz", "ru", "en") else None
    for k in ("duration", "pages", "is_recommended", "cache_enabled", "visible"):
        if k in payload:
            clean[k] = db.to_int(payload[k])

    # --- fayllar
    for part, pre in (("media", "media"), ("cover", "cover"), ("text", "text")):
        if part not in payload:
            continue
        p = payload[part]
        if p is None:
            clean[f"{pre}_sha"] = None
            clean[f"{pre}_name"] = None
            clean[f"{pre}_size"] = 0
        elif isinstance(p, dict) and p.get("sha256"):
            sha = str(p["sha256"])
            if not storage.exists(sha):
                raise HTTPException(400, f"{part}: blob topilmadi (avval yuklang)")
            clean[f"{pre}_sha"] = sha
            clean[f"{pre}_name"] = str(p.get("name") or "")[:200]
            clean[f"{pre}_size"] = storage.size_of(sha)

    # Kontent butunlay fayldan ayrilib qolmasin (kioskda ochilmaydigan yozuv
    # bo'lib qolardi) — yozishdan OLDIN tekshiramiz.
    after_media = clean.get("media_sha", item["media_sha"]) if "media_sha" in clean \
        else item["media_sha"]
    after_text = clean.get("text_sha", item["text_sha"]) if "text_sha" in clean \
        else item["text_sha"]
    if not after_media and not after_text:
        raise HTTPException(400, "media yoki matn fayli qolishi kerak")

    if not clean:
        return {"ok": True, "servers_to_sync": 0}

    db.update_content(content_id, clean)
    # Tayinlangan serverlarда metadata/fayl ham yangilanishi kerak
    sids = db.servers_with_content(content_id)
    db.bump_rev(sids)
    # Almashtirilgan fayldan qolgan yetim blobni tozalaymiz
    storage.gc(db.shas_in_use())
    db.add_event(f"Tahrirlandi: {clean.get('title') or item['title']}", "info")
    return {"ok": True, "servers_to_sync": len(sids)}


@app.delete("/api/admin/content/{content_id}")
async def content_delete(content_id: int, _=A):
    """Kutubxonadan o'chiradi VA barcha serverlardan olib tashlaydi."""
    item = db.get_content_by_id(content_id)
    if not item:
        raise HTTPException(404, "kontent topilmadi")
    sids = db.unassign_everywhere([content_id])
    db.delete_content(content_id)
    storage.gc(db.shas_in_use())
    if sids:
        job = db.create_job("remove", f"O'chirish: {item['title']}", sids,
                            [], {"content_ids": [content_id]})
        await relay.dispatch_job(job, sids)
    db.add_event(f"Kutubxonadan o'chirildi: {item['title']}", "warn")
    return {"ok": True, "servers": len(sids)}


@app.get("/api/admin/storage")
def storage_usage(_=A):
    n, used, free = storage.usage()
    return {"files": n, "used": used, "free": free}


# =====================================================================
#  Reklama · Saytlar · Bekatlar (kontent bilan bir xil desired-state)
# =====================================================================
def _clean_placement(v):
    """Reklama joylashuvини normallashtiradi — kanallar to'plami (popup/banner/
    media) vergul bilan. Eski qiymatlar mos: 'both' → 'popup,banner'. Bo'sh yoki
    yaroqsiz → 'popup'."""
    s = str(v or "").strip().lower()
    if s == "both":
        return "popup,banner"
    parts = [p.strip() for p in s.split(",") if p.strip()]
    valid = [p for p in ("popup", "banner", "media") if p in parts]
    return ",".join(valid) if valid else "popup"


@app.get("/api/admin/ads")
def ads_list(_=A):
    return db.get_ads()


@app.post("/api/admin/ads")
def ad_create(payload: dict, _=A):
    """Reklama qo'shadi. Media (rasm yoki video) avval `/api/admin/blob` bilan
    yuklanadi va sha256 shu yerga beriladi."""
    data = {
        "title": str(payload.get("title") or "")[:200],
        "subtitle": str(payload.get("subtitle") or "")[:300],
        "link_url": str(payload.get("link_url") or "")[:500],
        "duration": db.to_int(payload.get("duration"), 10),
        "placement": _clean_placement(payload.get("placement")),
        "is_active": 0 if payload.get("is_active") is False else 1,
        "sort_order": db.to_int(payload.get("sort_order")),
    }
    for k in ("start_time", "end_time"):
        if payload.get(k):
            data[k] = str(payload[k])[:8]
    if payload.get("interval_min"):
        data["interval_min"] = db.to_int(payload["interval_min"])
    p = payload.get("media")
    if isinstance(p, dict) and p.get("sha256"):
        sha = str(p["sha256"])
        if not storage.exists(sha):
            raise HTTPException(400, "media blob topilmadi (avval yuklang)")
        data["media_sha"] = sha
        data["media_name"] = str(p.get("name") or "")[:200]
        data["media_size"] = storage.size_of(sha)
    if not data.get("media_sha"):
        raise HTTPException(400, "reklama uchun rasm yoki video kerak")
    aid = db.add_ad(data)
    db.add_event(f"Reklama qo'shildi: {data['title'] or aid}", "info")
    return {"id": aid}


@app.patch("/api/admin/ads/{ad_id}")
async def ad_patch(ad_id: int, payload: dict, _=A):
    if not db.get_ad_by_id(ad_id):
        raise HTTPException(404, "reklama topilmadi")
    clean = {}
    for k in ("title", "subtitle", "link_url"):
        if k in payload:
            clean[k] = str(payload[k] or "")[:500]
    for k in ("duration", "interval_min", "sort_order"):
        if k in payload:
            clean[k] = db.to_int(payload[k])
    for k in ("start_time", "end_time"):
        if k in payload:
            clean[k] = str(payload[k] or "")[:8] or None
    if "placement" in payload:
        clean["placement"] = _clean_placement(payload["placement"])
    if "is_active" in payload:
        clean["is_active"] = 1 if payload["is_active"] else 0
    p = payload.get("media")
    if isinstance(p, dict) and p.get("sha256"):
        sha = str(p["sha256"])
        if not storage.exists(sha):
            raise HTTPException(400, "media blob topilmadi")
        clean.update({"media_sha": sha,
                      "media_name": str(p.get("name") or "")[:200],
                      "media_size": storage.size_of(sha)})
    db.update_ad(ad_id, clean)
    sids = db.ad_servers(ad_id)
    db.bump_rev(sids)
    storage.gc(db.shas_in_use())
    for sid in sids:
        await relay.push_manifest(sid)
    return {"ok": True, "servers_to_sync": len(sids)}


@app.delete("/api/admin/ads/{ad_id}")
async def ad_delete(ad_id: int, _=A):
    a = db.get_ad_by_id(ad_id)
    if not a:
        raise HTTPException(404, "reklama topilmadi")
    sids = db.ad_servers(ad_id)
    db.delete_ad(ad_id)
    db.bump_rev(sids)
    storage.gc(db.shas_in_use())
    for sid in sids:
        await relay.push_manifest(sid)
    db.add_event(f"Reklama o'chirildi: {a['title'] or ad_id}", "warn")
    return {"ok": True, "servers": len(sids)}


@app.post("/api/admin/ads/{ad_id}/servers")
async def ad_assign(ad_id: int, payload: dict, _=A):
    """Reklamani serverlarga tayinlaydi (ro'yxatда yo'qlaridan olib tashlanadi)."""
    if not db.get_ad_by_id(ad_id):
        raise HTTPException(404, "reklama topilmadi")
    want = {str(s) for s in payload.get("server_ids") or []}
    known = {s["id"] for s in db.get_servers()}
    want &= known
    have = set(db.ad_servers(ad_id))
    add, drop = want - have, have - want
    if add:
        db.assign_ads(list(add), [ad_id])
    if drop:
        db.unassign_ads(list(drop), [ad_id])
    for sid in add | drop:
        await relay.push_manifest(sid)
    return {"ok": True, "added": len(add), "removed": len(drop)}


@app.get("/api/admin/ads/{ad_id}/media")
def ad_media(ad_id: int, request: Request, _=A):
    """Reklama faylini panelда ko'rsatish uchun (rasm yoki video)."""
    a = db.get_ad_by_id(ad_id)
    if not a or not a.get("media_sha"):
        raise HTTPException(404, "media yo'q")
    p = storage.blob_path(a["media_sha"])
    if not p or not os.path.isfile(p):
        raise HTTPException(404, "fayl topilmadi")
    return storage.range_response(p, request, filename=a.get("media_name"))


@app.get("/api/admin/sites")
def sites_list(_=A):
    return db.get_sites()


@app.post("/api/admin/sites")
async def site_create(payload: dict, _=A):
    """Sayt qo'shadi. Saytlar ro'yxati BARCHA serverlarga bir xil ketadi."""
    name = str(payload.get("name") or "").strip()
    url = str(payload.get("url") or "").strip()
    if not name or not url:
        raise HTTPException(400, "nom va URL kerak")
    sid = db.add_site({
        "name": name[:120], "url": url[:500],
        "description": str(payload.get("description") or "")[:1000],
        "features": str(payload.get("features") or "")[:1000],
        "icon": str(payload.get("icon") or "")[:64],
        "sort_order": db.to_int(payload.get("sort_order")),
    })
    await _push_all()
    db.add_event(f"Sayt qo'shildi: {name}", "info")
    return {"id": sid}


@app.patch("/api/admin/sites/{site_id}")
async def site_patch(site_id: int, payload: dict, _=A):
    clean = {}
    for k in ("name", "url", "description", "features", "icon"):
        if k in payload:
            clean[k] = str(payload[k] or "")[:1000]
    if "sort_order" in payload:
        clean["sort_order"] = db.to_int(payload["sort_order"])
    db.update_site(site_id, clean)
    await _push_all()
    return {"ok": True}


@app.delete("/api/admin/sites/{site_id}")
async def site_delete(site_id: int, _=A):
    db.delete_site(site_id)
    await _push_all()
    return {"ok": True}


BRANDING_MAX = 5   # bitta turdagi bannerlar kutubxonasining chegarasi


def _branding_full(kind, sha=None, vertical=None):
    """Kutubxona to'lganmi. Limit VERTIKAL bo'yicha (poyezd/avtobus alohida
    kutubxona). `sha` allaqachon bor bo'lsa — to'la emas (qayta tanlash mumkin)."""
    rows = db.lib_list(kind, vertical)
    if sha and any(r.get("sha") == sha for r in rows):
        return False
    return len(rows) >= BRANDING_MAX


@app.get("/api/admin/branding/library")
def branding_library(kind: str = "hero", vertical: str | None = None, _=A):
    """Yuklangan bannerlar ro'yxati. `vertical` (poyezd/avtobus) berilса —
    faqat o'sha turdagilar (poyezd rasmlari avtobusда ko'rinmaydi)."""
    if kind not in db.BRANDING_KINDS:
        raise HTTPException(400, f"noma'lum tur: {kind}")
    return db.lib_list(kind, vertical)


@app.post("/api/admin/branding/library")
def branding_library_add(payload: dict, _=A):
    """Kutubxonaga yangi banner qo'shadi (fayl avval `/blob` bilan yuklanadi).
    Rasm SAQLANIB TURADI — keyin xohlagan serverga tanlab qo'yiladi."""
    kind = str(payload.get("kind") or "hero")
    if kind not in db.BRANDING_KINDS:
        raise HTTPException(400, f"noma'lum tur: {kind}")
    p = payload.get("media")
    if not isinstance(p, dict) or not p.get("sha256"):
        raise HTTPException(400, "media.sha256 kerak")
    sha = str(p["sha256"])
    if not storage.exists(sha):
        raise HTTPException(400, "blob topilmadi (avval yuklang)")
    vertical = str(payload.get("vertical") or "train").strip().lower()
    if _branding_full(kind, sha, vertical):
        raise HTTPException(400, f"Eng ko'pi {BRANDING_MAX} ta banner — "
                                 "avval bittasini o'chiring")
    lid = db.lib_add(kind, sha, str(p.get("name") or "")[:200],
                     storage.size_of(sha), vertical)
    return {"id": lid}


@app.delete("/api/admin/branding/library/{lib_id}")
async def branding_library_del(lib_id: int, _=A):
    """Kutubxonadan o'chiradi. Shu banner faol bo'lgan serverlar standart
    rasmga qaytadi va yangi manifest oladi."""
    srv = db.lib_delete(lib_id)
    for sid in srv:
        await relay.push_manifest(sid)
    storage.gc(db.shas_in_use())
    return {"ok": True, "servers": len(srv)}


@app.get("/api/admin/branding/library/{lib_id}/image")
def branding_library_img(lib_id: int, request: Request, _=A):
    row = db.lib_get(lib_id)
    if not row:
        raise HTTPException(404, "topilmadi")
    p = storage.blob_path(row["sha"])
    if not p or not os.path.isfile(p):
        raise HTTPException(404, "fayl topilmadi")
    return storage.range_response(p, request, filename=row.get("name"))


@app.put("/api/admin/servers/{server_id}/branding")
async def branding_set(server_id: str, payload: dict, _=A):
    """Shu server uchun QAYSI banner faol bo'lishini belgilaydi.

        {"kind":"hero","library_id":3}                 -> kutubxonadan tanlaydi
        {"kind":"hero","media":{"sha256":…,"name":…}}   -> to'g'ridan-to'g'ri
        {"kind":"hero","media":null}                    -> standart rasmga qaytaradi
    """
    srv = db.get_server(server_id)
    if not srv:
        raise HTTPException(404, "server topilmadi")
    vertical = srv.get("vertical") or "train"
    kind = str(payload.get("kind") or "hero")
    if kind not in db.BRANDING_KINDS:
        raise HTTPException(400, f"noma'lum tur: {kind}")

    lib_id = payload.get("library_id")
    cleared = False
    if lib_id:
        try:
            lib_id = int(lib_id)
        except (TypeError, ValueError):
            raise HTTPException(400, "library_id noto'g'ri")
        row = db.lib_get(lib_id)
        if not row or row["kind"] != kind:
            raise HTTPException(404, "kutubxonada topilmadi")
        db.set_branding(server_id, kind, row["sha"], row["name"], row["size"])
    elif payload.get("media") is None:
        db.clear_branding(server_id, kind)
        cleared = True
    else:
        p = payload["media"]
        if not isinstance(p, dict) or not p.get("sha256"):
            raise HTTPException(400, "media.sha256 kerak")
        sha = str(p["sha256"])
        if not storage.exists(sha):
            raise HTTPException(400, "blob topilmadi (avval yuklang)")
        if _branding_full(kind, sha, vertical):
            raise HTTPException(400, f"Eng ko'pi {BRANDING_MAX} ta banner — "
                                     "avval bittasini o'chiring")
        name = str(p.get("name") or "")[:200]
        db.lib_add(kind, sha, name, storage.size_of(sha), vertical)  # kutubxonaga ham
        db.set_branding(server_id, kind, sha, name, storage.size_of(sha))
    await relay.push_manifest(server_id)
    storage.gc(db.shas_in_use())
    db.add_event(f"{db.get_server(server_id)['name']} — banner "
                 f"{'standartga qaytarildi' if cleared else 'almashtirildi'}",
                 "info")
    return {"ok": True}


@app.get("/api/admin/servers/{server_id}/branding/{kind}")
def branding_get(server_id: str, kind: str, request: Request, _=A):
    """Panelда joriy brending rasmini ko'rsatish uchun."""
    row = next((b for b in db.get_branding(server_id) if b["kind"] == kind), None)
    if not row:
        raise HTTPException(404, "brending yo'q")
    p = storage.blob_path(row["sha"])
    if not p or not os.path.isfile(p):
        raise HTTPException(404, "fayl topilmadi")
    return storage.range_response(p, request, filename=row.get("name"))


@app.get("/api/admin/servers/{server_id}/stops")
def stops_list(server_id: str, _=A):
    return db.get_stops(server_id)


@app.put("/api/admin/servers/{server_id}/stops")
async def stops_replace(server_id: str, payload: dict, _=A):
    """Bekatlar jadvalini to'liq almashtiradi (har server uchun alohida).

    Jadval odatda to'liq qayta kiritiladi — bittalab tahrirlashdan ko'ra
    butun ro'yxatni yuborish ancha qulay va xatoga kam joy qoldiradi."""
    if not db.get_server(server_id):
        raise HTTPException(404, "server topilmadi")
    stops = payload.get("stops")
    if not isinstance(stops, list):
        raise HTTPException(400, "stops ro'yxati kerak")
    n = db.replace_stops(server_id, stops)
    await relay.push_manifest(server_id)
    db.add_event(f"{db.get_server(server_id)['name']} — bekatlar yangilandi "
                 f"({n} ta)", "info")
    return {"ok": True, "n": n}


async def _push_all():
    """Barcha onlayn serverlarga manifest (saytlar hammaga tegishli)."""
    for s in db.get_servers():
        if relay.is_online(s["id"]):
            await relay.push_manifest(s["id"])


# --------------------------------------------------------------- tarqatish
@app.post("/api/admin/deploy")
async def deploy(payload: dict, _=A):
    """Kontentni serverlarga tarqatadi (desired state + ish yaratiladi)."""
    cids = [int(i) for i in payload.get("content_ids") or [] if str(i).isdigit()]
    sids = [str(s) for s in payload.get("server_ids") or []]
    if not cids or not sids:
        raise HTTPException(400, "content_ids va server_ids kerak")
    known = {s["id"] for s in db.get_servers()}
    sids = [s for s in sids if s in known]
    if not sids:
        raise HTTPException(400, "server topilmadi")
    items = [db.get_content_by_id(i) for i in cids]
    if any(i is None for i in items):
        raise HTTPException(400, "kontent topilmadi")

    apply_at = _parse_apply_at(payload.get("apply_at"))
    title = (items[0]["title"] if len(items) == 1
             else f"{len(items)} fayl tarqatilmoqda")
    job = db.create_job("deploy", title, sids, cids, {
        "skip_existing": bool(payload.get("skip_existing", True)),
        "apply_at": apply_at,
    })

    if apply_at:
        # REJALASHTIRILGAN tarqatish: tayinlov HOZIR qo'yilmaydi (aks holda
        # heartbeat farqni ko'rib darhol tortib olardi). Vaqti kelganda
        # `_ops_loop` tayinlab, manifestni yuboradi.
        for sid in sids:
            db.queue_op(sid, "deploy_apply",
                        {"content_ids": cids, "job_id": job},
                        f"Tarqatish: {title}", apply_at)
            db.set_target(job, sid, state="queued")
        db.add_event(f"Tarqatish rejaga qo'yildi ({apply_at}): {title} → "
                     f"{len(sids)} server", "info")
        return {"job_id": job, "servers": len(sids), "queued": len(sids),
                "apply_at": apply_at}

    db.assign(sids, cids)
    await relay.dispatch_job(job, sids)
    offline = [s for s in sids if not relay.is_online(s)]
    db.add_event(f"Tarqatish boshlandi: {title} → {len(sids)} server", "info")
    return {"job_id": job, "servers": len(sids), "queued": len(offline),
            "apply_at": None}


@app.post("/api/admin/remove")
async def remove_from_servers(payload: dict, _=A):
    """Kontentni tanlangan serverlardan o'chiradi (kutubxonada qoladi)."""
    cids = [int(i) for i in payload.get("content_ids") or [] if str(i).isdigit()]
    sids = [str(s) for s in payload.get("server_ids") or []]
    if not cids:
        raise HTTPException(400, "content_ids kerak")
    if not sids:                       # berilmasa — hammasidan
        sids = sorted({s for c in cids for s in db.servers_with_content(c)})
    if not sids:
        return {"job_id": None, "servers": 0}
    db.unassign(sids, cids)
    job = db.create_job("remove", f"{len(cids)} fayl o'chirilmoqda", sids, cids)
    await relay.dispatch_job(job, sids)
    db.add_event(f"O'chirish: {len(cids)} fayl → {len(sids)} server", "warn")
    return {"job_id": job, "servers": len(sids)}


@app.get("/api/admin/jobs")
def jobs_list(active: int = 0, _=A):
    return db.get_jobs(limit=40, active_only=bool(active))


@app.post("/api/admin/jobs/{job_id}/cancel")
def job_cancel(job_id: int, _=A):
    db.cancel_job(job_id)
    return {"ok": True}


@app.post("/api/admin/jobs/{job_id}/retry")
async def job_retry(job_id: int, _=A):
    """Xato bo'lgan nishonlarni qaytadan urinadi (masalan disk to'lgan yoki
    litsenziya muddati tugagan bo'lsa — muammo hal bo'lgach)."""
    sids = db.retry_job(job_id)
    if not sids:
        raise HTTPException(400, "qayta urinish uchun xato nishon yo'q")
    await relay.dispatch_job(job_id, sids)
    db.add_event(f"Ish #{job_id} qayta urinildi ({len(sids)} obyekt)", "info")
    return {"ok": True, "servers": len(sids)}


@app.post("/api/admin/sync-all")
async def sync_all(_=A):
    """Barcha onlayn serverlarga manifest yuboradi (qo'lда "hammasini tekshir")."""
    n = 0
    for s in db.get_servers():
        if relay.is_online(s["id"]):
            if await relay.push_manifest(s["id"]):
                n += 1
    return {"sent": n}


# ------------------------------------------------------- statistika/loglar
@app.get("/api/admin/stats")
def stats(days: int = 14, server_id: str = "", source: str = "", _=A):
    """Yig'ma statistika. `source` = kiosk | web | "" (ikkisi ham).

    `sync` bo'limi — serverlarda hali yuborilmagan eventlar (panel "hammasi
    tortib olindimi" degan savolga javob beradi)."""
    days = max(1, min(int(days), 90))
    sid = server_id or None
    src = source if source in ("kiosk", "web") else None
    servers = db.get_servers()
    return {
        "totals": db.stats_totals(days, sid, src),
        "daily": db.stats_daily(days, sid, src),
        "top_content": db.stats_top_content(days, 8, sid, src),
        "top_ads": db.stats_top_ads(days, 8, sid, src),
        "top_servers": db.stats_top_servers(days, 8),
        "by_source": db.stats_by_source(days, sid),
        "devices": db.stats_by_device(days, sid, src, 20),
        # Boyitilган analitika (donut/ro'yxat/soat)
        "ads_placement": db.stats_ads_placement(days, sid, src),
        "content_types": db.stats_content_types(days, sid, src),
        "langs": db.stats_langs(days, sid, src),
        "screens": db.stats_screens(days, sid, src, 8),
        "sites": db.stats_sites(days, sid, src, 8),
        "event_mix": db.stats_event_mix(days, sid, src),
        "session_avg": db.stats_session_avg(days, sid, src),
        "hourly": db.stats_hourly(days, sid, src),
        "sync": {
            "pending": sum(s.get("stats_pending", 0) or 0 for s in servers),
            "server_total": sum(s.get("stats_total", 0) or 0 for s in servers),
            "servers": [{"id": s["id"], "name": s["name"],
                         "pending": s.get("stats_pending", 0) or 0,
                         "total": s.get("stats_total", 0) or 0,
                         "online": relay.is_online(s["id"]) or db.is_online(s)}
                        for s in servers if (s.get("stats_pending") or 0) > 0],
        },
    }


@app.post("/api/admin/stats/reset")
def stats_reset(_=A):
    """Bulutdagi statistikани 0 ga tushiradi (0 dan test qilish uchun)."""
    n = db.clear_stats()
    db.add_event(f"Statistika tozalandi ({n} event o'chirildi)", "info")
    return {"ok": True, "deleted": n}


@app.get("/api/admin/logs")
def logs(server_id: str = "", level: str = "", q: str = "", limit: int = 200,
         _=A):
    return db.get_logs(server_id or None, level or None, q or None, limit)


# ---------------------------------------------------------- enroll tokenlar
@app.get("/api/admin/enroll-tokens")
def enroll_tokens(_=A):
    return db.get_enroll_tokens()


@app.post("/api/admin/enroll-tokens")
def enroll_token_new(payload: dict, _=A):
    """Yangi bir martalik token. Javobда OCHIQ MATN faqat SHU MARTA keladi —
    bazada xesh saqlanadi."""
    label = str(payload.get("label") or "").strip()[:120]
    route = str(payload.get("route") or "").strip()[:160]
    if not label:
        raise HTTPException(400, "server nomi (label) kerak")
    token = db.create_enroll_token(label, route)
    return {"token": token, "label": label, "route": route}


@app.delete("/api/admin/enroll-tokens/{token_id}")
def enroll_token_delete(token_id: int, _=A):
    db.delete_enroll_token(token_id)
    return {"ok": True}


# =====================================================================
#  Statik panel
# =====================================================================
@app.get("/")
def index():
    p = os.path.join(STATIC_DIR, "index.html")
    if not os.path.isfile(p):
        return Response("static/index.html topilmadi", status_code=500)
    # Statik fayllarga build versiyasini qo'shamiz — yangi build chiqqanda
    # brauzer eski keshdagi app.js/styles.css'ni bermasin (aks holda panel
    # yangilanмайди va "eski UI" muammosi bo'ladi).
    with open(p, "r", encoding="utf-8") as f:
        html = f.read()
    html = (html.replace("/static/styles.css", f"/static/styles.css?v={APP_BUILD}")
                .replace("/static/app.js", f"/static/app.js?v={APP_BUILD}"))
    return Response(html, media_type="text/html",
                    headers={"Cache-Control": "no-cache"})


if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _port_busy(port, host="127.0.0.1"):
    """Port allaqachon band bo'lsa True. Uvicorn'ning WinError 10048 xatosi
    tushunarsiz — shuning uchun oldindan tekshirib aniq xabar beramiz."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.6)
        return s.connect_ex((host, port)) == 0


if __name__ == "__main__":
    import sys

    import uvicorn
    _setup_logging()
    if _port_busy(config.PORT):
        print(f"\n  {config.PORT}-port allaqachon band — bulut SHU MASHINADA "
              f"ishlab turgan bo'lishi mumkin.\n"
              f"  Tekshirish:  http://127.0.0.1:{config.PORT}\n"
              f"  Kim egallagan (PowerShell):\n"
              f"    Get-NetTCPConnection -LocalPort {config.PORT} -State Listen |"
              f" Select-Object OwningProcess\n"
              f"  To'xtatish:  Stop-Process -Id <PID> -Force\n"
              f"  Yoki boshqa portda:  CLOUD_PORT=9001 py main.py\n",
              file=sys.stderr)
        sys.exit(1)
    kw = {}
    if config.USE_TLS:
        kw = {"ssl_certfile": config.TLS_CERT, "ssl_keyfile": config.TLS_KEY}
    uvicorn.run("main:app", host=config.HOST, port=config.PORT,
                log_level="warning", **kw)
