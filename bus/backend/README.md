# Avtobus backend (`bus/backend/`)

Headless FastAPI serveri — avtobus qurilmasida (mini-PC/Pi) ishlaydi, yo'lovchi
telefoniga kontent/striming/xaritani beradi va KioskCloud bulutiga chiquvchi WSS
bilan ulanadi. **PyQt yo'q** (poyezd `server/` backend'idan olingan, kiosksiz).

> Tuzilma **tekis** (bitta papkada modullar) — bu servis hajmiga mos va Python
> uchun odatiy ("flat is better than nested"). Har modul bitta aniq vazifa
> bajaradi (quyida). Ishga tushirish: `python main.py` (yoki Docker — `../README.md`).

## Modullar (qaysi fayl nima qiladi)

| Fayl | Vazifasi | Qator |
|---|---|---|
| **main.py** | FastAPI ilova + BARCHA marshrutlar (`/api/content`, `/api/stream/{id}`, `/api/ads`, `/api/status`, `/ws`, ...) + blok-gate (`_blocked_now`) + `_safe_join` (path himoyasi) | ~740 |
| **config.py** | Muhit o'zgaruvchilari (`KIOSK_*`): port, TLS, vertical=bus, bulut URL, API kalit, kesh | ~120 |
| **db.py** | SQLite (WAL): kontent, reklama, sozlama, bekat, statistika. Barcha so'rovlar **parametrli** | ~1150 |
| **cloud_client.py** | Bulut agenti: enroll → manifest tortish → **Ed25519-imzolangan buyruqlar** → statistika/log yuborish | ~1080 |
| **ws.py** | Real-vaqt WebSocket (`/ws`) — status/e'lon broadcast | ~180 |
| **security.py** | Ed25519 imzo tekshiruvi, parol xesh, `compare_digest` (timing-safe) | ~285 |
| **licensing.py** | Hardware-bog'langan litsenziya (`hardware_id`, imzo tekshiruvi, muddat) | ~245 |
| **media_tools.py** | Video "faststart" remux (ffmpeg — `subprocess` list-form, `shell=True` YO'Q) | ~100 |
| **discovery.py** | LAN beacon (avtobusда O'CHIQ — `KIOSK_DISCOVERY=0`, kiosk yo'q) | ~100 |
| **weather.py** | Ob-havo keshi (bosh sahifa kartasi uchun) | ~185 |

## Ma'lumot va sozlama

- **Baza + kontent**: `KIOSK_DB` (`/data/data.db`) + `KIOSK_CONTENT` (`/data/content`)
  — Docker'da `busdata` volume'да (oflayn kesh, konteyner qayta qurilса saqlanadi).
- **Sozlama = `.env`** (`../.env`), kodда qattiq yozilmaydi. Sirlar git/docker-ignore.
- **Vertical**: `KIOSK_VERTICAL=bus` — bulutga enroll'да yuboriladi, panel yorliqlari
  shunga qarab moslanadi (Vagon→Avtobus va h.k.).

## Xavfsizlik chegaralari (backend dasturchi bilishi shart)

- **API kalit** (`?k=` yoki `X-API-Key`) — `/api*` ni himoyalaydi (`compare_digest`).
  Yo'lovchi kontenti ochiq, sozlama/stat/WS-register kalit talab qiladi.
- **`_safe_join`** — foydalanuvchi bergan fayl nomидан yo'l tuzganда path-traversal
  (`../`, absolyut, disk) ni bloklaydi. Media/cover/stream/book/map shundan o'tadi.
- **Blok-gate `_blocked_now()`** — litsenziya/qo'lda-blok/texnik rejimда kontent
  endpointlari bo'sh/403 qaytaradi (avtobus web-only bo'lgani uchun).
- **Bulut buyruqlari** — har biri Ed25519 tekshiriladi; `set_settings` faqat
  `REMOTE_SETTINGS` oq ro'yxatiga tegadi (`api_key`/parol/token EMAS).

## Poyezd `server/` bilan farqi

Bu backend `server/` dan olingan, lekin: kiosk-mijoz yo'q, PyQt yo'q, LAN discovery
o'chiq, TLS o'rniga ichki HTTP (Docker/Caddy ortida). Kontent modeli bir xil,
shuning uchun bulut avtobusni oddiy server sifatida ko'radi.
