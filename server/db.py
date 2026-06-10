"""
db.py — SQLite baza bilan ishlash (TZ 10-bo'lim sxemasi).

Jadvallar: content, ads, sites, settings, route_stops.
Birinchi ishga tushishda baza yaratiladi va test kontent bilan to'ldiriladi
(2-bosqich "tayyor mezoni" — /api/content ro'yxat bersin).
"""
import sqlite3
import os
import logging
from contextlib import contextmanager

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
    is_recommended INTEGER DEFAULT 0,
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
    sort_order     INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS audit_log (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ts      TEXT DEFAULT (datetime('now','localtime')),
    action  TEXT NOT NULL,
    details TEXT
);
"""


def init_db():
    """Bazani yaratadi va bo'sh bo'lsa test ma'lumot bilan to'ldiradi."""
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
        conn.commit()
        # Bo'sh bo'lsa seed qilamiz
        if conn.execute("SELECT COUNT(*) AS n FROM content").fetchone()["n"] == 0:
            _seed(conn)
        conn.commit()
    finally:
        conn.close()   # xato bo'lsa ham ulanish (handle) oqib qolmasin


def _seed(conn):
    """Boshlang'ich test ma'lumotlari (admin keyinroq haqiqiysini qo'shadi)."""
    content = [
        # type, title, author, genre, description, duration, pages, cover, file, text, tab, rec
        ("movie",  "Baron", None, "Kriminal, Ekshn",
         "O'zbek kriminal dramasi.", 6600, None,
         "baron.svg", "baron.mp4", None, "Kinolar", 1),
        ("movie",  "Sarob", None, "Drama",
         "Hayotiy drama filmi.", 5400, None,
         "sarob.svg", "sarob.mp4", None, "Kinolar", 0),
        ("cartoon", "Zumrad va Qimmat", None, "Multfilm",
         "Bolalar uchun multfilm.", 3600, None,
         "zumrad.svg", "zumrad.mp4", None, "Multfilmlar", 0),
        ("music",  "Yulduz Usmonova — Konsert", "Yulduz Usmonova", "Konsert",
         "Jonli konsert yozuvi.", 7200, None,
         "concert.svg", "concert.mp4", None, "Musiqa", 0),
        ("book",   "O'tkan kunlar", "Abdulla Qodiriy", "Badiiy",
         "O'zbek adabiyotining durdona asari.", None, 560,
         "otkan.svg", None, "otkan.json", "Badiiy", 1),
        ("audiobook", "Mehrobdan chayon", "Abdulla Qodiriy", "Badiiy",
         "Audiokitob ko'rinishida.", 18000, None,
         "mehrob.svg", "mehrob.mp3", None, "Badiiy", 0),
    ]
    conn.executemany(
        """INSERT INTO content
           (type,title,author,genre,description,duration,pages,
            cover_path,file_path,text_path,category_tab,is_recommended)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", content)

    conn.executemany(
        "INSERT INTO ads (image_path,title,subtitle,link_url,is_active,sort_order) VALUES (?,?,?,?,?,?)",
        [("ad1.jpg", "Afrosiyob bilan tez va qulay",
          "Toshkent — Samarqand 2 soatda", "https://railway.uz", 1, 0)])

    conn.executemany(
        "INSERT INTO sites (name,url,description,features,icon,sort_order) VALUES (?,?,?,?,?,?)",
        [
            ("Rasmiy sayt", "https://railway.uz",
             "O'zbekiston temir yo'llari rasmiy sayti",
             "Jadval; Online chipta; Shaxsiy kabinet; Poyezd holati", "globe", 0),
            ("E-Chipta portali", "https://chipta.railway.uz",
             "Onlayn chipta xarid qilish", "Chipta sotib olish; Qaytarish", "globe", 1),
            ("Telegram kanal", "https://t.me/railway_uz",
             "Yangiliklar va e'lonlar", "Yangiliklar; Aksiyalar", "globe", 2),
        ])

    conn.executemany(
        "INSERT INTO settings (key,value) VALUES (?,?)",
        [
            ("wagon_number", "6"),
            ("wagon_note", "Restoran vagonning chap tarafida"),
            ("train_name", "AFROSIYOB 764"),
            ("route", "Toshkent → Samarqand"),
            ("depart_time", "08:00"),
            ("duration", "2s 45d"),
            ("default_theme", "light"),
        ])

    conn.executemany(
        "INSERT INTO route_stops (name,arrival_time,latitude,longitude,sort_order) VALUES (?,?,?,?,?)",
        [
            ("Toshkent",  "08:00", 41.2995, 69.2401, 0),
            ("Guliston",  "08:30", 40.4897, 68.7842, 1),
            ("Jizzax",    "09:10", 40.1158, 67.8422, 2),
            ("Samarqand", "10:00", 39.6542, 66.9597, 3),
        ])


# --- O'qish funksiyalari (API uchun) ---
def get_content(content_type=None):
    conn = connect()
    if content_type:
        rows = conn.execute(
            "SELECT * FROM content WHERE type=? ORDER BY id", (content_type,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM content ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_content_by_id(content_id):
    conn = connect()
    row = conn.execute("SELECT * FROM content WHERE id=?", (content_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_ads(active_only=True):
    """Reklamalar. active_only=True — faqat faollari (API), False — barchasi (admin)."""
    conn = connect()
    sql = "SELECT * FROM ads"
    if active_only:
        sql += " WHERE is_active=1"
    sql += " ORDER BY sort_order, id"
    rows = conn.execute(sql).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_ad_by_id(ad_id):
    conn = connect()
    row = conn.execute("SELECT * FROM ads WHERE id=?", (ad_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_sites():
    conn = connect()
    rows = conn.execute("SELECT * FROM sites ORDER BY sort_order, id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_route():
    conn = connect()
    rows = conn.execute("SELECT * FROM route_stops ORDER BY sort_order, id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_settings():
    conn = connect()
    rows = conn.execute("SELECT key,value FROM settings").fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


# --- Yozish funksiyalari (admin oyna uchun) ---
#
# Quyidagi generik helperlar barcha jadvallar uchun INSERT/UPDATE/DELETE'ni
# bitta joyda bajaradi (kod takrorini yo'qotadi). Har jadval faqat ustunlar
# ro'yxati bilan farq qiladi.

CONTENT_COLS = ["type", "title", "author", "genre", "description", "duration",
                "pages", "cover_path", "file_path", "text_path",
                "category_tab", "is_recommended"]
ADS_COLS = ["media_path", "title", "subtitle", "link_url", "duration",
            "interval_min", "start_time", "end_time", "is_active", "sort_order"]
SITE_COLS = ["name", "url", "description", "features", "icon", "sort_order"]
STOP_COLS = ["name", "arrival_time", "departure_time", "latitude", "longitude",
             "distance_km", "sort_order"]


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
    conn = connect()
    row = conn.execute(
        "SELECT 1 FROM content WHERE file_path=? OR cover_path=? OR text_path=? LIMIT 1",
        (name, name, name)).fetchone()
    conn.close()
    return row is not None


# --- Reklama (ads) ---
def add_ad(data):
    return _insert("ads", ADS_COLS, data)


def update_ad(ad_id, data):
    _update("ads", ad_id, data, ADS_COLS)


def delete_ad(ad_id):
    _delete("ads", ad_id)


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
    import hashlib
    import os as _os
    iterations = 100_000
    salt = _os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt, iterations)
    return f"pbkdf2${iterations}${salt.hex()}${dk.hex()}"


def verify_secret(plain, stored):
    """Kiritilgan qiymatni saqlangan xesh bilan timing-safe solishtiradi."""
    import hashlib
    import hmac
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


# --- API kalit (kiosk <-> server autentifikatsiyasi) ---
def get_or_create_api_key():
    """Settings'dagi api_key'ni qaytaradi; yo'q bo'lsa yangisini yaratadi.

    Bitta umumiy kalit: server birinchi ishga tushganda generatsiya qilinadi,
    operator uni admin oynasidan ko'chirib kiosk o'rnatuvchisiga kiritadi.
    Kalitsiz so'rovlar 401 oladi (LAN'dagi begona qurilmalardan himoya)."""
    import secrets
    key = get_settings().get("api_key")
    if not key:
        key = secrets.token_urlsafe(24)
        set_setting("api_key", key)
        log.info("Yangi API kalit yaratildi (admin oynasida ko'rinadi)")
    return key
