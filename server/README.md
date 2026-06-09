# Kiosk — Server (admin) dasturi

Roadmapdagi **2-bosqich** (server poydevori) + **admin desktop oynasi**:
katalog beradi, striming qiladi (HTTP Range bilan), test kontent bilan keladi,
hamda PyQt6 admin oyna orqali boshqariladi.

## Ishga tushirish (desktop admin — asosiy yo'l)
```bash
pip install -r requirements.txt
python admin.py
```
`admin.py` — bu **desktop ilova** (`server.exe` bo'ladi). Ishga tushganda
ichida FastAPI backendni avtomatik ko'taradi va admin oynasini ko'rsatadi.
Tablar: **Server** (holat, ulangan kiosklar, e'lon yuborish), **Kontent**,
**Reklama**, **Saytlar**, **Bekatlar** (hammasi qo'shish/tahrirlash/o'chirish),
**Sozlamalar**.

## Faqat backend (ishlab chiqish/sinov uchun)
```bash
python main.py   # oynasiz, faqat API
```
Server `http://0.0.0.0:8765` da ishlaydi (portni `KIOSK_PORT` bilan o'zgartirish
mumkin). Birinchi ishga tushishda `data.db`
avtomatik yaratiladi va test kontent bilan to'ldiriladi.

## Endpointlar (TZ 11.1)
| Metod va yo'l | Vazifasi |
|---|---|
| `GET /api/health` | server tirikligi |
| `GET /api/content[?type=movie]` | katalog ro'yxati |
| `GET /api/content/{id}` | bitta kontent |
| `GET /api/content/{id}/cover` | muqova (fayl yo'q bo'lsa dinamik SVG) |
| `GET /api/stream/{id}` | video/audio striming (Range qo'llab-quvvatlanadi) |
| `GET /api/book/{id}/text` | kitob matni (boblar bilan) |
| `GET /api/ads` `GET /api/sites` `GET /api/route` `GET /api/settings` | qo'shimcha ma'lumotlar |

## Tuzilma
- `config.py` — yo'llar va port sozlamalari.
- `db.py` — SQLite sxema (TZ 10) + test seed + generik CRUD (content, ads,
  sites, route_stops). Kontent o'chirilganda yetim media/muqova/matn fayllari
  ham tozalanadi.
- `main.py` — FastAPI ilova va endpointlar. Striming: xavfsiz Range tahlili
  (suffix/oraliq/ochiq), noto'g'ri oraliqqa 416, ETag/Last-Modified/Cache-Control.
- `admin.py` — PyQt6 desktop admin oynasi (backendni ichida ishga tushiradi).
  Reklama/sayt/bekat tablar bitta umumiy `RecordDialog` + `_crud_tab` orqali.
- `content/media/` — video/audio fayllar (admin yuklaydi).
- `content/covers/` — muqova rasmlar (yo'q bo'lsa SVG generatsiya qilinadi).
- `content/books/` — kitob matnlari (JSON, boblar bilan).
- `data.db` — SQLite baza (avtomatik yaratiladi).

## Eslatma
Test seed'dagi `file_path` (baron.mp4 ...) haqiqiy fayllarga ishora qiladi —
ular `content/media/` ga qo'yilmaguncha `/api/stream/{id}` 404 qaytaradi.
Muqovalar esa fayl bo'lmasa ham dinamik SVG sifatida ishlaydi.
Haqiqiy fayllarni 8-bosqichdagi admin orqali yoki qo'lda joylashtirasiz.

## Holat (Roadmap)
- [x] 2-bosqich: server poydevori (katalog + striming + Range)
- [x] Admin desktop oyna: kontent/reklama/sayt/bekat CRUD + sozlamalar
- [x] 8-bosqich: WebSocket real-time + ulangan kiosklar soni + e'lon yuborish
