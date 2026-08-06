# Kiosk platformasi — arxitektura va tuzilma

Yangi dasturchi uchun **birinchi o'qiladigan** hujjat. Loyiha nima, qaysi qism
qayerda, front↔backend qanday ulanadi, qanday ishga tushiriladi.

## 1. Platforma nima?

Bitta markaziy **bulut (KioskCloud)** dan boshqariladigan, har xil joylarda
(poyezd, avtobus, kafe, market, tashkilot) **lokal ishlaydigan** ko'ngilochar
kiosk/veb tizimi. Yo'lovchi/mijoz o'z telefonidan lokal Wi-Fi orqali kino,
multfilm, musiqa, kitob, xarita va reklamani ko'radi. Internet uzilsa ham lokal
kontent ishlayveradi (oflayn kesh). Bulut kontent/reklama/yo'nalishni tarqatadi,
statistikani yig'adi, qurilmalarni masofadan boshqaradi.

## 2. Komponentlar (repo yuqori darajasi)

| Papka | Nima | Texnologiya | Kim ishlaydi |
|---|---|---|---|
| **`cloud/`** | Markaziy bulut panel — barcha serverlarni boshqaradi | FastAPI (Python) + vanilla-JS SPA | backend + frontend |
| **`server/`** | Poyezd lokal serveri (desktop admin + API) | PyQt6 + FastAPI | backend + desktop |
| **`kiosk/`** | Poyezd kiosk ekrani (vagondagi katta ekran) | PyQt6 | desktop |
| **`web/`** | Poyezd veb versiyasi (poyezd.uz — telefon) | Nuxt 4 SPA | frontend |
| **`bus/`** | **Avtobus vertikali** (web-only, kiosk/desktop yo'q) | FastAPI + Nuxt | backend + frontend |
| **`docs/`** | Dizayn va texnik hujjatlar | — | — |

**Vertikallar:** poyezd = to'liq (kiosk+desktop+web), avtobus = faqat backend+web.
Yangi vertikal (kafe/market) qo'shish uchun `bus/` ni andoza qilib oling.

## 3. Ma'lumot oqimi (front ↔ backend ↔ bulut)

```
┌─ LOKAL QURILMA (poyezd/avtobus) ──────────────┐
│                                                │
│  Yo'lovchi telefon ──HTTP──> Web (Nuxt SPA)   │
│                                 │ Nitro proksi │
│                                 ▼ X-API-Key    │
│                          Backend (FastAPI)     │────chiquvchi WSS───┐
│                          /api, striming, WS    │<──manifest (imzo)──┤
│                          data.db + content/    │                    │
└────────────────────────────────────────────────┘                    ▼
                                                              ┌─ BULUT (cloud/) ─┐
   Bir nechta qurilma (50+ poyezd/avtobus) ───────────────>  │  desired-state   │
                                                              │  manifest,       │
   Admin brauzer ──HTTPS──> Bulut panel (vanilla SPA)  <────  │  Ed25519 imzo,   │
                                                              │  statistika      │
                                                              └──────────────────┘
```

- **Web hech qachon backendga to'g'ridan-to'g'ri kirmaydi** — Nuxt **Nitro server
  qatlami** (`web/server/api/*`) proksi qiladi va `X-API-Key` ni **server tomonда**
  qo'shadi (kalit brauzerga chiqmaydi).
- **Qurilma bulutga CHIQUVCHI WSS** ochadi (`cloud_client.py`) — bulut qurilmага
  kira olmaydi (NAT orqasida bo'lsa ham ishlaydi). Buyruqlar **Ed25519 imzolangan**.
- Bulut faqat **istalgan holat (desired state)** ni beradi; qurilma o'zi tortadi
  (sha256 dedup, oflayn navbat). Statistika qurilmadan bulutga batch bilan boradi.

## 4. Qanday ishga tushiriladi (dev)

**Bulut (cloud/):** — kod `backend/`, frontend `web/`, ishga tushirish `cloud/` dan:
```bash
cd cloud && pip install -r backend/requirements.txt && python backend/main.py   # :9000
```

**Avtobus (bus/) — Docker:**
```bash
cd bus && bash setup.sh          # yoki setup.ps1 (Windows) — savolli o'rnatgich
# yoki qo'lda: docker compose up -d --build   (web :80, backend ichki :8000)
```

**Avtobus — Docker'siz dev:**
```bash
cd bus/backend && python main.py                 # :8000 (headless)
cd bus/web && npm install && npm run dev          # :3000 (Nitro proksi backendga)
```

**Poyezd (server/ + kiosk/):** PyQt desktop — `python server/admin.py`, kiosk
`python kiosk/main.py`. Veb: `cd web && npm run dev`.

## 5. Komponent ichki tuzilmasi

Har birining o'z README'si bor:
- [`cloud/README.md`](cloud/README.md) — bulut panel (FastAPI + SPA)
- [`bus/README.md`](bus/README.md) — avtobus vertikali (deploy + setup)
- `bus/backend/` va `bus/web/` — quyida "Konventsiyalar"ga qarang

### Nuxt web (web/, bus/web/) — standart Nuxt 4 tartibi
```
components/  layout/ (AppHeader) · ui/ (qayta ishlatiladigan) · views/<bo'lim>/
composables/ useAds, useStats, ...        pages/       (marshrutlar)
server/api/  Nitro proksi (resurs bo'yicha: ads.ts, books.ts, cover/[id]...)
server/utils/ backend.ts (X-API-Key), map.ts (tur↔frontend model)
assets/  i18n/locales/  types/app.ts  plugins/
```

### Backend (cloud/, bus/backend/, server/) — FastAPI
- `main.py` — ilova + marshrutlar (yoki `routes/`)
- `db.py` — SQLite (WAL); barcha so'rovlar **parametrli**
- `config.py` — muhit o'zgaruvchilari (`KIOSK_*` / `CLOUD_*`)
- `cloud_client.py` — bulutga WSS agent (enroll, manifest, buyruq)
- `security.py` — Ed25519 imzo/tekshiruv, parol xesh
- `licensing.py` — hardware-bog'langan litsenziya

## 6. Konventsiyalar (yangi dasturchilar uchun)

- **Sozlama = muhit o'zgaruvchisi** (`.env`), kodда qattiq yozilmaydi. Sirlar
  (`.env`, `*.pem`, `*.db`, `content/`, `storage/`) **git'ga tushmaydi**.
- **API kalit faqat server tomonда** (Nitro `runtimeConfig`), brauzerга chiqmaydi.
- **SQL har doim parametrli** (`?` bilan), string-format bilan emas.
- **Fayl yo'llari** foydalanuvchi kiritган nomдан tuzilса — `_safe_join` orqali
  (path traversal himoyasi).
- **Bulut buyruqlari Ed25519 imzolanadi**; tasdiqlanmagan serverга kontent/buyruq
  yuborilmaydi.
- Panel/веб'да server nomi, izoh kabi **server-boshqaradigan matn** HTML'ga
  chiqarilса — `esc()` / escaping bilan (XSS).
- Panel o'zgarganда `cloud/main.py:APP_BUILD` va `static/app.js:UI_BUILD` ni
  **bir xil** qilib oshiring (kesh-bust).

## 7. Katta fayllar (navigatsiya)

Ba'zi fayllar hali monolit — har birining boshida **bo'lim-indeksi/mundarija**
bor (qidiruv uchun). Kelajakda modullarga bo'linadi:
- `cloud/backend/main.py` (~1500 q) — FastAPI marshrutlari (MARSHRUT INDEKSI bor)
- `cloud/backend/db.py` (~1700 q) — barcha DB funksiyalari (BO'LIM INDEKSI bor)
- `cloud/web/app.js` (~3500 q) — panel SPA (MUNDARIJA + raqamlangan bo'limlar)
