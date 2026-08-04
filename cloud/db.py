"""
db.py — Bulut bazasi (SQLite). Uslub `server/db.py` bilan bir xil: WAL,
kontekst-menejer tranzaksiya, generik helperlar.

Asosiy g'oya — **desired state**: qaysi serverda qanday kontent bo'lishi
kerakligini bulut belgilaydi (`assignments`), har o'zgarishda o'sha serverning
`desired_rev` raqami oshadi. Agent heartbeatда o'z `applied_rev`ini aytadi;
farq bo'lsa bulut to'liq manifest yuboradi. Shu bilan "yuklash" va "o'chirish"
bitta mexanizmga aylanadi.
"""
import os
import json
import hmac
import hashlib
import logging
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta

import config

log = logging.getLogger("cloud.db")

# Kontent turlari — server/db.py bilan AYNAN bir xil bo'lishi shart (tarqatilgan
# yozuv poyezd serverida shu turda saqlanadi).
CONTENT_TYPES = ("movie", "cartoon", "music", "book", "audiobook")

LOG_LEVELS = ("INFO", "WARN", "ERROR")


def connect():
    conn = sqlite3.connect(config.DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def _conn():
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


SCHEMA = """
-- Poyezd serverlari (agentlar). id — enroll paytida beriladi.
CREATE TABLE IF NOT EXISTS servers (
    id            TEXT PRIMARY KEY,        -- srv_xxxxxxxx
    name          TEXT NOT NULL,           -- "Poyezd 076Ф"
    route         TEXT,                    -- "Toshkent → Xiva"
    note          TEXT,
    token_hash    TEXT NOT NULL,           -- server_token (pbkdf2)
    hw_id         TEXT,                    -- qurilma barmoq izi (enroll)
    version       TEXT,                    -- server ilova versiyasi
    kiosks_total  INTEGER DEFAULT 0,
    kiosks_online INTEGER DEFAULT 0,
    disk_total    INTEGER DEFAULT 0,
    disk_free     INTEGER DEFAULT 0,
    license       TEXT,                    -- active | trial | expired | blocked
    license_note  TEXT,
    desired_rev   INTEGER DEFAULT 0,       -- bulut belgilagan holat versiyasi
    applied_rev   INTEGER DEFAULT 0,       -- server tasdiqlagan versiya
    queue_active  INTEGER DEFAULT 0,
    queue_pending INTEGER DEFAULT 0,
    stats_pending INTEGER DEFAULT 0,        -- bulutga yuborilmagan eventlar
    stats_total   INTEGER DEFAULT 0,        -- serverdagi jami eventlar
    web_running   INTEGER DEFAULT 0,        -- veb ilova (poyezd.uz) ishlayaptimi
    settings      TEXT,                     -- serverning joriy sozlamalari (JSON)
    -- 0 = o'zi ro'yxatga turgan, admin TASDIQLAMAGAN. Tasdiqlanmagan serverga
    -- manifest ham, buyruq ham yuborilmaydi (faqat ro'yxatda ko'rinadi).
    approved      INTEGER DEFAULT 1,
    enrolled_at   TEXT DEFAULT (datetime('now')),
    last_seen     TEXT
);

-- Har bir serverning kiosklari (server heartbeatда yuboradi)
CREATE TABLE IF NOT EXISTS server_kiosks (
    server_id  TEXT NOT NULL,
    device_id  TEXT NOT NULL,
    kiosk_no   TEXT,
    room       TEXT,
    ip         TEXT,
    platform   TEXT,
    cached_n   INTEGER DEFAULT 0,
    disk_total INTEGER DEFAULT 0,
    disk_free  INTEGER DEFAULT 0,
    online     INTEGER DEFAULT 0,
    last_seen  TEXT,
    PRIMARY KEY (server_id, device_id),
    FOREIGN KEY (server_id) REFERENCES servers(id) ON DELETE CASCADE
);

-- Bulut kutubxonasi: kontent MANBASI (fayllar storage/ da sha256 bo'yicha).
CREATE TABLE IF NOT EXISTS content (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    type           TEXT NOT NULL,
    title          TEXT NOT NULL,
    author         TEXT,
    genre          TEXT,
    description    TEXT,
    duration       INTEGER,
    pages          INTEGER,
    lang           TEXT,                   -- uz|ru|en; NULL = barcha tillarda
    category_tab   TEXT,
    is_recommended INTEGER DEFAULT 0,
    cache_enabled  INTEGER DEFAULT 1,
    visible        INTEGER DEFAULT 1,      -- 0 = kioskda umuman ko'rinmaydi
    media_sha      TEXT, media_name TEXT, media_size INTEGER DEFAULT 0,
    cover_sha      TEXT, cover_name TEXT, cover_size INTEGER DEFAULT 0,
    text_sha       TEXT, text_name  TEXT, text_size  INTEGER DEFAULT 0,
    created_at     TEXT DEFAULT (datetime('now'))
);

-- Desired state: shu serverda shu kontent BO'LISHI KERAK
CREATE TABLE IF NOT EXISTS assignments (
    server_id  TEXT NOT NULL,
    content_id INTEGER NOT NULL,
    added_at   TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (server_id, content_id),
    FOREIGN KEY (server_id) REFERENCES servers(id) ON DELETE CASCADE,
    FOREIGN KEY (content_id) REFERENCES content(id) ON DELETE CASCADE
);

-- Tarqatish/buyruq ishlari
CREATE TABLE IF NOT EXISTS jobs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    kind       TEXT NOT NULL,              -- deploy|remove|announce|cache_clear|sync
    title      TEXT,
    opts       TEXT,                       -- JSON (skip_existing, night_window, matn...)
    state      TEXT DEFAULT 'running',     -- running|done|error|cancelled
    created_at TEXT DEFAULT (datetime('now')),
    done_at    TEXT
);

CREATE TABLE IF NOT EXISTS job_items (
    job_id     INTEGER NOT NULL,
    content_id INTEGER NOT NULL,
    PRIMARY KEY (job_id, content_id),
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS job_targets (
    job_id      INTEGER NOT NULL,
    server_id   TEXT NOT NULL,
    state       TEXT DEFAULT 'pending',    -- pending|queued|running|done|error
    pct         INTEGER DEFAULT 0,
    bytes_done  INTEGER DEFAULT 0,
    bytes_total INTEGER DEFAULT 0,
    error       TEXT,
    updated_at  TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (job_id, server_id),
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
);

-- Kiosklardan yig'ilgan foydalanish statistikasi (server batch qilib yuboradi)
CREATE TABLE IF NOT EXISTS stats_events (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    server_id TEXT,
    device_id TEXT,
    session   TEXT,
    ts        TEXT,
    event     TEXT NOT NULL,
    data      TEXT,
    source    TEXT DEFAULT 'kiosk'
);
CREATE INDEX IF NOT EXISTS idx_cstats_ts ON stats_events(ts);
CREATE INDEX IF NOT EXISTS idx_cstats_event ON stats_events(event);
CREATE INDEX IF NOT EXISTS idx_cstats_srv ON stats_events(server_id);

-- Serverlardan kelgan loglar
CREATE TABLE IF NOT EXISTS logs (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        TEXT,
    server_id TEXT,
    level     TEXT DEFAULT 'INFO',
    source    TEXT,
    msg       TEXT
);
CREATE INDEX IF NOT EXISTS idx_logs_ts ON logs(ts);

-- Panel uchun hodisalar oqimi ("So'nggi hodisalar")
CREATE TABLE IF NOT EXISTS events (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    ts   TEXT DEFAULT (datetime('now')),
    kind TEXT,                             -- ok|warn|err|info
    text TEXT
);

-- Bir martalik enrollment tokenlari (installerga yoziladi)
CREATE TABLE IF NOT EXISTS enroll_tokens (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    token_hash TEXT NOT NULL,
    label      TEXT,                       -- "Poyezd 076Ф" (taklif qilingan nom)
    route      TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    used_at    TEXT,
    server_id  TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def init_db():
    os.makedirs(os.path.dirname(config.DB_PATH) or ".", exist_ok=True)
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        # Migratsiya: mavjud bazaga keyin qo'shilgan ustunlar (CREATE IF NOT
        # EXISTS mavjud jadvalni o'zgartirmaydi — guarded ALTER kerak).
        ccols = {r["name"] for r in
                 conn.execute("PRAGMA table_info(content)").fetchall()}
        if "visible" not in ccols:
            conn.execute("ALTER TABLE content ADD COLUMN visible"
                         " INTEGER DEFAULT 1")
        scols = {r["name"] for r in
                 conn.execute("PRAGMA table_info(servers)").fetchall()}
        for col in ("stats_pending", "stats_total", "web_running"):
            if col not in scols:
                conn.execute(f"ALTER TABLE servers ADD COLUMN {col}"
                             " INTEGER DEFAULT 0")
        if "settings" not in scols:
            conn.execute("ALTER TABLE servers ADD COLUMN settings TEXT")
        if "approved" not in scols:
            # Mavjud serverlar token bilan ulangan — ular tasdiqlangan hisoblanadi
            conn.execute("ALTER TABLE servers ADD COLUMN approved"
                         " INTEGER DEFAULT 1")
        conn.commit()
    finally:
        conn.close()


# --------------------------------------------------------------- sozlamalar
def get_setting(key, default=None):
    with _conn() as c:
        row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key, value):
    with _conn() as c:
        c.execute("INSERT INTO settings (key,value) VALUES (?,?) "
                  "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                  (key, value))


# ------------------------------------------------------- parol xeshlash
def hash_secret(plain):
    """pbkdf2$<iter>$<salt>$<hash> — server/db.py bilan bir xil format."""
    iterations = 100_000
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt, iterations)
    return f"pbkdf2${iterations}${salt.hex()}${dk.hex()}"


def verify_secret(plain, stored):
    try:
        algo, iterations, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"),
                                 bytes.fromhex(salt_hex), int(iterations))
        return hmac.compare_digest(dk.hex(), hash_hex)
    except (AttributeError, ValueError):
        return False


# ------------------------------------------------------------- serverlar
def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def create_server(name, route, token, hw_id="", approved=1):
    """Yangi serverni ro'yxatga oladi va uning id'sini qaytaradi.

    `approved=0` — server O'ZI ulangan (tokensiz): ro'yxatda ko'rinadi, lekin
    admin tasdiqlamaguncha unga hech narsa yuborilmaydi."""
    sid = "srv_" + secrets.token_hex(5)
    with _conn() as c:
        c.execute(
            "INSERT INTO servers (id,name,route,token_hash,hw_id,approved) "
            "VALUES (?,?,?,?,?,?)",
            (sid, name, route, hash_secret(token), hw_id, 1 if approved else 0))
    return sid


def server_by_hw(hw_id):
    """Shu qurilma allaqachon ro'yxatga olinganmi (hw_id bo'yicha).

    Server qayta o'rnatilса yoki bazasi tozalansa u yana enroll qiladi —
    shunda BIR XIL qurilma uchun ikkinchi yozuv paydo bo'lmasin: eski yozuv
    yangi token bilan qayta ishlatiladi."""
    if not hw_id:
        return None
    with _conn() as c:
        row = c.execute("SELECT * FROM servers WHERE hw_id=? ORDER BY enrolled_at"
                        " LIMIT 1", (hw_id,)).fetchone()
    return dict(row) if row else None


def reissue_token(server_id, token):
    """Mavjud serverga yangi token beradi (qayta enroll)."""
    with _conn() as c:
        c.execute("UPDATE servers SET token_hash=? WHERE id=?",
                  (hash_secret(token), server_id))


def approve_server(server_id, approved=True):
    with _conn() as c:
        c.execute("UPDATE servers SET approved=? WHERE id=?",
                  (1 if approved else 0, server_id))


def is_approved(server_id):
    with _conn() as c:
        row = c.execute("SELECT approved FROM servers WHERE id=?",
                        (server_id,)).fetchone()
    return bool(row) and (row["approved"] or 0) == 1


def server_auth(server_id, token):
    """Agent tokenini tekshiradi (WS ulanishда)."""
    with _conn() as c:
        row = c.execute("SELECT token_hash FROM servers WHERE id=?",
                        (server_id,)).fetchone()
    return bool(row) and verify_secret(token, row["token_hash"])


def get_server(server_id):
    with _conn() as c:
        row = c.execute("SELECT * FROM servers WHERE id=?", (server_id,)).fetchone()
    return dict(row) if row else None


def get_servers():
    with _conn() as c:
        rows = c.execute("SELECT * FROM servers ORDER BY name").fetchall()
    return [dict(r) for r in rows]


def update_server(server_id, **fields):
    allowed = ("name", "route", "note", "version", "kiosks_total", "kiosks_online",
               "disk_total", "disk_free", "license", "license_note",
               "applied_rev", "queue_active", "queue_pending", "last_seen",
               "stats_pending", "stats_total", "web_running", "settings")
    data = {k: v for k, v in fields.items() if k in allowed}
    if not data:
        return
    sets = ", ".join(f"{k}=?" for k in data)
    with _conn() as c:
        c.execute(f"UPDATE servers SET {sets} WHERE id=?",
                  (*data.values(), server_id))


def touch_server(server_id):
    with _conn() as c:
        c.execute("UPDATE servers SET last_seen=? WHERE id=?", (now(), server_id))


def delete_server(server_id):
    with _conn() as c:
        c.execute("DELETE FROM servers WHERE id=?", (server_id,))


def is_online(server_row):
    """Oxirgi heartbeatдан beri OFFLINE_AFTER_S o'tmagan bo'lsa onlayn."""
    ls = server_row.get("last_seen") if isinstance(server_row, dict) else None
    if not ls:
        return False
    try:
        seen = datetime.strptime(ls, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return False
    return (datetime.now() - seen).total_seconds() <= config.OFFLINE_AFTER_S


def replace_server_kiosks(server_id, kiosks):
    """Serverning kiosk ro'yxatini yangilaydi (heartbeatдан to'liq keladi)."""
    rows = []
    for k in kiosks[:200]:
        if not isinstance(k, dict):
            continue
        did = str(k.get("device_id") or "").strip()[:128]
        if not did:
            continue
        rows.append((server_id, did, str(k.get("kiosk_no") or "")[:32],
                     str(k.get("room") or "")[:64], str(k.get("ip") or "")[:64],
                     str(k.get("platform") or "")[:64],
                     to_int(k.get("cached_n")), to_int(k.get("disk_total")),
                     to_int(k.get("disk_free")), 1 if k.get("online") else 0,
                     str(k.get("last_seen") or "")[:32]))
    with _conn() as c:
        # Ro'yxatda yo'q kiosk o'chirilmaydi (tarix saqlanadi) — faqat
        # online=0 bo'ladi, keyin kelganda yangilanadi.
        c.execute("UPDATE server_kiosks SET online=0 WHERE server_id=?", (server_id,))
        c.executemany(
            "INSERT INTO server_kiosks (server_id,device_id,kiosk_no,room,ip,"
            "platform,cached_n,disk_total,disk_free,online,last_seen) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(server_id,device_id) DO UPDATE SET "
            "kiosk_no=excluded.kiosk_no, room=excluded.room, ip=excluded.ip, "
            "platform=excluded.platform, cached_n=excluded.cached_n, "
            "disk_total=excluded.disk_total, disk_free=excluded.disk_free, "
            "online=excluded.online, last_seen=excluded.last_seen", rows)
    return len(rows)


def forget_kiosk(server_id, device_id):
    """Kioskni bulut ro'yxatidan ham olib tashlaydi (serverда ham o'chiriladi)."""
    with _conn() as c:
        c.execute("DELETE FROM server_kiosks WHERE server_id=? AND device_id=?",
                  (server_id, device_id))


def get_server_kiosks(server_id):
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM server_kiosks WHERE server_id=? "
            "ORDER BY CAST(kiosk_no AS INTEGER), device_id", (server_id,)).fetchall()
    return [dict(r) for r in rows]


def to_int(v, default=0):
    try:
        return max(0, int(v))
    except (TypeError, ValueError):
        return default


# --------------------------------------------------------------- kontent
CONTENT_COLS = ["type", "title", "author", "genre", "description", "duration",
                "pages", "lang", "category_tab", "is_recommended",
                "cache_enabled", "visible", "media_sha", "media_name", "media_size",
                "cover_sha", "cover_name", "cover_size",
                "text_sha", "text_name", "text_size"]


def add_content(data):
    use = [c for c in CONTENT_COLS if c in data]
    ph = ",".join("?" * len(use))
    with _conn() as c:
        cur = c.execute(
            f"INSERT INTO content ({','.join(use)}) VALUES ({ph})",
            [data[k] for k in use])
        return cur.lastrowid


def update_content(content_id, data):
    data = {k: v for k, v in data.items() if k in CONTENT_COLS}
    if not data:
        return
    sets = ", ".join(f"{k}=?" for k in data)
    with _conn() as c:
        c.execute(f"UPDATE content SET {sets} WHERE id=?",
                  (*data.values(), content_id))


def get_content(content_type=None, q=None):
    sql = "SELECT * FROM content"
    args = []
    where = []
    if content_type and content_type in CONTENT_TYPES:
        where.append("type=?")
        args.append(content_type)
    if q:
        where.append("(title LIKE ? OR author LIKE ? OR genre LIKE ?)")
        args += [f"%{q}%"] * 3
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id DESC"
    with _conn() as c:
        rows = c.execute(sql, args).fetchall()
    return [dict(r) for r in rows]


def get_content_by_id(content_id):
    with _conn() as c:
        row = c.execute("SELECT * FROM content WHERE id=?", (content_id,)).fetchone()
    return dict(row) if row else None


def delete_content(content_id):
    """Kutubxonadan o'chiradi. Fayllar (blob) faqat boshqa hech kim
    ishlatmasa o'chiriladi — buni chaqiruvchi storage.gc() bilan qiladi."""
    with _conn() as c:
        c.execute("DELETE FROM content WHERE id=?", (content_id,))


def content_deploy_counts():
    """{content_id: nechta serverga tayinlangan} — kutubxona kartochkalari uchun."""
    with _conn() as c:
        rows = c.execute(
            "SELECT content_id, COUNT(*) n FROM assignments GROUP BY content_id"
        ).fetchall()
    return {r["content_id"]: r["n"] for r in rows}


def shas_in_use():
    """Bazada ishlatilayotgan barcha sha256'lar (yetim blob tozalash uchun)."""
    out = set()
    with _conn() as c:
        for col in ("media_sha", "cover_sha", "text_sha"):
            for r in c.execute(
                    f"SELECT DISTINCT {col} s FROM content WHERE {col} IS NOT NULL"):
                if r["s"]:
                    out.add(r["s"])
    return out


# ----------------------------------------------------- desired state (rev)
def assign(server_ids, content_ids):
    """Kontentni serverlarga tayinlaydi va desired_rev'ni oshiradi."""
    pairs = [(s, c) for s in server_ids for c in content_ids]
    if not pairs:
        return 0
    with _conn() as c:
        c.executemany("INSERT OR IGNORE INTO assignments (server_id,content_id) "
                      "VALUES (?,?)", pairs)
        c.executemany("UPDATE servers SET desired_rev=desired_rev+1 WHERE id=?",
                      [(s,) for s in set(server_ids)])
    return len(pairs)


def unassign(server_ids, content_ids):
    """Tayinlovni olib tashlaydi — server keyingi manifestда faylni O'CHIRADI."""
    pairs = [(s, c) for s in server_ids for c in content_ids]
    if not pairs:
        return 0
    with _conn() as c:
        c.executemany("DELETE FROM assignments WHERE server_id=? AND content_id=?",
                      pairs)
        c.executemany("UPDATE servers SET desired_rev=desired_rev+1 WHERE id=?",
                      [(s,) for s in set(server_ids)])
    return len(pairs)


def unassign_everywhere(content_ids):
    """Kontentni BARCHA serverlardan olib tashlaydi (kutubxonadan o'chirishda)."""
    if not content_ids:
        return []
    qs = ",".join("?" * len(content_ids))
    with _conn() as c:
        rows = c.execute(
            f"SELECT DISTINCT server_id FROM assignments WHERE content_id IN ({qs})",
            content_ids).fetchall()
        sids = [r["server_id"] for r in rows]
        c.execute(f"DELETE FROM assignments WHERE content_id IN ({qs})", content_ids)
        c.executemany("UPDATE servers SET desired_rev=desired_rev+1 WHERE id=?",
                      [(s,) for s in sids])
    return sids


def bump_rev(server_ids):
    """Berilgan serverlarning desired_rev'ini oshiradi — metadata o'zgarganда
    ham serverlar yangi manifest oladi."""
    ids = list({s for s in server_ids})
    if not ids:
        return
    with _conn() as c:
        c.executemany("UPDATE servers SET desired_rev=desired_rev+1 WHERE id=?",
                      [(s,) for s in ids])


def desired_content(server_id):
    """Shu serverda BO'LISHI KERAK bo'lgan kontent (to'liq yozuvlar bilan)."""
    with _conn() as c:
        rows = c.execute(
            "SELECT c.* FROM content c JOIN assignments a ON a.content_id=c.id "
            "WHERE a.server_id=? ORDER BY c.id", (server_id,)).fetchall()
    return [dict(r) for r in rows]


def assigned_ids(server_id):
    with _conn() as c:
        rows = c.execute("SELECT content_id FROM assignments WHERE server_id=?",
                         (server_id,)).fetchall()
    return [r["content_id"] for r in rows]


def servers_with_content(content_id):
    with _conn() as c:
        rows = c.execute("SELECT server_id FROM assignments WHERE content_id=?",
                         (content_id,)).fetchall()
    return [r["server_id"] for r in rows]


# ------------------------------------------------------------------ ishlar
def create_job(kind, title, server_ids, content_ids=(), opts=None):
    with _conn() as c:
        cur = c.execute("INSERT INTO jobs (kind,title,opts) VALUES (?,?,?)",
                        (kind, title, json.dumps(opts or {}, ensure_ascii=False)))
        jid = cur.lastrowid
        if content_ids:
            c.executemany("INSERT OR IGNORE INTO job_items (job_id,content_id) "
                          "VALUES (?,?)", [(jid, i) for i in content_ids])
        c.executemany("INSERT OR IGNORE INTO job_targets (job_id,server_id) "
                      "VALUES (?,?)", [(jid, s) for s in server_ids])
    return jid


def set_target(job_id, server_id, **fields):
    allowed = ("state", "pct", "bytes_done", "bytes_total", "error")
    data = {k: v for k, v in fields.items() if k in allowed}
    if not data:
        return
    sets = ", ".join(f"{k}=?" for k in data)
    with _conn() as c:
        c.execute(f"UPDATE job_targets SET {sets}, updated_at=? "
                  "WHERE job_id=? AND server_id=?",
                  (*data.values(), now(), job_id, server_id))
    _refresh_job_state(job_id)


def _refresh_job_state(job_id):
    """Barcha nishonlar tugagan bo'lsa ishni yopadi."""
    with _conn() as c:
        rows = c.execute("SELECT state FROM job_targets WHERE job_id=?",
                         (job_id,)).fetchall()
        states = [r["state"] for r in rows]
        if not states or any(s in ("pending", "queued", "running") for s in states):
            return
        new = "error" if any(s == "error" for s in states) else "done"
        c.execute("UPDATE jobs SET state=?, done_at=? WHERE id=?",
                  (new, now(), job_id))


def pending_targets(server_id):
    """Shu server uchun hali bajarilmagan ishlar (onlayn bo'lganda yuboriladi)."""
    with _conn() as c:
        rows = c.execute(
            "SELECT t.job_id, j.kind, j.opts FROM job_targets t "
            "JOIN jobs j ON j.id=t.job_id "
            "WHERE t.server_id=? AND t.state IN ('pending','queued','running') "
            "ORDER BY t.job_id", (server_id,)).fetchall()
    return [dict(r) for r in rows]


def get_jobs(limit=40, active_only=False):
    sql = ("SELECT j.*, "
           "(SELECT COUNT(*) FROM job_targets t WHERE t.job_id=j.id) n_targets, "
           "(SELECT COUNT(*) FROM job_targets t WHERE t.job_id=j.id AND t.state='done') n_done, "
           "(SELECT COUNT(*) FROM job_items i WHERE i.job_id=j.id) n_items "
           "FROM jobs j")
    if active_only:
        sql += " WHERE j.state='running'"
    sql += " ORDER BY j.id DESC LIMIT ?"
    with _conn() as c:
        rows = c.execute(sql, (limit,)).fetchall()
        out = []
        for r in rows:
            j = dict(r)
            j["targets"] = [dict(t) for t in c.execute(
                "SELECT t.*, s.name FROM job_targets t "
                "LEFT JOIN servers s ON s.id=t.server_id WHERE t.job_id=? "
                "ORDER BY t.server_id", (j["id"],)).fetchall()]
            j["items"] = [dict(t) for t in c.execute(
                "SELECT c.id, c.title, c.type, c.media_size FROM job_items i "
                "JOIN content c ON c.id=i.content_id WHERE i.job_id=?",
                (j["id"],)).fetchall()]
            out.append(j)
    return out


def cancel_job(job_id):
    with _conn() as c:
        c.execute("UPDATE job_targets SET state='error', error='bekor qilindi' "
                  "WHERE job_id=? AND state IN ('pending','queued','running')",
                  (job_id,))
        c.execute("UPDATE jobs SET state='cancelled', done_at=? WHERE id=?",
                  (now(), job_id))


# ------------------------------------------------------- statistika/loglar
STATS_EVENTS = ("session_start", "session_end", "screen_view", "lang_change",
                "content_open", "ad_play", "qr_route", "site_qr", "sos_open")


def insert_stats(server_id, events):
    rows = []
    for e in events[:5000]:
        if not isinstance(e, dict):
            continue
        ev = str(e.get("event") or "")
        if ev not in STATS_EVENTS:
            continue
        data = e.get("data")
        rows.append((server_id, str(e.get("device_id") or "")[:128],
                     str(e.get("session") or "")[:64], str(e.get("ts") or "")[:32],
                     ev, json.dumps(data, ensure_ascii=False) if data else None,
                     "web" if e.get("source") == "web" else "kiosk"))
    if not rows:
        return 0
    with _conn() as c:
        c.executemany(
            "INSERT INTO stats_events (server_id,device_id,session,ts,event,data,source)"
            " VALUES (?,?,?,?,?,?,?)", rows)
    return len(rows)


def insert_logs(server_id, entries):
    rows = []
    for e in entries[:2000]:
        if not isinstance(e, dict):
            continue
        lvl = str(e.get("level") or "INFO").upper()
        rows.append((str(e.get("ts") or now())[:32], server_id,
                     lvl if lvl in LOG_LEVELS else "INFO",
                     str(e.get("source") or "")[:32], str(e.get("msg") or "")[:1000]))
    if not rows:
        return 0
    with _conn() as c:
        c.executemany("INSERT INTO logs (ts,server_id,level,source,msg) "
                      "VALUES (?,?,?,?,?)", rows)
    return len(rows)


def get_logs(server_id=None, level=None, q=None, limit=200):
    sql = ("SELECT l.*, s.name server_name FROM logs l "
           "LEFT JOIN servers s ON s.id=l.server_id")
    where, args = [], []
    if server_id:
        where.append("l.server_id=?")
        args.append(server_id)
    if level and level.upper() in LOG_LEVELS:
        where.append("l.level=?")
        args.append(level.upper())
    if q:
        where.append("l.msg LIKE ?")
        args.append(f"%{q}%")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY l.id DESC LIMIT ?"
    args.append(min(int(limit), 1000))
    with _conn() as c:
        return [dict(r) for r in c.execute(sql, args).fetchall()]


def add_event(text, kind="info"):
    with _conn() as c:
        c.execute("INSERT INTO events (kind,text) VALUES (?,?)", (kind, text[:300]))


def recent_events(limit=12):
    with _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]


def _since(days):
    return (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")


def _flt(server_id=None, source=None):
    """Statistika so'rovlari uchun umumiy filtr: (SQL bo'lagi, argumentlar)."""
    sql, args = "", []
    if server_id:
        sql += " AND server_id=?"
        args.append(server_id)
    if source in ("kiosk", "web"):
        sql += " AND source=?"
        args.append(source)
    return sql, args


def stats_totals(days=14, server_id=None, source=None):
    """Sessiya soni, noyob qurilma, kontent ochilishi, reklama ko'rsatilishi."""
    flt, extra = _flt(server_id, source)
    args = [_since(days)] + extra

    def one(sql):
        with _conn() as c:
            row = c.execute(sql, args).fetchone()
        return row[0] if row and row[0] is not None else 0

    base = "FROM stats_events WHERE ts >= ?" + flt
    return {
        "sessions": one(f"SELECT COUNT(DISTINCT session) {base} AND event='session_start'"),
        "devices": one(f"SELECT COUNT(DISTINCT device_id) {base}"),
        "opens": one(f"SELECT COUNT(*) {base} AND event='content_open'"),
        "ads": one(f"SELECT COUNT(*) {base} AND event='ad_play'"),
        "events": one(f"SELECT COUNT(*) {base}"),
    }


def stats_daily(days=14, server_id=None, source=None):
    flt, extra = _flt(server_id, source)
    args = [_since(days)] + extra
    with _conn() as c:
        rows = c.execute(
            "SELECT substr(ts,1,10) d, COUNT(DISTINCT session) n "
            "FROM stats_events WHERE ts >= ? AND event='session_start'" + flt +
            " GROUP BY d ORDER BY d", args).fetchall()
    got = {r["d"]: r["n"] for r in rows}
    out = []
    for i in range(days - 1, -1, -1):
        d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        out.append({"date": d, "n": got.get(d, 0)})
    return out


def stats_top_content(days=14, limit=8, server_id=None, source=None):
    """Eng ko'p ochilgan kontent (data JSON ichidagi title bo'yicha)."""
    flt, extra = _flt(server_id, source)
    args = [_since(days)] + extra
    with _conn() as c:
        rows = c.execute(
            "SELECT json_extract(data,'$.title') t, COUNT(*) n FROM stats_events "
            "WHERE ts >= ? AND event='content_open'" + flt +
            " GROUP BY t HAVING t IS NOT NULL ORDER BY n DESC LIMIT ?",
            (*args, limit)).fetchall()
    return [{"title": r["t"], "n": r["n"]} for r in rows]


def stats_by_source(days=14, server_id=None):
    """Kiosk ekrani va veb (telefon/brauzer) bo'yicha taqsimot."""
    flt, extra = _flt(server_id, None)
    with _conn() as c:
        rows = c.execute(
            "SELECT source, COUNT(DISTINCT session) sessions, "
            "COUNT(DISTINCT device_id) devices, COUNT(*) events "
            "FROM stats_events WHERE ts >= ?" + flt + " GROUP BY source",
            (_since(days), *extra)).fetchall()
    return {r["source"] or "kiosk": {"sessions": r["sessions"],
                                     "devices": r["devices"],
                                     "events": r["events"]} for r in rows}


def stats_by_device(days=14, server_id=None, source=None, limit=20):
    """Qurilmalar kesimi: kiosk ekranlari va veb foydalanuvchilari."""
    flt, extra = _flt(server_id, source)
    with _conn() as c:
        rows = c.execute(
            "SELECT e.device_id, e.source, e.server_id, s.name server_name, "
            "COUNT(DISTINCT e.session) sessions, COUNT(*) events, "
            "MAX(e.ts) last_ts FROM stats_events e "
            "LEFT JOIN servers s ON s.id=e.server_id "
            "WHERE e.ts >= ?" + flt.replace(" AND ", " AND e.") +
            " GROUP BY e.device_id ORDER BY sessions DESC, events DESC LIMIT ?",
            (_since(days), *extra, limit)).fetchall()
    return [dict(r) for r in rows]


def stats_top_servers(days=14, limit=8):
    with _conn() as c:
        rows = c.execute(
            "SELECT e.server_id, s.name, COUNT(DISTINCT e.session) n "
            "FROM stats_events e LEFT JOIN servers s ON s.id=e.server_id "
            "WHERE e.ts >= ? AND e.event='session_start' "
            "GROUP BY e.server_id ORDER BY n DESC LIMIT ?",
            (_since(days), limit)).fetchall()
    return [{"server_id": r["server_id"], "name": r["name"] or r["server_id"],
             "n": r["n"]} for r in rows]


def server_sessions_today(server_id):
    today = datetime.now().strftime("%Y-%m-%d")
    with _conn() as c:
        row = c.execute(
            "SELECT COUNT(DISTINCT session) n FROM stats_events "
            "WHERE server_id=? AND event='session_start' AND ts >= ?",
            (server_id, today)).fetchone()
    return row["n"] if row else 0


def server_sessions_list(server_id, limit=40):
    """Tafsilot ekranidagi "Foydalanuvchi sessiyalari" jadvali."""
    with _conn() as c:
        rows = c.execute(
            "SELECT session, device_id, MIN(ts) started, MAX(ts) ended, "
            "COUNT(*) events FROM stats_events WHERE server_id=? AND session<>'' "
            "GROUP BY session ORDER BY started DESC LIMIT ?",
            (server_id, limit)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            top = c.execute(
                "SELECT json_extract(data,'$.title') t FROM stats_events "
                "WHERE session=? AND event='content_open' AND server_id=? LIMIT 1",
                (d["session"], server_id)).fetchone()
            d["content"] = (top["t"] if top and top["t"] else "—")
            lang = c.execute(
                "SELECT json_extract(data,'$.lang') l FROM stats_events "
                "WHERE session=? AND server_id=? AND json_extract(data,'$.lang') "
                "IS NOT NULL LIMIT 1", (d["session"], server_id)).fetchone()
            d["lang"] = (lang["l"] if lang and lang["l"] else "uz")
            out.append(d)
    return out


# --------------------------------------------------------- enroll tokenlar
def create_enroll_token(label, route):
    token = secrets.token_urlsafe(18)
    with _conn() as c:
        c.execute("INSERT INTO enroll_tokens (token_hash,label,route) VALUES (?,?,?)",
                  (hash_secret(token), label, route))
    return token


def consume_enroll_token(token):
    """Tokenni tekshiradi va BIR MARTA ishlatilgan deb belgilaydi.
    Mos yozuvni qaytaradi (label/route bilan) yoki None."""
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM enroll_tokens WHERE used_at IS NULL ORDER BY id"
        ).fetchall()
        for r in rows:
            if verify_secret(token, r["token_hash"]):
                return dict(r)
    return None


def mark_enroll_used(token_id, server_id):
    with _conn() as c:
        c.execute("UPDATE enroll_tokens SET used_at=?, server_id=? WHERE id=?",
                  (now(), server_id, token_id))


def get_enroll_tokens():
    with _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT id,label,route,created_at,used_at,server_id FROM enroll_tokens "
            "ORDER BY id DESC LIMIT 50").fetchall()]


def delete_enroll_token(token_id):
    with _conn() as c:
        c.execute("DELETE FROM enroll_tokens WHERE id=? AND used_at IS NULL",
                  (token_id,))
