# Kiosk — Server (admin) dasturi

Poyezd kiosk tizimining **server qismi**: kontent katalogini boshqaradi, media striming
qiladi (HTTP Range bilan), kiosklarni real vaqtda kuzatadi va PyQt6 admin oyna orqali
boshqariladi. Loyihaning umumiy tavsifi — ildizdagi [README.md](../README.md).

## Ishga tushirish (desktop admin — asosiy yo'l)

```bash
pip install -r requirements.txt
python main.py
```

`main.py` ishga tushganda FastAPI backendni o'z ichida (fon oqimda) ko'taradi va admin
oynasini ko'rsatadi. Birinchi ishga tushishda:
- `data.db` (SQLite) yaratiladi va demo kontent bilan to'ldiriladi;
- Ed25519 imzo kaliti va self-signed TLS sertifikat yaratiladi (`security.py`);
- LANga imzolangan UDP beacon tarqatiladi (kiosklar serverni avtomatik topadi).

Server `https://0.0.0.0:8765` da ishlaydi (portni `KIOSK_PORT`, TLSni `KIOSK_TLS=0`
bilan o'zgartirish mumkin).

**Admin oyna tablari:** Boshqaruv (ulangan kiosklar, e'lon yuborish, API kalit),
Kontent, Reklama, Saytlar, Bekatlar, Statistika, Kesh, Sozlamalar.

## Faqat backend (sinov uchun, oynasiz)

```bash
KIOSK_TLS=0 python -c "import uvicorn; uvicorn.run('main:app', host='0.0.0.0', port=8765)"
```

## Demo / yo'nalish / xarita tiklash (tools/)

```bash
python tools/seed_demo.py          # demo media/kitob/reklama
python tools/seed_route_xiva.py    # 076Ф Xiva yo'nalishi jadvali
python tools/fetch_map_assets.py   # oflayn xarita assetlari (MapLibre + PMTiles)
```

## Endpointlar

Barcha `/api/*` API kalit talab qiladi (`X-API-Key` header yoki `?k=` query param);
`/api/health` ochiq. To'liq jadval — ildizdagi [README.md](../README.md#rest--websocket-api).

| Metod va yo'l | Vazifasi |
|---|---|
| `GET /api/health` | server tirikligi (kalitsiz) |
| `GET /api/content[?type=movie]` | ko'rinadigan katalog |
| `GET /api/content/{id}` · `/cover` | bitta kontent · muqova (yo'q bo'lsa SVG) |
| `GET /api/stream/{id}` | video/audio striming (HTTP Range, 206/416, ETag) |
| `GET /api/book/{id}/text` | kitob matni (boblar) |
| `GET /api/ads` · `/ads/{id}/media` | reklama ro'yxati + fayli |
| `GET /api/sites` · `/route` · `/settings` · `/status` | saytlar, yo'nalish, sozlamalar, holat |
| `POST /api/heartbeat` · `/stats` | kiosk holati · foydalanish eventlari |
| `WS /ws?k=...` | real vaqt: status, e'lon, sinx, kesh buyruqlari |

## Tuzilma

- `main.py` — FastAPI ilova va barcha endpointlar; xavfsiz Range tahlili, path-traversal himoyasi (`_safe_join`), joriy bekat/tezlik hisoblash (yarim tundan o'tadigan reyslar ham), `status_payload` (REST + WS).
- `config.py` — yo'llar, port, TLS va discovery sozlamalari.
- `db.py` — SQLite sxema (content, ads, sites, settings, route_stops, kiosks, audit_log, stats_events) + demo seed + generik CRUD; kontent o'chirilganda yetim fayllar tozalanadi; WAL rejimi.
- `security.py` — Ed25519 imzo kaliti + self-signed TLS sertifikat (bir marta yaratiladi, fingerprint o'zgarmaydi); `trust_bundle()` kiosklarga faqat ochiq material beradi.
- `discovery.py` — imzolangan UDP beacon (server-topish).
- `ws.py` — WebSocket connection manager (broadcast, ro'yxat).
- `weather.py` — internet ob-havo keshi (joriy bekat hududi bo'yicha harorat).
- `ui/` — PyQt6 admin oyna: `window.py`, `login.py` (parol hash + audit), `pages/` (dashboard, content, ads, stats, settings, cache, crud), `mapserver.py` (lokal PMTiles Range-server), `server_thread.py` (backendni fon oqimda ko'taradi).
- `tools/` — seed va asset yuklash skriptlari.
- `assets/` — ikonkalar, oflayn xarita (PMTiles, fontlar, MapLibre), `uz_stations.json`.
- `content/` — `media/`, `covers/`, `books/`, `ads/` (admin to'ldiradi; git'ga tushmaydi).

## Build (Windows)

```bash
pyinstaller kiosk_server.spec        # -> dist/KioskServer/
# so'ng installer.iss ni Inno Setup bilan  -> Output/KioskServerSetup.exe
```

## Eslatma

- Demo seed'dagi ba'zi `file_path` haqiqiy fayllarga ishora qiladi — ular `content/media/`
  ga qo'yilmaguncha `/api/stream/{id}` 404 qaytaradi. Muqovalar fayl bo'lmasa ham
  dinamik SVG sifatida ishlaydi.
- Maxfiy kalitlar (`signing_key.pem`, `server_*.pem`) va `data.db` git'ga tushmaydi —
  birinchi ishga tushishda qayta yaratiladi.
