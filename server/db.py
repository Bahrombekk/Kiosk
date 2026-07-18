"""
db.py — SQLite baza bilan ishlash (TZ 10-bo'lim sxemasi).

Jadvallar: content, ads, sites, settings, route_stops.
Birinchi ishga tushishda baza yaratiladi va test kontent bilan to'ldiriladi
(2-bosqich "tayyor mezoni" — /api/content ro'yxat bersin).
"""
import sqlite3
import os
import logging
import hashlib
import hmac
import secrets
from contextlib import contextmanager, closing
from datetime import datetime

import config

log = logging.getLogger("kiosk.db")

# Kontentning ruxsat etilgan turlari (validatsiya uchun bir joyda).
CONTENT_TYPES = ("movie", "cartoon", "music", "book", "audiobook")


def connect():
    # timeout: admin (Qt oqimi) va server (uvicorn oqimi) bir vaqtda yozsa
    # "database is locked" darhol otilmasin — 30s kutadi. WAL: o'quvchi va
    # yozuvchi bir-birini bloklamaydi (parallel kirish xavfsiz bo'ladi).
    conn = sqlite3.connect(config.DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row  # natijalar dict kabi olinadi
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


@contextmanager
def _conn():
    """Tranzaksiyani avtomatik commit qiladi va ulanishni yopadi (kod takrorini kamaytiradi)."""
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
CREATE TABLE IF NOT EXISTS content (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    type          TEXT NOT NULL,          -- movie|cartoon|music|book|audiobook
    title         TEXT NOT NULL,
    author        TEXT,
    genre         TEXT,
    description   TEXT,
    duration      INTEGER,                -- soniya (video/audio)
    pages         INTEGER,                -- sahifa (kitob)
    cover_path    TEXT,
    file_path     TEXT,                   -- video/audio fayl
    text_path     TEXT,                   -- kitob matni fayli
    category_tab  TEXT,
    lang          TEXT,                    -- uz|ru|en; NULL = barcha tillarda
    lang_group    INTEGER,                 -- bir asarning til versiyalari guruhi
    cache_enabled INTEGER DEFAULT 1,       -- 1 = kiosklar lokal keshiga yuklansin
    is_recommended INTEGER DEFAULT 0,
    visible       INTEGER DEFAULT 1,       -- 0 = kiosklarda umuman ko'rinmaydi
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ads (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    image_path  TEXT,                      -- eski ustun (media_path'ga ko'chirilgan)
    media_path  TEXT,                      -- reklama fayli: rasm YOKI video
    title       TEXT,
    subtitle    TEXT,
    link_url    TEXT,
    duration    INTEGER DEFAULT 10,        -- namoyish (soniya); video uchun 0 = oxirigacha
    interval_min INTEGER,                  -- har necha daqiqada chiqadi (bo'sh = umumiy sozlama)
    start_time  TEXT,                      -- HH:MM — shu vaqtdan ko'rsatiladi (bo'sh = doim)
    end_time    TEXT,                      -- HH:MM — shu vaqtgacha
    placement   TEXT DEFAULT 'popup',      -- popup | banner (asosiy sahifa) | both
    is_active   INTEGER DEFAULT 1,
    sort_order  INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sites (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    url         TEXT NOT NULL,
    description TEXT,
    features    TEXT,                     -- JSON yoki matn
    icon        TEXT,
    sort_order  INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS route_stops (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL,
    arrival_time   TEXT,                  -- HH:MM (kelish)
    departure_time TEXT,                  -- HH:MM (jo'nash)
    latitude       REAL,
    longitude      REAL,
    distance_km    INTEGER,               -- boshlang'ich bekatdan masofa
    sort_order     INTEGER DEFAULT 0,
    direction      INTEGER DEFAULT 0      -- 0 = borish, 1 = qaytish
);

CREATE TABLE IF NOT EXISTS kiosks (
    device_id  TEXT PRIMARY KEY,            -- kiosk hostname (barqaror ID)
    kiosk_no   TEXT,                        -- o'rnatuvchi bergan raqam (server.txt)
    room       TEXT,                        -- xona/vagon raqami (server.txt)
    ip         TEXT,
    platform   TEXT,
    cached_n   INTEGER DEFAULT 0,           -- lokal keshlangan media soni
    cached_ids TEXT,                        -- keshlangan kontent id'lari (JSON)
    disk_total INTEGER,                     -- kiosk diski hajmi (bayt)
    disk_free  INTEGER,                     -- bo'sh joy (bayt)
    caching    TEXT,                        -- hozir yuklanayotgan media (JSON: id/pct/title)
    cache_enabled INTEGER DEFAULT 1,        -- 0 = shu kioskда lokal kesh o'chiq (xotirasiz kiosk)
    first_seen TEXT DEFAULT (datetime('now','localtime')),
    last_seen  TEXT                         -- oxirgi heartbeat vaqti
);

CREATE TABLE IF NOT EXISTS audit_log (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ts      TEXT DEFAULT (datetime('now','localtime')),
    action  TEXT NOT NULL,
    details TEXT
);

CREATE TABLE IF NOT EXISTS stats_events (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT,
    session   TEXT,                        -- kiosk sessiya id'si
    ts        TEXT,                        -- kiosk vaqti (ISO, lokal)
    event     TEXT NOT NULL,               -- session_start|screen_view|content_open|ad_play|...
    data      TEXT                         -- JSON qo'shimcha maydonlar
);
CREATE INDEX IF NOT EXISTS idx_stats_ts ON stats_events(ts);
CREATE INDEX IF NOT EXISTS idx_stats_event ON stats_events(event);
"""


def init_db():
    """Bazani yaratadi, migratsiya qiladi va minimal default sozlamalarni yozadi."""
    os.makedirs(config.CONTENT_DIR, exist_ok=True)
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        # Eski bazalarga yangi ustunlar (CREATE IF NOT EXISTS mavjud jadvalni
        # o'zgartirmaydi — guarded ALTER bilan migratsiya qilamiz)
        cols = {r["name"] for r in
                conn.execute("PRAGMA table_info(route_stops)").fetchall()}
        if "departure_time" not in cols:
            conn.execute(
                "ALTER TABLE route_stops ADD COLUMN departure_time TEXT")
        if "distance_km" not in cols:
            conn.execute(
                "ALTER TABLE route_stops ADD COLUMN distance_km INTEGER")
        if "direction" not in cols:    # ikki yo'nalish (borish/qaytish)
            conn.execute("ALTER TABLE route_stops ADD COLUMN direction"
                         " INTEGER DEFAULT 0")
        # content: til ustunlari (ko'p tilli katalog). Mavjud yozuvlar 'uz'
        # deb belgilanadi (kiosk qat'iy til filtri bilan ishlaydi).
        ccols = {r["name"] for r in
                 conn.execute("PRAGMA table_info(content)").fetchall()}
        if "lang" not in ccols:
            conn.execute("ALTER TABLE content ADD COLUMN lang TEXT"
                         " DEFAULT 'uz'")
        if "lang_group" not in ccols:
            conn.execute("ALTER TABLE content ADD COLUMN lang_group INTEGER")
        if "cache_enabled" not in ccols:
            conn.execute("ALTER TABLE content ADD COLUMN cache_enabled"
                         " INTEGER DEFAULT 1")
        if "visible" not in ccols:
            conn.execute("ALTER TABLE content ADD COLUMN visible"
                         " INTEGER DEFAULT 1")
        # ads: media (rasm/video), davomiylik va vaqt oralig'i ustunlari
        acols = {r["name"] for r in
                 conn.execute("PRAGMA table_info(ads)").fetchall()}
        if "media_path" not in acols:
            conn.execute("ALTER TABLE ads ADD COLUMN media_path TEXT")
            # Eski yozuvlardagi rasm nomini yangi ustunga ko'chiramiz
            conn.execute("UPDATE ads SET media_path = image_path"
                         " WHERE media_path IS NULL")
        if "duration" not in acols:
            conn.execute("ALTER TABLE ads ADD COLUMN duration INTEGER DEFAULT 10")
        if "interval_min" not in acols:
            conn.execute("ALTER TABLE ads ADD COLUMN interval_min INTEGER")
        if "start_time" not in acols:
            conn.execute("ALTER TABLE ads ADD COLUMN start_time TEXT")
        if "end_time" not in acols:
            conn.execute("ALTER TABLE ads ADD COLUMN end_time TEXT")
        if "placement" not in acols:
            conn.execute("ALTER TABLE ads ADD COLUMN placement TEXT"
                         " DEFAULT 'popup'")
        # kiosks: kesh ro'yxati va disk ma'lumotlari (keyin qo'shilgan)
        kcols = {r["name"] for r in
                 conn.execute("PRAGMA table_info(kiosks)").fetchall()}
        for col, ddl in (("cached_ids", "TEXT"), ("disk_total", "INTEGER"),
                         ("disk_free", "INTEGER"), ("caching", "TEXT"),
                         ("cache_enabled", "INTEGER DEFAULT 1")):
            if col not in kcols:
                conn.execute(f"ALTER TABLE kiosks ADD COLUMN {col} {ddl}")
        conn.commit()
        _ensure_defaults(conn)
        _remove_legacy_seed(conn)
        conn.commit()
    finally:
        conn.close()   # xato bo'lsa ham ulanish (handle) oqib qolmasin


def _ensure_defaults(conn):
    """Ilova ishlashi uchun kerakli, lekin demo katalog bo'lmagan sozlamalar."""
    conn.executemany(
        "INSERT OR IGNORE INTO settings (key,value) VALUES (?,?)",
        [
            ("default_theme", "light"),
            ("ad_interval_min", "5"),
            ("ad_algorithm", "weighted"),
            ("media_cache", "1"),
            ("cache_limit_gb", "0"),
            ("sos_enabled", "0"),
            ("active_route_direction", "0"),   # 0=borish, 1=qaytish (kioskda faol)
            ("weather_auto", "1"),             # 1=internet ob-havo, 0=qo'lda harorat
            ("speed_auto", "1"),               # 1=jadvaldan tezlik, 0=qo'lda tezlik
            ("trial_enabled", "0"),            # 1=sinov muddati nazorati yoqiq
            ("trial_start", ""),               # topshirish sanasi YYYY-MM-DD
            ("trial_days", "30"),              # necha kunga berilgan
            ("trial_blocked", "0"),            # 1=qo'lda darhol bloklangan
        ])


def _remove_legacy_seed(conn):
    """Avvalgi buildlarda avtomatik qo'shilgan demo yozuvlarni tozalaydi."""
    done = conn.execute(
        "SELECT value FROM settings WHERE key='legacy_seed_cleanup_done'"
    ).fetchone()
    if done and done["value"] == "1":
        return
    conn.execute(
        """DELETE FROM content
           WHERE (title,file_path) IN (
             ('Baron','baron.mp4'),
             ('Sarob','sarob.mp4'),
             ('Zumrad va Qimmat','zumrad.mp4'),
             ('Yulduz Usmonova вЂ” Konsert','concert.mp4'),
             ('Mehrobdan chayon','mehrob.mp3')
           )
           OR (title='O''tkan kunlar' AND text_path='otkan.json')""")
    conn.execute(
        """DELETE FROM content
           WHERE file_path IN (
             'sintel.mp4',
             'jellyfish.mp4',
             'w3sample.mp4',
             'elephants_dream.mp4',
             'tears_of_steel.mp4',
             'big_buck_bunny.mp4',
             'concert.mp3',
             'music2.mp4',
             'mehrob.wav'
           )
           OR text_path IN ('bahor.json','otkan.json')""")
    conn.execute(
        "DELETE FROM ads WHERE title=? AND link_url=?",
        ("Afrosiyob bilan tez va qulay", "https://railway.uz"))
    conn.execute(
        """DELETE FROM sites
           WHERE (name,url) IN (
             ('Rasmiy sayt','https://railway.uz'),
             ('E-Chipta portali','https://chipta.railway.uz'),
             ('Telegram kanal','https://t.me/railway_uz')
           )""")
    conn.execute(
        """DELETE FROM route_stops
           WHERE name IN ('Toshkent','Guliston','Jizzax','Samarqand')
             AND COALESCE(sort_order, -1) BETWEEN 0 AND 3""")
    conn.execute(
        """DELETE FROM route_stops
           WHERE name IN (
             'Toshkent-Janubiy','Jum''a','Kattaqo''rg''on','Zirabuloq',
             'Ziyovuddin','Navoiy','Qiziltepa','Buxoro-1','Jayhun',
             'Hazorasp','Urganch','Xiva'
           )""")
    conn.execute(
        "INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)",
        ("legacy_seed_cleanup_done", "1"))


# --- O'qish funksiyalari (API uchun) ---
def get_content(content_type=None):
    with closing(connect()) as conn:
        if content_type:
            rows = conn.execute(
                "SELECT * FROM content WHERE type=? ORDER BY id", (content_type,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM content ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def content_field_values(field, content_type=None):
    """Mavjud kontentda ishlatilgan qiymatlar ro'yxati (takrorsiz) — admin
    dialogidagi Janr/Tab combo takliflari uchun. `field` faqat ruxsat etilgan
    ustunlardan bo'ladi (SQL inyeksiyasidan himoya)."""
    if field not in ("genre", "category_tab"):
        return []
    sql = (f"SELECT DISTINCT {field} AS v FROM content"
           f" WHERE {field} IS NOT NULL AND TRIM({field}) != ''")
    args = ()
    if content_type:
        sql += " AND type=?"
        args = (content_type,)
    with closing(connect()) as conn:
        rows = conn.execute(sql + " ORDER BY v COLLATE NOCASE", args).fetchall()
    return [r["v"] for r in rows]


def get_content_by_id(content_id):
    with closing(connect()) as conn:
        row = conn.execute("SELECT * FROM content WHERE id=?", (content_id,)).fetchone()
    return dict(row) if row else None


def upsert_kiosk(device_id, **fields):
    """Kiosk heartbeat ma'lumotini yangilaydi (birinchi marta — yaratadi).
    Bir marta ulangan kiosk ro'yxatda DOIM qoladi (oflayn bo'lsa ham)."""
    if not device_id:
        return
    allowed = ("kiosk_no", "room", "ip", "platform", "cached_n",
               "cached_ids", "disk_total", "disk_free", "caching", "last_seen")
    f = {k: v for k, v in fields.items() if k in allowed}
    if not f:
        return
    # Atomik upsert: bir vaqtda kelgan ikki heartbeat (birinchi ulanishda)
    # "UPDATE; bo'lmasa INSERT" naqshida poyga qilib IntegrityError berardi.
    cols = ["device_id", *f.keys()]
    sets = ",".join(f"{k}=excluded.{k}" for k in f)
    with _conn() as c:
        c.execute(
            f"INSERT INTO kiosks ({','.join(cols)})"
            f" VALUES ({','.join('?' * len(cols))})"
            f" ON CONFLICT(device_id) DO UPDATE SET {sets}",
            [device_id, *f.values()])


def get_kiosks():
    """Ro'yxatdan o'tgan barcha kiosklar (admin jadvali uchun)."""
    with closing(connect()) as conn:
        rows = conn.execute(
            "SELECT * FROM kiosks ORDER BY kiosk_no, device_id").fetchall()
    return [dict(r) for r in rows]


def get_kiosk_cache_enabled(device_id):
    """Shu kioskда lokal kesh yoqilganmi (1/0). Noma'lum kiosk — 1 (yoqiq)."""
    if not device_id:
        return 1
    with closing(connect()) as conn:
        row = conn.execute("SELECT cache_enabled FROM kiosks WHERE device_id=?",
                           [device_id]).fetchone()
    if row is None or row["cache_enabled"] is None:
        return 1
    return int(row["cache_enabled"])


def set_kiosk_cache_enabled(device_id, enabled):
    """Admin shu kiosk uchun lokal keshni yoqadi/o'chiradi (xotirasiz kiosklar)."""
    if not device_id:
        return
    with _conn() as c:
        c.execute("UPDATE kiosks SET cache_enabled=? WHERE device_id=?",
                  [1 if enabled else 0, device_id])


def get_ads(active_only=True):
    """Reklamalar. active_only=True — faqat faollari (API), False — barchasi (admin)."""
    sql = "SELECT * FROM ads"
    if active_only:
        sql += " WHERE is_active=1"
    sql += " ORDER BY sort_order, id"
    with closing(connect()) as conn:
        rows = conn.execute(sql).fetchall()
    return [dict(r) for r in rows]


def get_ad_by_id(ad_id):
    with closing(connect()) as conn:
        row = conn.execute("SELECT * FROM ads WHERE id=?", (ad_id,)).fetchone()
    return dict(row) if row else None


def get_sites():
    with closing(connect()) as conn:
        rows = conn.execute("SELECT * FROM sites ORDER BY sort_order, id").fetchall()
    return [dict(r) for r in rows]


def get_route(direction=None):
    """Yo'nalish bekatlari (tartib bo'yicha).

    direction=None — KIOSKDA FAOL yo'nalish (`active_route_direction` sozlamasi,
    standart 0). API va status shu yo'l bilan faolni oladi.
    direction=0/1 — aniq yo'nalish (admin tahrirlash ko'rinishi)."""
    if direction is None:
        direction = effective_direction()
    with closing(connect()) as conn:
        rows = conn.execute(
            "SELECT * FROM route_stops WHERE direction=? "
            "ORDER BY sort_order, id", (direction,)).fetchall()
    return [dict(r) for r in rows]


# --- Faol yo'nalishni aniqlash (qo'lda 0/1 yoki 'auto' — kun+vaqt bo'yicha) ---
def effective_direction(now=None):
    """Kiosklarда hozir ko'rsatiladigan yo'nalish (0=borish, 1=qaytish).

    `active_route_direction` sozlamasi:
      '0'/'1' — admin qo'lda belgilagan;
      'auto'  — jadval + joriy vaqt bo'yicha avtomatik (48 soatlik tsikl)."""
    val = (get_settings().get("active_route_direction") or "0").strip()
    if val == "auto":
        return _auto_direction(now)
    return 1 if val == "1" else 0


def _parse_route_min(s):
    """'HH:MM' yoki 'H.MM' ni yarim tundан minutga aylantiradi (yoki None)."""
    if not s:
        return None
    try:
        h, m = str(s).replace(".", ":").split(":")[:2]
        return int(h) * 60 + int(m)
    except (ValueError, TypeError):
        return None


def _leg_bounds(stops):
    """Yo'nalish uchun (jo'nash_min, kelish_min, davomiylik_min) yoki None.
    Davomiylik yarim tunдан o'tishni hisobga oladi."""
    if len(stops) < 2:
        return None
    dep = _parse_route_min(stops[0].get("departure_time")
                           or stops[0].get("arrival_time"))
    arr = _parse_route_min(stops[-1].get("arrival_time")
                           or stops[-1].get("departure_time"))
    if dep is None or arr is None:
        return None
    return dep, arr, ((arr - dep) % 1440) or 1440


def _route_anchor(dep_b_min, now):
    """Borish jo'nashining mos sana-vaqti (tsikl fazasini aniqlash uchun).
    'route_anchor' sozlamasidan (admin Avto'ni tanlaganда belgilaydi); yo'q
    bo'lsa — bugungi borish jo'nash vaqti (faqat taxminiy)."""
    raw = get_settings().get("route_anchor")
    if raw:
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            pass
    return now.replace(hour=dep_b_min // 60, minute=dep_b_min % 60,
                       second=0, microsecond=0)


def _auto_direction(now=None):
    """Jadval + joriy vaqt bo'yicha faol yo'nalish. 48 soatlik tsikl:
    borish -> Xivada turish -> qaytish -> Toshkentda turish. Anchor (bitta
    borish jo'nashi) qaysi fazada ekanimizni aniqlaydi."""
    b = _leg_bounds(get_route(0))
    q = _leg_bounds(get_route(1))
    if not b or not q:
        return 0      # jadval to'liq emas — xavfsiz standart: borish
    dep_b, arr_b, dur_b = b
    dep_q, arr_q, dur_q = q
    idle_xiva = (dep_q - arr_b) % 1440      # Xivada turish (kelish->qaytish jo'nash)
    idle_tosh = (dep_b - arr_q) % 1440      # Toshkentda turish (kelish->borish jo'nash)
    cycle = dur_b + idle_xiva + dur_q + idle_tosh
    if cycle <= 0:
        return 0
    now = now or datetime.now()
    anchor = _route_anchor(dep_b, now)
    elapsed = ((now - anchor).total_seconds() / 60) % cycle
    if elapsed < dur_b:
        return 0                            # borish yo'lda
    if elapsed < dur_b + idle_xiva + dur_q:
        return 1                            # Xivada turish + qaytish yo'lda
    return 0                                # Toshkentda turish — keyingi borishga


def get_settings():
    with closing(connect()) as conn:
        rows = conn.execute("SELECT key,value FROM settings").fetchall()
    return {r["key"]: r["value"] for r in rows}


# --- Sinov muddati / litsenziya bloki ---
def trial_state(s=None):
    """Sinov muddati holatini qaytaradi (dict). Blok = QO'LDA blok YOKI
    (nazorat yoqiq VA topshirishdan beri trial_days kun o'tgan).

    {enabled, blocked, reason, start, days, end, days_left}
      reason: 'manual' | 'expired' | None."""
    from datetime import date, datetime as _dt, timedelta
    s = s if s is not None else get_settings()
    enabled = (s.get("trial_enabled") or "0") == "1"
    manual = (s.get("trial_blocked") or "0") == "1"
    try:
        days = int(s.get("trial_days") or 0)
    except (TypeError, ValueError):
        days = 0
    start_raw = (s.get("trial_start") or "").strip()
    end = None
    days_left = None
    if start_raw:
        try:
            start = _dt.strptime(start_raw, "%Y-%m-%d").date()
            end = start + timedelta(days=days)
            days_left = (end - date.today()).days
        except ValueError:
            end = None
    expired = bool(enabled and end is not None and date.today() >= end)
    blocked = manual or expired
    return {
        "enabled": enabled,
        "blocked": blocked,
        "reason": "manual" if manual else ("expired" if expired else None),
        "start": start_raw,
        "days": days,
        "end": end.isoformat() if end else None,
        "days_left": days_left,
    }


# --- Yozish funksiyalari (admin oyna uchun) ---
#
# Quyidagi generik helperlar barcha jadvallar uchun INSERT/UPDATE/DELETE'ni
# bitta joyda bajaradi (kod takrorini yo'qotadi). Har jadval faqat ustunlar
# ro'yxati bilan farq qiladi.

CONTENT_COLS = ["type", "title", "author", "genre", "description", "duration",
                "pages", "cover_path", "file_path", "text_path",
                "category_tab", "lang", "lang_group", "cache_enabled",
                "is_recommended", "visible"]
ADS_COLS = ["media_path", "title", "subtitle", "link_url", "duration",
            "interval_min", "start_time", "end_time", "placement",
            "is_active", "sort_order"]
SITE_COLS = ["name", "url", "description", "features", "icon", "sort_order"]
STOP_COLS = ["name", "arrival_time", "departure_time", "latitude", "longitude",
             "distance_km", "sort_order", "direction"]


def _insert(table, cols, data):
    """Berilgan jadvalga yangi qator qo'shadi va yangi id'ni qaytaradi."""
    vals = [data.get(c) for c in cols]
    placeholders = ",".join(["?"] * len(cols))
    with _conn() as c:
        cur = c.execute(
            f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})", vals)
        return cur.lastrowid


def _update(table, row_id, data, allowed):
    """Qatorni yangilaydi (faqat ruxsat etilgan ustunlar — SQL inyeksiyasidan himoya)."""
    data = {k: v for k, v in data.items() if k in allowed}
    if not data:
        return
    sets = ", ".join(f"{k}=?" for k in data)
    with _conn() as c:
        c.execute(f"UPDATE {table} SET {sets} WHERE id=?", (*data.values(), row_id))


def _delete(table, row_id):
    with _conn() as c:
        c.execute(f"DELETE FROM {table} WHERE id=?", (row_id,))


# --- Kontent ---
def add_content(data):
    """Yangi kontent qo'shadi. data — ustun nomi: qiymat dict. id qaytaradi."""
    return _insert("content", CONTENT_COLS, data)


def update_content(content_id, data):
    """Mavjud kontentni yangilaydi (faqat berilgan ustunlar)."""
    _update("content", content_id, data, CONTENT_COLS)


def delete_content(content_id):
    """Kontentni o'chiradi va boshqa hech kim ishlatmaydigan media/muqova/matn
    fayllarini ham diskdan tozalaydi (yetim fayllar to'planib qolmasligi uchun)."""
    item = get_content_by_id(content_id)
    _delete("content", content_id)
    if not item:
        return
    _cleanup_files(item)


def _cleanup_files(item):
    """item'ga tegishli, lekin boshqa kontent ishlatmaydigan fayllarni o'chiradi."""
    targets = [
        (config.MEDIA_DIR, item.get("file_path")),
        (config.COVERS_DIR, item.get("cover_path")),
        (config.BOOKS_DIR, item.get("text_path")),
    ]
    for dir_, name in targets:
        if not name:
            continue
        if _file_in_use(name):
            continue  # boshqa yozuv shu faylga ishora qiladi — qoldiramiz
        path = os.path.join(dir_, name)
        try:
            if os.path.isfile(path):
                os.remove(path)
                log.info("Yetim fayl o'chirildi: %s", path)
        except OSError as e:
            log.warning("Faylni o'chirib bo'lmadi (%s): %s", path, e)


def _file_in_use(name):
    """Berilgan fayl nomi content jadvalida hali ham ishlatilyaptimi?"""
    with closing(connect()) as conn:
        row = conn.execute(
            "SELECT 1 FROM content WHERE file_path=? OR cover_path=? OR text_path=? LIMIT 1",
            (name, name, name)).fetchone()
    return row is not None


# --- Reklama (ads) ---
def add_ad(data):
    return _insert("ads", ADS_COLS, data)


def update_ad(ad_id, data):
    _update("ads", ad_id, data, ADS_COLS)


def delete_ad(ad_id):
    """Reklamani o'chiradi va boshqa reklama ishlatmaydigan media faylini ham
    diskdan tozalaydi (delete_content bilan bir xil — content/ads/ papkasida
    yetim fayllar cheksiz to'planib qolmasin)."""
    item = get_ad_by_id(ad_id)
    _delete("ads", ad_id)
    if not item:
        return
    name = item.get("media_path")
    if not name:
        return
    with closing(connect()) as conn:
        in_use = conn.execute(
            "SELECT 1 FROM ads WHERE media_path=? LIMIT 1", (name,)).fetchone()
    if in_use:
        return   # boshqa reklama shu faylga ishora qiladi — qoldiramiz
    path = os.path.join(config.ADS_DIR, name)
    try:
        if os.path.isfile(path):
            os.remove(path)
            log.info("Yetim reklama fayli o'chirildi: %s", path)
    except OSError as e:
        log.warning("Reklama faylini o'chirib bo'lmadi (%s): %s", path, e)


# --- Saytlar (sites) ---
def add_site(data):
    return _insert("sites", SITE_COLS, data)


def update_site(site_id, data):
    _update("sites", site_id, data, SITE_COLS)


def delete_site(site_id):
    _delete("sites", site_id)


# --- Yo'nalish bekatlari (route_stops) ---
def add_route_stop(data):
    return _insert("route_stops", STOP_COLS, data)


def update_route_stop(stop_id, data):
    _update("route_stops", stop_id, data, STOP_COLS)


def delete_route_stop(stop_id):
    _delete("route_stops", stop_id)


# --- Sozlamalar ---
def set_setting(key, value):
    with _conn() as c:
        c.execute(
            "INSERT INTO settings (key,value) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))


# --- Parol/PIN xeshlash (PBKDF2-SHA256) ---
def hash_secret(plain):
    """Parol/PIN'ni tuzlangan PBKDF2 xeshiga aylantiradi.

    Format: pbkdf2$<iteratsiya>$<salt_hex>$<hash_hex> — bitta satrda saqlanadi,
    verify_secret shu formatni o'qiydi. Hech qayerda ochiq matn saqlanmaydi."""
    import os as _os
    iterations = 100_000
    salt = _os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt, iterations)
    return f"pbkdf2${iterations}${salt.hex()}${dk.hex()}"


def verify_secret(plain, stored):
    """Kiritilgan qiymatni saqlangan xesh bilan timing-safe solishtiradi."""
    try:
        algo, iterations, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"),
                                 bytes.fromhex(salt_hex), int(iterations))
        return hmac.compare_digest(dk.hex(), hash_hex)
    except (AttributeError, ValueError):
        return False


# --- Audit log (admin amallari tarixi) ---
def log_action(action, details=""):
    """Admin amalini tarixga yozadi (kim nimani qachon o'zgartirgani)."""
    try:
        with _conn() as c:
            c.execute("INSERT INTO audit_log (action, details) VALUES (?,?)",
                      (action, str(details)[:500]))
    except Exception:
        log.warning("Audit log yozilmadi: %s", action, exc_info=True)


# --- Foydalanish statistikasi (kioskdan keladi — POST /api/stats) ---
STATS_EVENTS = ("session_start", "session_end", "screen_view", "lang_change",
                "content_open", "ad_play", "qr_route", "site_qr", "sos_open")


def insert_stats(device_id, events):
    """Kioskdan kelgan event to'plamini saqlaydi. Noma'lum/buzilgan yozuvlar
    jim tashlanadi (kiosk eski/yangi versiyada bo'lishi mumkin). Saqlangan
    yozuvlar sonini qaytaradi."""
    import json as _json
    rows = []
    for ev in events:
        if not isinstance(ev, dict):
            continue
        name = str(ev.get("event") or "")[:40]
        if name not in STATS_EVENTS:
            continue
        rows.append((str(device_id or "")[:64],
                     str(ev.get("session") or "")[:32],
                     str(ev.get("ts") or "")[:32],
                     name,
                     _json.dumps(ev.get("data") or {}, ensure_ascii=False,
                                 default=str)[:1000]))
    if not rows:
        return 0
    with _conn() as c:
        c.executemany(
            "INSERT INTO stats_events (device_id,session,ts,event,data)"
            " VALUES (?,?,?,?,?)", rows)
    return len(rows)


def _stats_since(days):
    """Oxirgi `days` kunni qoplaydigan ISO sana chegarasi (ts bilan string
    solishtiriladi — ts ISO formatda, leksikografik tartib to'g'ri ishlaydi)."""
    from datetime import datetime, timedelta
    return (datetime.now() - timedelta(days=days - 1)).strftime("%Y-%m-%d")


# data.<key> bo'yicha TOP so'rovlar uchun ruxsat etilgan kalitlar oq ro'yxati.
# json_extract yo'liga `key` to'g'ridan-to'g'ri qo'yilgani uchun (parametr
# bo'lolmaydi) SQL inyeksiyasidan himoya — faqat shu kalitlar ruxsat etiladi.
STATS_TOP_KEYS = ("title", "screen", "ad_id", "site", "lang", "type",
                  "content_id", "route", "stop")


def stats_daily_sessions(days=7):
    """Kunlik sessiyalar: [{day, sessions, avg_s}] (session_end bo'yicha)."""
    with closing(connect()) as conn:
        rows = conn.execute(
            """SELECT substr(ts,1,10) AS day, COUNT(*) AS sessions,
                      CAST(AVG(json_extract(data,'$.duration_s')) AS INTEGER) AS avg_s
               FROM stats_events
               WHERE event='session_end' AND ts >= ?
               GROUP BY day ORDER BY day DESC""", (_stats_since(days),)).fetchall()
    return [dict(r) for r in rows]


def stats_top(event, key, days=7, limit=10):
    """Berilgan event ichidagi data.<key> bo'yicha TOP ro'yxat:
    [{name, n}] — masalan content_open/title yoki screen_view/screen."""
    if key not in STATS_TOP_KEYS:
        raise ValueError(f"stats_top: ruxsat etilmagan key: {key!r}")
    with closing(connect()) as conn:
        rows = conn.execute(
            f"""SELECT json_extract(data,'$.{key}') AS name, COUNT(*) AS n
                FROM stats_events
                WHERE event=? AND ts >= ? AND name IS NOT NULL
                GROUP BY name ORDER BY n DESC LIMIT ?""",
            (event, _stats_since(days), limit)).fetchall()
    return [dict(r) for r in rows]


def stats_event_count(event, days=7):
    """Bitta event turining umumiy soni (SOS, QR kabi yagona ko'rsatkichlar)."""
    with closing(connect()) as conn:
        return conn.execute(
            "SELECT COUNT(*) AS n FROM stats_events WHERE event=? AND ts >= ?",
            (event, _stats_since(days))).fetchone()["n"]


def stats_hourly(days=7):
    """Soatlik faollik (peak hours): [{hr, n}] — eng gavjum soat birinchi.
    screen_view (ekran navigatsiyasi) bo'yicha hisoblanadi."""
    with closing(connect()) as conn:
        rows = conn.execute(
            "SELECT substr(ts,12,2) AS hr, COUNT(*) AS n FROM stats_events "
            "WHERE event='screen_view' AND ts >= ? AND length(ts) >= 13 "
            "GROUP BY hr ORDER BY n DESC", (_stats_since(days),)).fetchall()
    return [dict(r) for r in rows]


def stats_by_kiosk(days=7):
    """Kiosk bo'yicha sessiyalar: [{dev, n}] — eng faol kiosk birinchi."""
    with closing(connect()) as conn:
        rows = conn.execute(
            "SELECT device_id AS dev, COUNT(*) AS n FROM stats_events "
            "WHERE event='session_end' AND ts >= ? AND device_id IS NOT NULL "
            "AND device_id != '' GROUP BY device_id ORDER BY n DESC",
            (_stats_since(days),)).fetchall()
    return [dict(r) for r in rows]


def clear_stats():
    """Barcha foydalanish statistikasini o'chiradi (hisoblarni 0 ga tushiradi)."""
    with _conn() as c:
        c.execute("DELETE FROM stats_events")


def stats_totals(days=7):
    """Umumiy hisoblar: {sessions, content_opens, ad_plays, devices}."""
    since = _stats_since(days)
    with closing(connect()) as conn:
        def _count(ev):
            return conn.execute(
                "SELECT COUNT(*) AS n FROM stats_events WHERE event=? AND ts >= ?",
                (ev, since)).fetchone()["n"]

        return {
            "sessions": _count("session_end"),
            "content_opens": _count("content_open"),
            "ad_plays": _count("ad_play"),
            "devices": conn.execute(
                "SELECT COUNT(DISTINCT device_id) AS n FROM stats_events"
                " WHERE ts >= ?", (since,)).fetchone()["n"],
        }


# --- API kalit (kiosk <-> server autentifikatsiyasi) ---
def get_or_create_api_key():
    """Settings'dagi api_key'ni qaytaradi; yo'q bo'lsa yangisini yaratadi.

    Bitta umumiy kalit: server birinchi ishga tushganda generatsiya qilinadi,
    operator uni admin oynasidan ko'chirib kiosk o'rnatuvchisiga kiritadi.
    Kalitsiz so'rovlar 401 oladi (LAN'dagi begona qurilmalardan himoya)."""
    key = get_settings().get("api_key")
    if not key:
        key = secrets.token_urlsafe(24)
        set_setting("api_key", key)
        log.info("Yangi API kalit yaratildi (admin oynasida ko'rinadi)")
    return key
