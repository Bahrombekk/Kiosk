# Kiosk — poyezd ko'ngilochar tizimi

Poyezd vagonlariga o'rnatiladigan **oflayn ishlay oladigan ko'ngilochar kiosk** tizimi.
Yo'lovchilar sensorli ekrandan kino, multfilm, musiqa, audiokitob va matnli kitoblarni
ko'radi/tinglaydi, safar yo'nalishini xaritada kuzatadi, foydali saytlarga QR kod orqali
o'tadi. Mazmun bitta **server (admin) dasturi** orqali boshqariladi; vagondagi har bir
kiosk shu serverdan kontent oladi va internet bo'lmasa lokal keshdan ishlaydi.

Loyiha ikki mustaqil **PyQt6 desktop ilovasi**dan iborat:

| Qism | Papka | Vazifasi | Build natijasi |
|---|---|---|---|
| **Server (admin)** | [server/](server/) | Kontent katalogini boshqaradi, media striming qiladi, kiosklarni real vaqtda kuzatadi | `KioskServerSetup.exe` |
| **Kiosk (user)** | [user/](user/) | Vagondagi sensorli ekran ilovasi (fullscreen, qulflangan) | `KioskSetup.exe` |

---

## Mundarija

- [Arxitektura](#arxitektura)
- [Asosiy imkoniyatlar](#asosiy-imkoniyatlar)
- [Texnologiyalar](#texnologiyalar)
- [Loyiha tuzilmasi](#loyiha-tuzilmasi)
- [Tez boshlash (ishlab chiqish)](#tez-boshlash-ishlab-chiqish)
- [Sozlash](#sozlash)
- [REST / WebSocket API](#rest--websocket-api)
- [Xavfsizlik](#xavfsizlik)
- [Build va o'rnatish (.exe)](#build-va-ornatish-exe)
- [Kiosk qurilmasini qulflash](#kiosk-qurilmasini-qulflash)
- [Litsenziya / sinov muddati](#litsenziya--sinov-muddati)

---

## Arxitektura

```
                    ┌──────────────────────────────┐
                    │   SERVER (admin) — server/    │
                    │  PyQt6 oyna + FastAPI backend │
                    │  SQLite (data.db) + content/  │
                    └───────────────┬──────────────┘
                                    │  LAN (alohida VLAN/SSID tavsiya etiladi)
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
   imzolangan UDP beacon      HTTPS REST + Range          WSS (real-time)
   (avto server-topish)       (katalog, striming)         (status, e'lon, sinx)
        │                           │                           │
        ▼                           ▼                           ▼
  ┌──────────────┐          ┌──────────────┐          ┌──────────────┐
  │  KIOSK #1    │          │  KIOSK #2    │   ...    │  KIOSK #N     │
  │  user/ ilova │          │  user/ ilova │          │  user/ ilova  │
  │ + lokal kesh │          │ + lokal kesh │          │ + lokal kesh  │
  └──────────────┘          └──────────────┘          └──────────────┘
```

- **Server** ishga tushganda FastAPI backendni o'z ichida ko'taradi (uvicorn), admin
  oynasini ko'rsatadi va LANga imzolangan UDP "beacon" tarqatadi.
- **Kiosk** ishga tushganda beaconni tutib serverni avtomatik topadi (qo'lda IP yozish
  shart emas), TLS sertifikatini "pin" qiladi, katalogni yuklab oladi va media fayllarni
  fonda lokal diskka keshlaydi.
- Internet/server uzilsa kiosk **oflayn rejimga** o'tadi: keshlangan katalog va media
  ishlashda davom etadi, faqat keshlanmagan striming to'xtaydi.

---

## Asosiy imkoniyatlar

### Kiosk (foydalanuvchi) ilovasi
- **5 bo'lim:** Asosiy (status + reklama + tavsiyalar), Xarita (yo'nalish timeline + oflayn vektor xarita), Videolar, Kitoblar, Saytlar.
- **Pleyerlar:** to'liq ekran VLC video pleyer; audiokitob/musiqa pleyeri (to'lqin, playlist, prev/next, tezlik 1×/1.5×/2×); matnli kitob o'quvchi (boblar, sahifalash).
- **Kitob = matn + audio birga:** bitta yozuv ham o'qiladi, ham tinglanadi.
- **3 til:** o'zbek / rus / ingliz — bir tugma bilan almashadi, harakatsizlikdan keyin standart (UZ) tilga qaytadi.
- **Reklama:** asosiy sahifa banneri + qalqib chiquvchi popup (rasm yoki video), vaqt oralig'i va kadans bilan.
- **Real vaqt status:** tezlik, harorat, joriy bekat, vagon — serverdan WebSocket orqali jonli yangilanadi (yarim tundan o'tadigan reyslarda ham joriy bekat to'g'ri).
- **Oflayn xarita:** QtWebEngine + MapLibre + PMTiles, lokal Range-server orqali (internetsiz vektor xarita).
- **Zastavka/screensaver:** ochilish splash + harakatsizlik ekrani.
- **SOS:** favqulodda raqamlar va kiosk joylashuvi modali.
- **Foydalanish statistikasi:** ekran ko'rishlari, sessiyalar diskdagi navbatga yoziladi va davriy serverga yuboriladi (oflaynda yig'ilib turadi).
- **Responsive:** UI monitor o'lchamiga global miqyos (SCALE) bilan moslashadi.

### Server (admin) ilovasi
- **CRUD sahifalari:** Kontent, Reklama, Saytlar, Bekatlar (yo'nalish jadvali), Sozlamalar.
- **Boshqaruv (dashboard):** ulangan kiosklar jadvali (oflaynlar ham ko'rinadi), real-time e'lon yuborish, API kalit.
- **Statistika:** `stats_events` asosida foydalanish hisobotlari.
- **Kesh boshqaruvi:** kioskga "hoziroq yukla" / "keshni tozalash" buyruqlari, kiosk disk holati.
- **Striming:** HTTP Range (206 Partial Content), ETag/Last-Modified, 416 noto'g'ri oraliqqa.
- **Dinamik muqova:** muqova fayli bo'lmasa rang-kodli SVG placeholder generatsiya qilinadi.
- **Internet ob-havo:** joriy bekat hududi bo'yicha haroratni fonda yuklab keshlaydi.

---

## Texnologiyalar

| Soha | Texnologiya |
|---|---|
| UI (ikkala ilova) | **PyQt6** (+ PyQt6-WebEngine — oflayn xarita) |
| Server backend | **FastAPI** + **uvicorn** (WebSocket bilan) |
| Ma'lumotlar bazasi | **SQLite** (WAL rejimi) |
| Media ijro (kiosk) | **python-vlc** (LibVLC — VLC bundle qilinadi) |
| Kriptografiya | **cryptography** — Ed25519 imzo (discovery) + self-signed TLS |
| Real vaqt | WebSocket (status, e'lon, sinx, kesh buyruqlari) |
| QR | **qrcode** (Pillowsiz, matritsa chiziladi) |
| Xarita | MapLibre GL + PMTiles (oflayn vektor tayl) |
| Build | **PyInstaller** + **Inno Setup** (Windows) |

---

## Loyiha tuzilmasi

```
Kiosk/
├── server/                      # SERVER (admin) ilovasi
│   ├── main.py                  # FastAPI ilova + barcha endpointlar
│   ├── config.py                # yo'llar, port, TLS/discovery sozlamalari
│   ├── db.py                    # SQLite sxema + seed + generik CRUD
│   ├── security.py              # Ed25519 imzo kaliti + TLS sertifikat
│   ├── discovery.py             # imzolangan UDP beacon (server-topish)
│   ├── ws.py                    # WebSocket connection manager
│   ├── weather.py               # internet ob-havo keshi
│   ├── ui/                      # PyQt6 admin oyna
│   │   ├── window.py            #   asosiy oyna + navigatsiya
│   │   ├── login.py             #   admin login (parol hash + audit)
│   │   ├── pages/               #   dashboard, content, ads, stats, settings, cache, crud
│   │   ├── cards.py, dialogs.py, helpers.py, styles.py, toggle.py
│   │   ├── mapserver.py         #   lokal PMTiles Range-server
│   │   ├── route_map_dialog.py, stop_dialog.py   # bekat/xarita dialoglari
│   │   └── server_thread.py     #   backendni fon oqimda ko'taradi
│   ├── tools/                   # seed_demo.py, seed_route_xiva.py, fetch_map_assets.py
│   ├── assets/                  # ikonkalar, xarita (PMTiles, fontlar), uz_stations.json
│   ├── content/                 # media/, covers/, books/, ads/  (admin to'ldiradi)
│   ├── installer.iss            # Inno Setup skripti
│   ├── kiosk_server.spec        # PyInstaller spec
│   └── requirements.txt
│
├── user/                        # KIOSK (foydalanuvchi) ilovasi
│   ├── main.py                  # kiosk oyna, ulanish, navigatsiya, qulf
│   ├── core/                    # config, theme, i18n, cache, security(ExitGuard),
│   │                            #   netpin/trust (TLS pinning), pinhash, logsetup
│   ├── services/                # api, ws_client, discovery, health, ads, stats,
│   │                            #   media_cache, maptiles, stream_proxy
│   ├── screens/                 # home, map, videos, books, sites, connecting
│   ├── players/                 # video, audio, reader
│   ├── widgets/                 # navbar, card, cover, banner, screensaver,
│   │                            #   lockscreen, pinpad, qr, routemap, emergency, ...
│   ├── system/                  # lockdown (OS qulf), vlcsetup, watchdog
│   ├── assets/                  # ikonkalar, dizayn rasmlari
│   ├── DEPLOYMENT-LOCKDOWN.md   # kiosk qurilmasini qulflash qo'llanmasi
│   ├── setup_kiosk_user.ps1     # kiosk foydalanuvchisini yaratish skripti
│   ├── installer.iss / kiosk.spec / requirements.txt
│
└── Qo'llanmalar/                # dastlabki qoralama/prototip (arxiv)
```

> **Eslatma:** `content/`, `cache/`, `logs/`, `*.db`, TLS/imzo kalitlari (`*.pem`),
> `trust.json`, `server.txt` va build artefaktlari (`build/`, `dist/`, `Output/`)
> `.gitignore`da — repoga tushmaydi. Demo kontent `seed_demo.py` orqali tiklanadi.

---

## Tez boshlash (ishlab chiqish)

Talab: **Python 3.10** tavsiya etiladi (3.14 da intermittent segfault kuzatilgan),
kiosk uchun mashinada **VLC** o'rnatilgan bo'lsin.

### 1. Server (admin)

```bash
cd server
pip install -r requirements.txt
python main.py        # admin oyna + backend (https://0.0.0.0:8765)
```

Birinchi ishga tushishda `data.db` avtomatik yaratiladi va demo kontent bilan
to'ldiriladi. Faqat backend (oynasiz, sinov uchun):

```bash
KIOSK_TLS=0 python -c "import uvicorn; uvicorn.run('main:app', host='0.0.0.0', port=8765)"
```

Demo kontent / yo'nalish / xaritani qo'lda tiklash:

```bash
python tools/seed_demo.py          # demo media/kitob/reklama
python tools/seed_route_xiva.py    # 076Ф Xiva yo'nalishi jadvali
python tools/fetch_map_assets.py   # oflayn xarita assetlari (MapLibre + PMTiles)
```

### 2. Kiosk (user)

```bash
cd user
pip install -r requirements.txt
python main.py
```

Manbadan ishga tushganda (`python main.py`) — **oddiy ramkali oyna** (sozlash qulay).
Build qilingan `Kiosk.exe` esa avtomatik **fullscreen kiosk rejim**ida ochiladi.

Server manzilini qo'lda berish (ixtiyoriy — bo'lmasa discovery topadi):

```bash
set KIOSK_SERVER=https://192.168.1.10:8765   # Windows
set KIOSK_API_KEY=...                        # server dashboardidan
python main.py
```

**Texnik tugmalar (ishlab chiqishda):**
- `Ctrl+Shift+Q` — chiqish PIN oynasi
- Soat ustiga **10 marta** tez teginish — chiqish PIN (sensorli ekranlar uchun)

---

## Sozlash

### Kiosk — `server.txt` (exe yonida; installer yozadi, bloknotda tahrir qilsa bo'ladi)

```
# izoh qatori
https://192.168.1.10:8765     # server manzili (1-oddiy qator)
key=AbCdEf...                 # API kalit
kiosk=6                       # kiosk raqami (admin jadvalida ko'rinadi)
xona=12                       # xona/vagon raqami
cache=0                       # lokal media keshni o'chirish (standart: yoqiq)
```

Ulanish manbasi ustuvorligi: `KIOSK_SERVER` env → `server.txt` → `trust.json` → discovery.

### Muhim muhit o'zgaruvchilari

| O'zgaruvchi | Qism | Vazifasi | Standart |
|---|---|---|---|
| `KIOSK_PORT` | server | backend porti | `8765` |
| `KIOSK_TLS` | server | `0` — HTTPSni o'chirish (faqat dev) | `1` (yoqiq) |
| `KIOSK_DISCOVERY` | server | UDP beaconni o'chirish | `1` (yoqiq) |
| `KIOSK_NAME` | server | serverning ko'rinadigan nomi | hostname |
| `KIOSK_SERVER` | kiosk | server URL (qo'lda) | discovery |
| `KIOSK_API_KEY` | kiosk | API kalit | `server.txt` |
| `KIOSK_WINDOWED` | kiosk | `1` oddiy oyna / `0` kiosk fullscreen | frozen→`0` |
| `KIOSK_EXIT_PIN` | kiosk | chiqish PINi | `7777` |
| `KIOSK_DEV_PIN` | kiosk | vendor master PIN (mijozdan mustaqil) | build oldidan o'zgartiring |

---

## REST / WebSocket API

Barcha `/api/*` yo'llari **API kalit** talab qiladi (`X-API-Key` header yoki `?k=` query
param; timing-safe solishtirish). `/api/health` ochiq qoladi.

| Metod va yo'l | Vazifasi |
|---|---|
| `GET /api/health` | server tirikligi (kalitsiz) |
| `GET /api/content[?type=movie]` | ko'rinadigan kontent katalogi |
| `GET /api/content/{id}` | bitta kontent |
| `GET /api/content/{id}/cover` | muqova (fayl yo'q bo'lsa dinamik SVG) |
| `GET /api/stream/{id}` | video/audio striming (HTTP Range) |
| `GET /api/book/{id}/text` | kitob matni (boblar bilan) |
| `GET /api/ads` · `GET /api/ads/{id}/media` | reklama ro'yxati + fayli |
| `GET /api/sites` · `GET /api/route` · `GET /api/settings` | saytlar, yo'nalish, ommaviy sozlamalar |
| `GET /api/status` | poyezd holati (tezlik, harorat, joriy bekat, blok) |
| `POST /api/heartbeat` | kiosk o'zini tanitadi (admin "Kiosklar" jadvali) |
| `POST /api/stats` | kiosk foydalanish event to'plami (batch) |
| `WS /ws?k=...` | real vaqt: `status_update`, `announcement`, `sync`, kesh buyruqlari |

`/api/settings` maxfiy kalitlarni (`api_key`, `admin_password_hash`) javobdan chiqarib
tashlaydi. Barcha fayl yo'llari **path-traversal** himoyasidan (`_safe_join`) o'tadi.

---

## Xavfsizlik

Bir necha mustaqil qatlam (har biri alohida ham himoya beradi):

- **API kalit** — barcha `/api` va `/ws` so'rovlari uchun (header yoki `?k=`).
- **TLS pinning** — server self-signed sertifikat bilan ishlaydi; kiosk uni birinchi
  ulanishda "pin" qiladi (`trust.json`), keyin faqat shu sertifikatga ishonadi.
  Stream proxy (`services/stream_proxy.py`) VLC/Qt ocholmaydigan self-signed HTTPSni
  lokal HTTP orqali ochib beradi.
- **Imzolangan discovery** — UDP beacon **Ed25519** bilan imzolanadi; soxta server
  yasab bo'lmaydi (maxfiy imzo kaliti serverda qoladi).
- **Admin login + audit** — server admin oynasi parol hash bilan, harakatlar loglanadi.
- **PIN hash** — kiosk chiqish/SOS PINlari xeshlangan holda.
- **OS lockdown** — kiosk Win/Alt+Tab/Task Manager qulflaydi, watchdog avto qayta ochadi.
- **Maxfiy kalitlar** — `*.pem`, `signing_key.pem`, `trust.json` hech qachon git'ga
  tushmaydi (birinchi ishga tushishda yaratiladi).

Batafsil: [user/DEPLOYMENT-LOCKDOWN.md](user/DEPLOYMENT-LOCKDOWN.md).

---

## Build va o'rnatish (.exe)

Windows uchun **PyInstaller** (paketlash) + **Inno Setup** (installer):

```bash
# Server
cd server
pyinstaller kiosk_server.spec        # -> dist/KioskServer/
# so'ng installer.iss ni Inno Setup bilan kompilyatsiya  -> Output/KioskServerSetup.exe

# Kiosk
cd user
pyinstaller kiosk.spec               # -> dist/Kiosk/ (VLC bundle bilan)
# so'ng installer.iss ni Inno Setup bilan kompilyatsiya  -> Output/KioskSetup.exe
```

- Kiosk installer **VLC**ni o'zi bilan olib keladi, **KioskWatchdog.exe**ni autostartga
  qo'yadi va (tanlansa) qulflash siyosatlarini yoqadi.
- Installer paroli `KIOSK_SETUP_PASS` muhit o'zgaruvchisi orqali beriladi (build vaqtida).
- Build py3.10 bilan tavsiya etiladi (py3.14 da intermittent buzilish kuzatilgan).

---

## Kiosk qurilmasini qulflash

Poyezdda yo'lovchi chiqib keta olmaydigan to'liq qulflash bosqichlari (alohida
foydalanuvchi + shell almashtirish, registry siyosatlari, watchdog, tiklanish yo'li)
**[user/DEPLOYMENT-LOCKDOWN.md](user/DEPLOYMENT-LOCKDOWN.md)** da batafsil.

Tezkor xulosa:
1. `KioskSetup.exe` → server manzili + API kalit kiriting → "qulflash" belgisini qoldiring.
2. To'liq qulflash uchun: alohida `kiosk` foydalanuvchisi + auto-logon + Winlogon Shell =
   `KioskWatchdog.exe` (Explorer umuman yuklanmaydi).
3. Kiosk va server **alohida VLAN/SSID**da bo'lsin (eng kuchli himoya).

Tiklanish: `Ctrl+Alt+Del → Chiqish` → admin hisobiga kiring; kerak bo'lsa
`lockdown_off.reg` / `lockdown_on.reg`.

---

## Litsenziya / sinov muddati

Serverda sinov muddati / litsenziya holati saqlanadi. Muddat tugasa server
`status.blocked=True` yuboradi va kiosk butun ekranni **qulf ekrani** bilan qoplaydi.
Holat kioskda keshlanadi — server o'chsa ham qulf saqlanadi. Vendor **master PIN**
(`KIOSK_DEV_PIN`) bloklangan holatda ham dasturni yopa oladi (mijozdan mustaqil).
