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
    license_info  TEXT,                     -- to'liq litsenziya holati (JSON)
    -- 0 = o'zi ro'yxatga turgan, admin TASDIQLAMAGAN. Tasdiqlanmagan serverga
    -- manifest ham, buyruq ham yuborilmaydi (faqat ro'yxatda ko'rinadi).
    approved      INTEGER DEFAULT 1,
    -- 1 = nomni ADMIN qo'ygan. Bunda heartbeatдan kelgan hostname nomni
    -- BOSIB KETMAYDI (aks holda har 30 soniyada "GPUPC" ga qaytardi).
    name_custom   INTEGER DEFAULT 0,
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
    cache_enabled INTEGER DEFAULT 1,      -- lokal kesh yoqilganmi
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

-- Reklama (bulut kutubxonasi). Fayl storage/ da sha256 bo'yicha.
CREATE TABLE IF NOT EXISTS ads (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT,
    subtitle     TEXT,
    link_url     TEXT,
    duration     INTEGER DEFAULT 10,     -- namoyish (soniya); video uchun 0
    interval_min INTEGER,                -- har necha daqiqada (bo'sh = umumiy)
    start_time   TEXT, end_time TEXT,    -- HH:MM oralig'i (bo'sh = doim)
    placement    TEXT DEFAULT 'popup',   -- popup | banner | both
    is_active    INTEGER DEFAULT 1,
    sort_order   INTEGER DEFAULT 0,
    media_sha    TEXT, media_name TEXT, media_size INTEGER DEFAULT 0,
    created_at   TEXT DEFAULT (datetime('now'))
);

-- Reklama qaysi serverlarga tayinlangan (kontent bilan bir xil mantiq)
CREATE TABLE IF NOT EXISTS ad_assignments (
    server_id TEXT NOT NULL,
    ad_id     INTEGER NOT NULL,
    PRIMARY KEY (server_id, ad_id),
    FOREIGN KEY (server_id) REFERENCES servers(id) ON DELETE CASCADE,
    FOREIGN KEY (ad_id) REFERENCES ads(id) ON DELETE CASCADE
);

-- Saytlar — barcha serverlarga bir xil ketadi (foydali havolalar ro'yxati)
CREATE TABLE IF NOT EXISTS sites (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    url         TEXT NOT NULL,
    description TEXT,
    features    TEXT,
    icon        TEXT,
    sort_order  INTEGER DEFAULT 0
);

-- Bekatlar — HAR SERVER uchun alohida (har poyezdning o'z yo'nalishi bor)
CREATE TABLE IF NOT EXISTS stops (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    server_id      TEXT NOT NULL,
    name           TEXT NOT NULL,
    arrival_time   TEXT,
    departure_time TEXT,
    latitude       REAL, longitude REAL,
    distance_km    INTEGER,
    sort_order     INTEGER DEFAULT 0,
    direction      INTEGER DEFAULT 0,    -- 0 = borish, 1 = qaytish
    FOREIGN KEY (server_id) REFERENCES servers(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_stops_srv ON stops(server_id, direction, sort_order);

-- Brending: server bo'yicha almashtiriladigan rasmlar (hero banner va h.k.)
CREATE TABLE IF NOT EXISTS branding (
    server_id TEXT NOT NULL,
    kind      TEXT NOT NULL,             -- hero (keyinchalik: logo, splash…)
    sha       TEXT NOT NULL,
    name      TEXT,
    size      INTEGER DEFAULT 0,
    PRIMARY KEY (server_id, kind),
    FOREIGN KEY (server_id) REFERENCES servers(id) ON DELETE CASCADE
);

-- Brending KUTUBXONASI: yuklangan bannerlar shu yerda turadi (umumiy).
-- `branding` jadvali esa har server uchun QAYSI BIRI faol ekanini saqlaydi —
-- ya'ni mavzu tanlagandek almashtirib turish mumkin, eski rasm yo'qolmaydi.
CREATE TABLE IF NOT EXISTS branding_library (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    kind       TEXT NOT NULL DEFAULT 'hero',
    sha        TEXT NOT NULL,
    name       TEXT,
    size       INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE (kind, sha)
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

-- KUTAYOTGAN buyruqlar: server offlayn bo'lsa yoki REJALASHTIRILGAN bo'lsa
-- shu yerda turadi va vaqti kelganda (server onlayn bo'lganda) yuboriladi.
-- Shuning uchun "saqlash" hech qachon yo'qolmaydi — internet tiklanishi yoki
-- belgilangan sana/vaqt kelishi bilan o'zi qo'llanadi.
CREATE TABLE IF NOT EXISTS pending_ops (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    server_id  TEXT NOT NULL,
    kind       TEXT NOT NULL,           -- set_settings | web | kiosk | announce | cache_clear
    payload    TEXT,                    -- JSON (buyruq maydonlari)
    label      TEXT,                    -- panelда ko'rinadigan qisqa izoh
    apply_at   TEXT,                    -- NULL = imkon bo'lishi bilan
    state      TEXT DEFAULT 'pending',  -- pending | sent | cancelled
    created_at TEXT DEFAULT (datetime('now','localtime')),
    sent_at    TEXT,
    FOREIGN KEY (server_id) REFERENCES servers(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_ops_srv ON pending_ops(server_id, state);

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

-- Panel foydalanuvchilari. Avval bitta global parol edi; u birinchi
-- foydalanuvchi (`admin`) sifatida ko'chiriladi va ishlashda davom etadi.
-- Login qo'shilgani uchun endi loglarда KIM qilgani ham ko'rinadi.
CREATE TABLE IF NOT EXISTS admin_users (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    username   TEXT NOT NULL UNIQUE,
    pass_hash  TEXT NOT NULL,
    role       TEXT DEFAULT 'super',      -- super | operator (kelajakda)
    is_active  INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    last_login TEXT
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
        for col in ("settings", "license_info"):
            if col not in scols:
                conn.execute(f"ALTER TABLE servers ADD COLUMN {col} TEXT")
        if "approved" not in scols:
            # Mavjud serverlar token bilan ulangan — ular tasdiqlangan hisoblanadi
            conn.execute("ALTER TABLE servers ADD COLUMN approved"
                         " INTEGER DEFAULT 1")
        if "name_custom" not in scols:
            conn.execute("ALTER TABLE servers ADD COLUMN name_custom"
                         " INTEGER DEFAULT 0")
        # Serverning LOKAL katalogi (poyezdda qo'shilgan kontent/reklama/sayt/
        # bekat) — telemetriya sifatida panelда KO'RINSIN (desired-state emas).
        for col in ("catalog_counts", "local_catalog"):
            if col not in scols:
                conn.execute(f"ALTER TABLE servers ADD COLUMN {col} TEXT")
        kcols = {r["name"] for r in
                 conn.execute("PRAGMA table_info(server_kiosks)").fetchall()}
        if "cache_enabled" not in kcols:
            conn.execute("ALTER TABLE server_kiosks ADD COLUMN cache_enabled"
                         " INTEGER DEFAULT 1")
        if "label" not in kcols:
            # Kioskning odam beradigan nomi ("1-vagon, o'ng tomon"). Faqat
            # bulutda saqlanadi — heartbeat uni bosib ketmaydi.
            conn.execute("ALTER TABLE server_kiosks ADD COLUMN label TEXT")
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


# ------------------------------------------------------ foydalanuvchilar
DEFAULT_USER = "admin"


def migrate_legacy_password():
    """Eski bitta global parolni `admin_users` ga ko'chiradi (bir marta).

    Shu sababli yangilanishdan keyin ham AYNI parol ishlaydi — faqat endi
    login maydoni bor (bo'sh qoldirilsa `admin` deb qabul qilinadi)."""
    with _conn() as c:
        n = c.execute("SELECT COUNT(*) n FROM admin_users").fetchone()["n"]
        if n:
            return
        row = c.execute("SELECT value FROM settings WHERE key='admin_pass_hash'"
                        ).fetchone()
        if row and row["value"]:
            c.execute("INSERT INTO admin_users (username,pass_hash,role) "
                      "VALUES (?,?,'super')", (DEFAULT_USER, row["value"]))
            log.info("Eski parol '%s' foydalanuvchisiga ko'chirildi", DEFAULT_USER)


def get_user(username):
    with _conn() as c:
        row = c.execute("SELECT * FROM admin_users WHERE username=? "
                        "AND is_active=1", (str(username or "").strip(),)
                        ).fetchone()
    return dict(row) if row else None


def get_users():
    with _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT id,username,role,is_active,created_at,last_login "
            "FROM admin_users ORDER BY id").fetchall()]


def upsert_user(username, password=None, role="super", is_active=1):
    """Foydalanuvchi qo'shadi yoki parolini/rolini yangilaydi."""
    username = str(username).strip()
    if not username:
        raise ValueError("login bo'sh")
    with _conn() as c:
        cur = c.execute("SELECT id FROM admin_users WHERE username=?",
                        (username,)).fetchone()
        if cur:
            if password:
                c.execute("UPDATE admin_users SET pass_hash=?, role=?, "
                          "is_active=? WHERE id=?",
                          (hash_secret(password), role, is_active, cur["id"]))
            else:
                c.execute("UPDATE admin_users SET role=?, is_active=? WHERE id=?",
                          (role, is_active, cur["id"]))
            return cur["id"]
        if not password:
            raise ValueError("yangi foydalanuvchi uchun parol kerak")
        c2 = c.execute("INSERT INTO admin_users (username,pass_hash,role,is_active)"
                       " VALUES (?,?,?,?)",
                       (username, hash_secret(password), role, is_active))
        return c2.lastrowid


def touch_user(user_id):
    with _conn() as c:
        c.execute("UPDATE admin_users SET last_login=? WHERE id=?",
                  (now(), user_id))


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


def rename_server(server_id, name=None, route=None, note=None):
    """Serverga ADMIN nom beradi — shundan keyin heartbeatдagi hostname nomni
    o'zgartirmaydi (`name_custom=1`)."""
    sets, args = [], []
    if name is not None:
        sets += ["name=?", "name_custom=1"]
        args.append(name)
    if route is not None:
        sets.append("route=?")
        args.append(route)
    if note is not None:
        sets.append("note=?")
        args.append(note)
    if not sets:
        return
    with _conn() as c:
        c.execute(f"UPDATE servers SET {', '.join(sets)} WHERE id=?",
                  (*args, server_id))


def set_kiosk_label(server_id, device_id, label):
    """Kioskка odam o'qiydigan nom beradi (faqat bulutda ko'rinadi)."""
    with _conn() as c:
        c.execute("UPDATE server_kiosks SET label=? WHERE server_id=? "
                  "AND device_id=?", (label, server_id, device_id))


def update_server(server_id, **fields):
    allowed = ("name", "route", "note", "version", "kiosks_total", "kiosks_online",
               "disk_total", "disk_free", "license", "license_note",
               "applied_rev", "queue_active", "queue_pending", "last_seen",
               "stats_pending", "stats_total", "web_running", "settings",
               "license_info", "catalog_counts", "local_catalog")
    data = {k: v for k, v in fields.items() if k in allowed}
    if not data:
        return
    sets = ", ".join(f"{k}=?" for k in data)
    with _conn() as c:
        c.execute(f"UPDATE servers SET {sets} WHERE id=?",
                  (*data.values(), server_id))


def set_local_catalog(server_id, catalog):
    """Serverning lokal katalogini saqlaydi (JSON). Panel server tafsilotiда
    «poyezdda mavjud kontent» sifatida ko'rsatadi + bekatlar jadvalини
    serverdagi joriy yo'nalishдан to'ldirish uchun ishlatadi."""
    import json as _json
    with _conn() as c:
        c.execute("UPDATE servers SET local_catalog=?, catalog_counts=? WHERE id=?",
                  (_json.dumps(catalog, ensure_ascii=False),
                   _json.dumps(_catalog_counts(catalog), ensure_ascii=False),
                   server_id))


def _catalog_counts(cat):
    """Lokal katalogдан yengil hisoblar (heartbeatда ham keladi).

    Buzuq shakl (list/int o'rniga kutilган) kelса ham YIQILMAYDI — agent
    kanalини uzib qo'ymaslik uchun har bir maydonни ehtiyotkorona sanaymiz."""
    def _n(x):
        try:
            return len(x)
        except TypeError:
            return 0
    if not isinstance(cat, dict):
        return {"content": 0, "ads": 0, "sites": 0, "stops": 0}
    route = cat.get("route")
    route = route if isinstance(route, dict) else {}
    return {
        "content": _n(cat.get("content")),
        "ads": _n(cat.get("ads")),
        "sites": _n(cat.get("sites")),
        "stops": _n(route.get("0")) + _n(route.get("1")),
    }


def get_local_catalog(server_id):
    """Serverning lokal katalogi (dict) yoki None."""
    import json as _json
    row = get_server(server_id) or {}
    raw = row.get("local_catalog")
    if not raw:
        return None
    try:
        return _json.loads(raw)
    except (ValueError, TypeError):
        return None


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
                     0 if k.get("cache_enabled") == 0 else 1,
                     str(k.get("last_seen") or "")[:32]))
    with _conn() as c:
        # Ro'yxatda yo'q kiosk o'chirilmaydi (tarix saqlanadi) — faqat
        # online=0 bo'ladi, keyin kelganda yangilanadi.
        c.execute("UPDATE server_kiosks SET online=0 WHERE server_id=?", (server_id,))
        c.executemany(
            "INSERT INTO server_kiosks (server_id,device_id,kiosk_no,room,ip,"
            "platform,cached_n,disk_total,disk_free,online,cache_enabled,"
            "last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(server_id,device_id) DO UPDATE SET "
            "kiosk_no=excluded.kiosk_no, room=excluded.room, ip=excluded.ip, "
            "platform=excluded.platform, cached_n=excluded.cached_n, "
            "disk_total=excluded.disk_total, disk_free=excluded.disk_free, "
            "online=excluded.online, cache_enabled=excluded.cache_enabled, "
            "last_seen=excluded.last_seen", rows)
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
    """Bazada ishlatilayotgan barcha sha256'lar (yetim blob tozalash uchun).
    Kontent VA reklama fayllari hisobga olinadi."""
    out = set()
    with _conn() as c:
        for col in ("media_sha", "cover_sha", "text_sha"):
            for r in c.execute(
                    f"SELECT DISTINCT {col} s FROM content WHERE {col} IS NOT NULL"):
                if r["s"]:
                    out.add(r["s"])
        for r in c.execute("SELECT DISTINCT media_sha s FROM ads "
                           "WHERE media_sha IS NOT NULL"):
            if r["s"]:
                out.add(r["s"])
        for r in c.execute("SELECT DISTINCT sha s FROM branding "
                           "WHERE sha IS NOT NULL"):
            if r["s"]:
                out.add(r["s"])
        # Kutubxonadagi bannerlar ham saqlanadi (faol bo'lmasa ham — keyin
        # qayta tanlash mumkin bo'lishi kerak)
        for r in c.execute("SELECT DISTINCT sha s FROM branding_library "
                           "WHERE sha IS NOT NULL"):
            if r["s"]:
                out.add(r["s"])
    return out


# ----------------------------------------------------- reklama / sayt / bekat
ADS_COLS = ["title", "subtitle", "link_url", "duration", "interval_min",
            "start_time", "end_time", "placement", "is_active", "sort_order",
            "media_sha", "media_name", "media_size"]
SITE_COLS = ["name", "url", "description", "features", "icon", "sort_order"]
STOP_COLS = ["server_id", "name", "arrival_time", "departure_time", "latitude",
             "longitude", "distance_km", "sort_order", "direction"]


def _ins(table, cols, data):
    use = [c for c in cols if c in data]
    if not use:
        raise ValueError(f"{table}: yoziladigan ustun yo'q")
    ph = ",".join("?" * len(use))
    with _conn() as c:
        cur = c.execute(f"INSERT INTO {table} ({','.join(use)}) VALUES ({ph})",
                        [data[k] for k in use])
        return cur.lastrowid


def _upd(table, row_id, cols, data):
    data = {k: v for k, v in data.items() if k in cols}
    if not data:
        return
    sets = ", ".join(f"{k}=?" for k in data)
    with _conn() as c:
        c.execute(f"UPDATE {table} SET {sets} WHERE id=?",
                  (*data.values(), row_id))


def _del(table, row_id):
    with _conn() as c:
        c.execute(f"DELETE FROM {table} WHERE id=?", (row_id,))


# --- Reklama
def add_ad(data):
    return _ins("ads", ADS_COLS, data)


def update_ad(ad_id, data):
    _upd("ads", ad_id, ADS_COLS, data)


def delete_ad(ad_id):
    _del("ads", ad_id)


def get_ads():
    with _conn() as c:
        rows = c.execute("SELECT * FROM ads ORDER BY sort_order, id").fetchall()
        assigned = {}
        for r in c.execute("SELECT ad_id, server_id FROM ad_assignments"):
            assigned.setdefault(r["ad_id"], []).append(r["server_id"])
    out = []
    for r in rows:
        d = dict(r)
        d["servers"] = assigned.get(d["id"], [])
        d["deployed"] = len(d["servers"])
        out.append(d)
    return out


def get_ad_by_id(ad_id):
    with _conn() as c:
        row = c.execute("SELECT * FROM ads WHERE id=?", (ad_id,)).fetchone()
    return dict(row) if row else None


def assign_ads(server_ids, ad_ids):
    pairs = [(s, a) for s in server_ids for a in ad_ids]
    if not pairs:
        return 0
    with _conn() as c:
        c.executemany("INSERT OR IGNORE INTO ad_assignments (server_id,ad_id) "
                      "VALUES (?,?)", pairs)
    bump_rev(server_ids)
    return len(pairs)


def unassign_ads(server_ids, ad_ids):
    pairs = [(s, a) for s in server_ids for a in ad_ids]
    if not pairs:
        return 0
    with _conn() as c:
        c.executemany("DELETE FROM ad_assignments WHERE server_id=? AND ad_id=?",
                      pairs)
    bump_rev(server_ids)
    return len(pairs)


def ad_servers(ad_id):
    with _conn() as c:
        rows = c.execute("SELECT server_id FROM ad_assignments WHERE ad_id=?",
                         (ad_id,)).fetchall()
    return [r["server_id"] for r in rows]


def desired_ads(server_id):
    with _conn() as c:
        rows = c.execute(
            "SELECT a.* FROM ads a JOIN ad_assignments x ON x.ad_id=a.id "
            "WHERE x.server_id=? ORDER BY a.sort_order, a.id",
            (server_id,)).fetchall()
    return [dict(r) for r in rows]


def ad_assigned_ids(server_id):
    with _conn() as c:
        rows = c.execute("SELECT ad_id FROM ad_assignments WHERE server_id=?",
                         (server_id,)).fetchall()
    return [r["ad_id"] for r in rows]


# --- Saytlar (barcha serverlarga bir xil)
def add_site(data):
    sid = _ins("sites", SITE_COLS, data)
    bump_all_rev()
    return sid


def update_site(site_id, data):
    _upd("sites", site_id, SITE_COLS, data)
    bump_all_rev()


def delete_site(site_id):
    _del("sites", site_id)
    bump_all_rev()


def get_sites():
    with _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM sites ORDER BY sort_order, id").fetchall()]


def bump_all_rev():
    """Barcha serverlarning rev'ini oshiradi (sayt ro'yxati hammaga tegishli)."""
    with _conn() as c:
        c.execute("UPDATE servers SET desired_rev=desired_rev+1")


# --- Bekatlar (har server uchun alohida)
def add_stop(data):
    sid = _ins("stops", STOP_COLS, data)
    bump_rev([data["server_id"]])
    return sid


def update_stop(stop_id, data):
    with _conn() as c:
        row = c.execute("SELECT server_id FROM stops WHERE id=?",
                        (stop_id,)).fetchone()
    _upd("stops", stop_id, STOP_COLS, data)
    if row:
        bump_rev([row["server_id"]])


def delete_stop(stop_id):
    with _conn() as c:
        row = c.execute("SELECT server_id FROM stops WHERE id=?",
                        (stop_id,)).fetchone()
    _del("stops", stop_id)
    if row:
        bump_rev([row["server_id"]])


def get_stops(server_id, direction=None):
    sql = "SELECT * FROM stops WHERE server_id=?"
    args = [server_id]
    if direction in (0, 1):
        sql += " AND direction=?"
        args.append(direction)
    sql += " ORDER BY direction, sort_order, id"
    with _conn() as c:
        return [dict(r) for r in c.execute(sql, args).fetchall()]


def replace_stops(server_id, stops):
    """Serverning bekatlar jadvalini to'liq almashtiradi (jadval kiritish
    odatda to'liq qayta yozish bilan bo'ladi — bittalab tahrirlashdan qulay)."""
    rows = []
    for i, s in enumerate(stops[:200]):
        if not isinstance(s, dict) or not str(s.get("name") or "").strip():
            continue
        rows.append((server_id, str(s["name"])[:120],
                     str(s.get("arrival_time") or "")[:8],
                     str(s.get("departure_time") or "")[:8],
                     s.get("latitude"), s.get("longitude"),
                     to_int(s.get("distance_km")),
                     to_int(s.get("sort_order"), i),
                     1 if to_int(s.get("direction")) == 1 else 0))
    with _conn() as c:
        c.execute("DELETE FROM stops WHERE server_id=?", (server_id,))
        c.executemany(
            "INSERT INTO stops (server_id,name,arrival_time,departure_time,"
            "latitude,longitude,distance_km,sort_order,direction) "
            "VALUES (?,?,?,?,?,?,?,?,?)", rows)
    bump_rev([server_id])
    return len(rows)


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


# ------------------------------------------------------------------ brending
BRANDING_KINDS = ("hero",)


def set_branding(server_id, kind, sha, name, size):
    with _conn() as c:
        c.execute("INSERT INTO branding (server_id,kind,sha,name,size) "
                  "VALUES (?,?,?,?,?) ON CONFLICT(server_id,kind) DO UPDATE SET "
                  "sha=excluded.sha, name=excluded.name, size=excluded.size",
                  (server_id, kind, sha, name, size))
    bump_rev([server_id])


def clear_branding(server_id, kind):
    with _conn() as c:
        c.execute("DELETE FROM branding WHERE server_id=? AND kind=?",
                  (server_id, kind))
    bump_rev([server_id])


def get_branding(server_id):
    with _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM branding WHERE server_id=?", (server_id,)).fetchall()]


def branding_shas():
    with _conn() as c:
        return {r["sha"] for r in c.execute(
            "SELECT DISTINCT sha FROM branding WHERE sha IS NOT NULL")}


# --- Banner kutubxonasi (yuklangan rasmlar saqlanib turadi)
def lib_add(kind, sha, name, size):
    """Kutubxonaga qo'shadi (bir xil rasm ikki marta yozilmaydi) va id qaytaradi."""
    with _conn() as c:
        row = c.execute("SELECT id FROM branding_library WHERE kind=? AND sha=?",
                        (kind, sha)).fetchone()
        if row:
            return row["id"]
        cur = c.execute("INSERT INTO branding_library (kind,sha,name,size) "
                        "VALUES (?,?,?,?)", (kind, sha, name, size))
        return cur.lastrowid


def lib_list(kind="hero"):
    with _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM branding_library WHERE kind=? ORDER BY id DESC",
            (kind,)).fetchall()]


def lib_get(lib_id):
    with _conn() as c:
        row = c.execute("SELECT * FROM branding_library WHERE id=?",
                        (lib_id,)).fetchone()
    return dict(row) if row else None


def lib_delete(lib_id):
    """Kutubxonadan o'chiradi. Qaysi serverlarda faol bo'lса — ular
    standart rasmga qaytadi (server_id ro'yxati qaytariladi)."""
    row = lib_get(lib_id)
    if not row:
        return []
    with _conn() as c:
        srv = [r["server_id"] for r in c.execute(
            "SELECT server_id FROM branding WHERE kind=? AND sha=?",
            (row["kind"], row["sha"])).fetchall()]
        c.execute("DELETE FROM branding WHERE kind=? AND sha=?",
                  (row["kind"], row["sha"]))
        c.execute("DELETE FROM branding_library WHERE id=?", (lib_id,))
    bump_rev(srv)
    return srv


def lib_shas():
    with _conn() as c:
        return {r["sha"] for r in c.execute(
            "SELECT DISTINCT sha FROM branding_library").fetchall()}


# -------------------------------------------- kutayotgan/rejalashtirilgan ish
def queue_op(server_id, kind, payload, label="", apply_at=None):
    """Buyruqni navbatga qo'yadi. `apply_at` (YYYY-MM-DD HH:MM:SS) berilса —
    o'sha vaqtdan keyin, aks holda server onlayn bo'lishi bilan yuboriladi."""
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO pending_ops (server_id,kind,payload,label,apply_at) "
            "VALUES (?,?,?,?,?)",
            (server_id, kind, json.dumps(payload or {}, ensure_ascii=False),
             label[:200], apply_at))
        return cur.lastrowid


def due_ops(server_id=None):
    """Yuborish vaqti KELGAN ishlar (rejasi yo'q yoki vaqti o'tgan)."""
    sql = ("SELECT * FROM pending_ops WHERE state='pending' "
           "AND (apply_at IS NULL OR apply_at <= ?)")
    args = [now()]
    if server_id:
        sql += " AND server_id=?"
        args.append(server_id)
    sql += " ORDER BY id"
    with _conn() as c:
        return [dict(r) for r in c.execute(sql, args).fetchall()]


def get_pending_ops(server_id):
    """Panelда ko'rsatish uchun — hali yuborilmagan hammasi."""
    with _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM pending_ops WHERE server_id=? AND state='pending' "
            "ORDER BY COALESCE(apply_at,'0'), id", (server_id,)).fetchall()]


def mark_op_sent(op_id):
    with _conn() as c:
        c.execute("UPDATE pending_ops SET state='sent', sent_at=? WHERE id=?",
                  (now(), op_id))


def cancel_op(op_id):
    with _conn() as c:
        c.execute("UPDATE pending_ops SET state='cancelled' WHERE id=? "
                  "AND state='pending'", (op_id,))


def pending_op_count(server_id):
    with _conn() as c:
        row = c.execute("SELECT COUNT(*) n FROM pending_ops WHERE server_id=? "
                        "AND state='pending'", (server_id,)).fetchone()
    return row["n"] if row else 0


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


def retry_job(job_id):
    """Xato bo'lgan nishonlarni qaytadan navbatga qo'yadi va nishon
    server_id'larini qaytaradi (chaqiruvchi manifest yuboradi)."""
    with _conn() as c:
        rows = c.execute("SELECT server_id FROM job_targets WHERE job_id=? "
                         "AND state='error'", (job_id,)).fetchall()
        sids = [r["server_id"] for r in rows]
        if not sids:
            return []
        c.execute("UPDATE job_targets SET state='pending', pct=0, error=NULL "
                  "WHERE job_id=? AND state='error'", (job_id,))
        c.execute("UPDATE jobs SET state='running', done_at=NULL WHERE id=?",
                  (job_id,))
    return sids


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


def clear_stats():
    """Bulutdagi barcha statistika eventlarини o'chiradi (0 dan test qilish
    uchun). Serverlardagi lokal statistika tegilmaydi — lekin ular allaqachon
    yuborganini qayta yubormaydi, shuning uchun bulut toza qoladi va faqat yangi
    aktivlik yig'iladi. Panel ko'rsatkichlari ham 0 ga tushadi."""
    with _conn() as c:
        n = c.execute("SELECT COUNT(*) FROM stats_events").fetchone()[0]
        c.execute("DELETE FROM stats_events")
        try:
            c.execute("DELETE FROM sqlite_sequence WHERE name='stats_events'")
        except Exception:
            pass
        try:
            c.execute("UPDATE servers SET stats_pending=0, stats_total=0")
        except Exception:
            pass
    return n


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


def stats_top_ads(days=14, limit=8, server_id=None, source=None):
    """Eng ko'p KO'RSATILGAN reklamalar (ad_play eventлари, data.title bo'yicha).
    Sarlavhasiz eski eventlar 'placement'га yig'iladi (bo'sh bo'lmasin)."""
    flt, extra = _flt(server_id, source)
    args = [_since(days)] + extra
    with _conn() as c:
        rows = c.execute(
            "SELECT COALESCE(NULLIF(json_extract(data,'$.title'),''), "
            "       json_extract(data,'$.placement'), '(nomsiz)') t, "
            "COUNT(*) n FROM stats_events "
            "WHERE ts >= ? AND event='ad_play'" + flt +
            " GROUP BY t ORDER BY n DESC LIMIT ?",
            (*args, limit)).fetchall()
    return [{"title": r["t"], "n": r["n"]} for r in rows]


def _stats_group(days, event, field, server_id, source, limit=None, dflt=None):
    """Umumiy: bitta event turини data JSON maydoni bo'yicha guruhlab sanaydi
    (donut/ro'yxat uchun). `dflt` — maydon NULL bo'lsa o'rniga."""
    flt, extra = _flt(server_id, source)
    col = f"json_extract(data,'$.{field}')"
    if dflt is not None:
        col = f"COALESCE(NULLIF({col},''),'{dflt}')"
    q = (f"SELECT {col} k, COUNT(*) n FROM stats_events "
         f"WHERE ts >= ? AND event=?{flt} GROUP BY k "
         f"{'HAVING k IS NOT NULL ' if dflt is None else ''}ORDER BY n DESC")
    if limit:
        q += " LIMIT ?"
    with _conn() as c:
        rows = c.execute(q, (_since(days), event, *extra, *([limit] if limit else []))).fetchall()
    return [{"k": r["k"], "n": r["n"]} for r in rows]


def stats_ads_placement(days=14, server_id=None, source=None):
    """Reklama qayerda ko'rsatilgani: banner / popup / pre|mid|end (kino ichi)."""
    return _stats_group(days, "ad_play", "placement", server_id, source, dflt="popup")


def stats_content_types(days=14, server_id=None, source=None):
    """Ochilган kontent turlari (movie/cartoon/music/book/audiobook)."""
    return _stats_group(days, "content_open", "type", server_id, source, dflt="?")


def stats_langs(days=14, server_id=None, source=None):
    """Sessiyalar tili (session_start.lang)."""
    return _stats_group(days, "session_start", "lang", server_id, source, dflt="uz")


def stats_screens(days=14, server_id=None, source=None, limit=8):
    """Eng ko'p ochilган ekranlar (screen_view.screen)."""
    return _stats_group(days, "screen_view", "screen", server_id, source, limit)


def stats_sites(days=14, server_id=None, source=None, limit=8):
    """QR bilan ochilган saytlar (site_qr.site)."""
    return _stats_group(days, "site_qr", "site", server_id, source, limit)


def stats_event_mix(days=14, server_id=None, source=None):
    """Foydalanuvchi harakatlari taqsimoti (kontent/reklama/QR/SOS/til)."""
    flt, extra = _flt(server_id, source)
    with _conn() as c:
        rows = c.execute(
            "SELECT event k, COUNT(*) n FROM stats_events WHERE ts >= ?"
            + flt + " AND event IN ('content_open','ad_play','site_qr',"
            "'qr_route','sos_open','lang_change') GROUP BY k ORDER BY n DESC",
            (_since(days), *extra)).fetchall()
    return [{"k": r["k"], "n": r["n"]} for r in rows]


def stats_session_avg(days=14, server_id=None, source=None):
    """O'rtacha sessiya davomiyligi (soniya) — session_end.duration_s."""
    flt, extra = _flt(server_id, source)
    with _conn() as c:
        r = c.execute(
            "SELECT AVG(CAST(json_extract(data,'$.duration_s') AS REAL)) a, "
            "COUNT(*) n FROM stats_events WHERE ts >= ? AND event='session_end'"
            + flt, (_since(days), *extra)).fetchone()
    return {"avg_s": int(r["a"] or 0), "n": r["n"] or 0}


def stats_hourly(days=14, server_id=None, source=None):
    """Kunning qaysi soatlarida faollik (0..23) — barcha eventlar."""
    flt, extra = _flt(server_id, source)
    with _conn() as c:
        rows = c.execute(
            "SELECT CAST(strftime('%H', REPLACE(ts,'T',' ')) AS INTEGER) h, "
            "COUNT(*) n FROM stats_events WHERE ts >= ?" + flt +
            " GROUP BY h", (_since(days), *extra)).fetchall()
    by = {r["h"]: r["n"] for r in rows if r["h"] is not None}
    return [{"h": h, "n": by.get(h, 0)} for h in range(24)]


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


def kiosk_session_counts(server_id, days=1):
    """Har bir kiosk bo'yicha sessiya soni (kiosk kartochkasida ko'rinadi)."""
    with _conn() as c:
        rows = c.execute(
            "SELECT device_id, COUNT(DISTINCT session) n FROM stats_events "
            "WHERE server_id=? AND event='session_start' AND ts >= ? "
            "GROUP BY device_id", (server_id, _since(days))).fetchall()
    return {r["device_id"]: r["n"] for r in rows}


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
