#!/usr/bin/env python3
"""
sender.py — Kontentni NISHON serverga qo'shib yuboruvchi (MANBA kompyuterda).

Ishlash tartibi (xavfsiz "qo'shish" rejimi):
  1. Nishonga ulanadi (receiver.ps1 bergan --host/--port/--token).
  2. Nishon serverini to'xtatadi (data.db lock'ini bo'shatish).
  3. Nishonning data.db'sini oladi.
  4. Bizning content/ads/sites/route_stops yozuvlarini unga QO'SHADI (dublikatsiz).
     Nishonning api_key / litsenziya / kiosklar / statistikasi SAQLANADI.
  5. Yetishmayotgan content/ media fayllarini yuklaydi (bor bo'lsa o'tkazadi).
  6. Yangilangan data.db'ni yuklaydi (oxirida — fayllar joyida bo'lgach).
  7. Nishon serverini qayta ishga tushiradi.

Qayta ishga tushirilса — dublikat yaratmaydi, mavjud fayllarni o'tkazadi (resume).

Foydalanish:
  py -3 sender.py --host 192.168.1.50 --port 8799 --token abc123...
"""
import argparse
import hashlib
import json
import os
import socket
import sqlite3
import sys
import tempfile

# Nishon bazasiga QO'SHILADIGAN jadvallar va dublikatni aniqlash uchun
# "tabiiy kalit" ustunlari. Boshqa jadvallar (settings, kiosks, audit_log,
# stats_events) TEGILMAYDI — nishonники saqlanadi.
TABLES = {
    "content":     ["type", "title", "file_path", "text_path", "lang"],
    "ads":         ["title", "media_path"],
    "sites":       ["name", "url"],
    "route_stops": ["name", "arrival_time", "departure_time",
                    "direction", "sort_order"],
}

CHUNK = 1024 * 1024


def _sha256_file(path):
    """Lokal faylning SHA-256 xeshi (receiver'ning `hash` buyrug'i bilan mos)."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Protokol (TCP) mijoz tomoni — har buyruq uchun yangi ulanish
# ---------------------------------------------------------------------------
def _connect(cfg):
    s = socket.create_connection((cfg.host, cfg.port), timeout=30)
    s.settimeout(600)
    return s


def _send_header(sock, obj):
    data = (json.dumps(obj) + "\n").encode("utf-8")
    sock.sendall(data)


def _recv_line(sock):
    buf = bytearray()
    while True:
        b = sock.recv(1)
        if not b:
            break
        if b == b"\n":
            break
        if b != b"\r":
            buf += b
    return buf.decode("utf-8")


def _recv_exact(sock, n):
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(min(CHUNK, n - len(buf)))
        if not chunk:
            raise IOError("ulanish uzildi (qabulda)")
        buf += chunk
    return bytes(buf)


def _resp(sock):
    line = _recv_line(sock)
    if not line:
        raise IOError("javob yo'q")
    r = json.loads(line)
    if not r.get("ok"):
        raise RuntimeError("nishon xatosi: " + str(r.get("error")))
    return r


def cmd(cfg, obj):
    """Payload'siz oddiy buyruq."""
    obj["token"] = cfg.token
    s = _connect(cfg)
    try:
        _send_header(s, obj)
        return _resp(s)
    finally:
        s.close()


def cmd_get_db(cfg, out_path):
    s = _connect(cfg)
    try:
        _send_header(s, {"token": cfg.token, "cmd": "get_db"})
        r = _resp(s)
        size = int(r.get("size", 0))
        if size == 0:
            return 0
        with open(out_path, "wb") as f:
            remaining = size
            while remaining > 0:
                chunk = s.recv(min(CHUNK, remaining))
                if not chunk:
                    raise IOError("ulanish uzildi (baza yuklab olishda)")
                f.write(chunk)
                remaining -= len(chunk)
        return size
    finally:
        s.close()


def cmd_manifest(cfg):
    s = _connect(cfg)
    try:
        _send_header(s, {"token": cfg.token, "cmd": "manifest"})
        r = _resp(s)
        size = int(r.get("size", 0))
        raw = _recv_exact(s, size) if size else b"{}"
        return json.loads(raw.decode("utf-8"))
    finally:
        s.close()


def cmd_put(cfg, rel, local_path, label=None):
    size = os.path.getsize(local_path)
    s = _connect(cfg)
    try:
        _send_header(s, {"token": cfg.token, "cmd": "put",
                         "path": rel, "size": size})
        sent = 0
        name = label or rel
        with open(local_path, "rb") as f:
            while True:
                chunk = f.read(CHUNK)
                if not chunk:
                    break
                s.sendall(chunk)
                sent += len(chunk)
                if size > 5 * CHUNK:
                    pct = sent * 100 // size
                    sys.stdout.write(
                        f"\r    {name}: {pct:3d}% "
                        f"({sent // CHUNK}/{size // CHUNK} MB)")
                    sys.stdout.flush()
        if size > 5 * CHUNK:
            sys.stdout.write("\n")
        return _resp(s)
    finally:
        s.close()


# ---------------------------------------------------------------------------
# Baza birlashtirish (merge)
# ---------------------------------------------------------------------------
def _cols(conn, table):
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]


def _schema_from(src):
    """Manba bazadan CREATE TABLE/INDEX'larni oladi (yangi bo'sh nishon uchun)."""
    rows = src.execute(
        "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL "
        "AND name NOT LIKE 'sqlite_%'").fetchall()
    return [r[0] for r in rows]


def merge_db(source_db, target_db, fresh):
    """Manba kontentini nishon bazasiga qo'shadi. Qo'shilgan yozuvlar sonini
    (jadval bo'yicha) qaytaradi."""
    src = sqlite3.connect(source_db)
    src.row_factory = sqlite3.Row
    tgt = sqlite3.connect(target_db)

    if fresh:
        # Nishonda baza yo'q edi — manba sxemasini quyamiz (settings'siz).
        for stmt in _schema_from(src):
            try:
                tgt.executescript(stmt + ";")
            except sqlite3.OperationalError:
                pass

    added = {}
    for table, natural in TABLES.items():
        try:
            src_cols = _cols(src, table)
            tgt_cols = _cols(tgt, table)
        except sqlite3.OperationalError:
            continue
        if not src_cols or not tgt_cols:
            continue
        cols = [c for c in src_cols if c in tgt_cols and c != "id"]
        nat = [c for c in natural if c in cols]
        if not nat:
            nat = cols

        # Nishonda mavjud tabiiy kalitlar
        existing = set()
        for row in tgt.execute(
                f"SELECT {','.join(nat)} FROM {table}"):
            existing.add(tuple(row))

        # content uchun lang_group'ni nishon bilan to'qnashmasligi uchun surish
        offset = 0
        has_lang_group = table == "content" and "lang_group" in cols
        if has_lang_group:
            mx = tgt.execute(
                "SELECT MAX(lang_group) FROM content").fetchone()[0]
            offset = int(mx) if mx else 0

        placeholders = ",".join(["?"] * len(cols))
        insert_sql = (f"INSERT INTO {table} ({','.join(cols)}) "
                      f"VALUES ({placeholders})")
        n = 0
        for row in src.execute(f"SELECT {','.join(cols)} FROM {table}"):
            d = dict(zip(cols, row))
            key = tuple(d[c] for c in nat)
            if key in existing:
                continue
            if has_lang_group and d.get("lang_group") is not None:
                d["lang_group"] = int(d["lang_group"]) + offset
            tgt.execute(insert_sql, [d[c] for c in cols])
            existing.add(key)
            n += 1
        added[table] = n

    tgt.commit()
    src.close()
    tgt.close()
    return added


# ---------------------------------------------------------------------------
# Fayllar
# ---------------------------------------------------------------------------
def list_content_files(source_dir):
    """content/ ostidagi barcha fayllar: {rel: (fullpath, size)} (rel 'content/..')."""
    out = {}
    cdir = os.path.join(source_dir, "content")
    for root, _dirs, files in os.walk(cdir):
        for name in files:
            full = os.path.join(root, name)
            rel = os.path.relpath(full, source_dir).replace("\\", "/")
            out[rel] = (full, os.path.getsize(full))
    return out


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True)
    ap.add_argument("--port", type=int, default=8799)
    ap.add_argument("--token", required=True)
    ap.add_argument("--source", default=os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        help="Manba server papkasi (data.db + content/). Standart: server/")
    ap.add_argument("--no-restart", action="store_true",
                    help="Oxirida serverni qayta ishga tushirmaslik")
    ap.add_argument("--verify", action="store_true",
                    help="O'lchami teng fayllarni ham SHA-256 bilan solishtirish"
                         " (bir xil o'lchamli, lekin farqli kontent aniqlanadi;"
                         " sekinroq — nishon har faylni xeshlaydi)")
    cfg = ap.parse_args()

    source_db = os.path.join(cfg.source, "data.db")
    if not os.path.isfile(source_db):
        print(f"XATO: manba baza topilmadi: {source_db}")
        sys.exit(1)

    print(f"Manba papka : {cfg.source}")
    print(f"Nishon      : {cfg.host}:{cfg.port}")

    # 1) Salom / tekshiruv
    hi = cmd(cfg, {"cmd": "hello"})
    print(f"Nishon papka: {hi.get('base')}  "
          f"(baza: {'bor' if hi.get('has_db') else 'yoq'}, "
          f"fayllar: {hi.get('content_files')})")

    # 2) Serverni to'xtatamiz
    print("Nishon serveri to'xtatilmoqda...")
    cmd(cfg, {"cmd": "stop"})

    # 3) Nishon bazasini olamiz
    tmpdir = tempfile.mkdtemp(prefix="kiosk_sync_")
    target_db = os.path.join(tmpdir, "target.db")
    print("Nishon bazasi olinmoqda...")
    dl = cmd_get_db(cfg, target_db)
    fresh = dl == 0
    if fresh:
        print("  Nishonda baza yo'q — yangisi (manba sxemasi bilan) yaratiladi.")

    # 4) Birlashtirish
    print("Kontent birlashtirilmoqda (dublikatsiz)...")
    added = merge_db(source_db, target_db, fresh)
    for t, n in added.items():
        print(f"  + {t}: {n} ta yangi yozuv")
    total_added = sum(added.values())

    # 5) Yetishmayotgan media fayllarini yuklaymiz
    print("Fayllar solishtirilmoqda...")
    manifest = cmd_manifest(cfg)
    local = list_content_files(cfg.source)
    to_send = []
    for rel, (full, size) in sorted(local.items()):
        if manifest.get(rel) != size:
            to_send.append((rel, full, size))
        elif cfg.verify:
            # O'lcham teng — --verify rejimida kontentni SHA-256 bilan ham
            # tekshiramiz (qayta kodlangan/buzilgan fayl "bor" deb qolmasin).
            remote_hash = cmd(cfg, {"cmd": "hash", "path": rel}).get("sha256")
            if remote_hash != _sha256_file(full):
                print(f"  ! hash farqi: {rel} — qayta yuklanadi")
                to_send.append((rel, full, size))
    skipped = len(local) - len(to_send)
    total_bytes = sum(s for _, _, s in to_send)
    print(f"  Jami: {len(local)} | yuklanadi: {len(to_send)} "
          f"| o'tkazildi: {skipped} | hajm: {total_bytes / (1024**3):.2f} GB")

    for i, (rel, full, size) in enumerate(to_send, 1):
        print(f"  [{i}/{len(to_send)}] {rel}  ({size / (1024**2):.1f} MB)")
        cmd_put(cfg, rel, full, label=os.path.basename(rel))

    # 6) Yangilangan bazani yuklaymiz (oxirida)
    print("Yangilangan baza yuklanmoqda...")
    cmd_put(cfg, "data.db", target_db, label="data.db")

    # 7) Serverni qayta ishga tushiramiz
    if not cfg.no_restart:
        print("Nishon serveri qayta ishga tushirilmoqda...")
        cmd(cfg, {"cmd": "start"})

    print("")
    print(f"TAYYOR. {total_added} ta yangi yozuv qo'shildi, "
          f"{len(to_send)} ta fayl yuklandi.")


if __name__ == "__main__":
    main()
