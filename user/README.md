# Kiosk — Foydalanuvchi (user) ilovasi

Poyezd vagoniga o'rnatiladigan **sensorli ekran kiosk ilovasi** (PyQt6): fullscreen,
qulflangan, oflayn ishlay oladi. Yo'lovchi kino/multfilm/musiqa/audiokitob/kitob ko'radi,
yo'nalishni xaritada kuzatadi, saytlarga QR orqali o'tadi. Mazmun [server](../server/)dan
olinadi. Loyihaning umumiy tavsifi — ildizdagi [README.md](../README.md).

## Ishga tushirish

```bash
pip install -r requirements.txt
python main.py
```

Manbadan ishga tushganda — **oddiy ramkali oyna** (sozlash qulay). Build qilingan
`Kiosk.exe` esa avtomatik **fullscreen kiosk rejim**ida ochiladi. Boshqarish:
`KIOSK_WINDOWED=1` (oddiy) / `=0` (kiosk).

Server manzilini qo'lda berish (ixtiyoriy — bo'lmasa discovery topadi):

```bash
set KIOSK_SERVER=https://192.168.1.10:8765   # Windows
set KIOSK_API_KEY=...                        # server dashboardidan
python main.py
```

Ulanish manbasi ustuvorligi: `KIOSK_SERVER` env → `server.txt` → `trust.json` → discovery.

> **Eslatma:** video/audio ijro uchun qurilmada **VLC** (LibVLC) o'rnatilgan bo'lishi
> shart — `python-vlc` shunga tayanadi. Build qilingan ilova VLCni o'zi bilan olib keladi.

## Texnik tugmalar (ishlab chiqishda)

- `Ctrl+Shift+Q` — chiqish PIN oynasi
- Navbardagi soat ustiga **10 marta** tez teginish — chiqish PIN (sensorli, klaviaturasiz ekranlar uchun); soat ko'rinmasa zaxira: ekran yuqori-o'ng burchagi

## Bo'limlar

- **Asosiy** (`screens/home.py`) — poyezd statusi (tezlik, harorat, joriy bekat, vagon), reklama banneri, tavsiya etilgan kontent.
- **Xarita** (`screens/map.py`) — yo'nalish timeline + oflayn vektor xarita (QtWebEngine + MapLibre + PMTiles).
- **Videolar** (`screens/videos.py`) — tablar, qidiruv, kartochkalar, detal modal, to'liq ekran VLC pleyer.
- **Kitoblar** (`screens/books.py`) — kartochkalar, detal modal; bitta yozuv ham **o'qiladi** (matn o'quvchi), ham **tinglanadi** (audiokitob pleyeri) — mavjudiga qarab.
- **Saytlar** (`screens/sites.py`) — kartochkalar + QR kod + yo'riqnoma.

## Tuzilma

- `main.py` — kiosk oyna, ulanish boshqaruvi, navigatsiya, til/mavzu, screensaver, crash-log, global event-filtr (maxfiy chiqish + harakatsizlik).
- `core/`
  - `config.py` — server manzili va ulanish sozlamalari (`server.txt`/`trust.json`/env o'qiydi). **Sozlashda asosiy fayl.**
  - `theme.py` — ranglar, o'lchamlar, responsive miqyos (`init_scale`, `T.s(px)`).
  - `i18n.py` — 3 til (uz/ru/en), rebuild-on-switch.
  - `cache.py` — oflayn kesh (katalog/JSON diskka).
  - `security.py` — `ExitGuard` (maxfiy chiqish, PIN); `pinhash.py` — PIN hash.
  - `netpin.py` / `trust.py` — TLS pinning (faqat pin qilingan sertifikatga ishonadi).
  - `logsetup.py`, `threads.py`, `overlay.py`.
- `services/`
  - `api.py` — server REST mijozi; `ws_client.py` — real-time kanal.
  - `discovery.py` — imzolangan UDP beaconni tutib serverni topadi.
  - `health.py` — ulanishni davriy tekshiradi; `media_cache.py` — media fonda diskka keshlash.
  - `ads.py` — reklama kadansi; `stats.py` — foydalanish eventlari navbati.
  - `stream_proxy.py` — self-signed HTTPSni VLC uchun lokal HTTP orqali ochish.
- `players/` — `video.py` (VLC), `audio.py` (audiokitob/musiqa: to'lqin, playlist, tezlik), `reader.py` (matn o'quvchi: boblar, sahifalash).
- `widgets/` — navbar, card, cover, banner, screensaver, lockscreen, pinpad, qr, routemap, emergency (SOS), modal, spinner, empty va b.
- `system/` — `lockdown.py` (OS qulf: Win/Alt+Tab/Task Manager), `vlcsetup.py` (bundle VLCni ulash), `watchdog.py` (ilova qulasa qayta ochish).
- `assets/` — navigatsiya ikonkalari, dizayn rasmlari.

## Sozlash — `server.txt` (exe yonida; installer yozadi)

```
https://192.168.1.10:8765     # server manzili (1-oddiy qator)
key=AbCdEf...                 # API kalit
kiosk=6                       # kiosk raqami (admin jadvalida ko'rinadi)
xona=12                       # xona/vagon raqami
cache=0                       # lokal media keshni o'chirish (standart: yoqiq)
```

## Oflayn rejim

Server/internet uzilsa kiosk avtomatik oflaynga o'tadi: keshlangan katalog va media
ishlashda davom etadi, pastki-o'ng burchakda oxirgi sinx vaqtli "oflayn" pill ko'rinadi.
Faqat keshlanmagan striming to'xtaydi. Kesh yo'q va birinchi ishga tushish bo'lsa —
"Serverga ulanmoqda..." ekrani (kutilgan xatti-harakat).

## Build va qurilmani qulflash

```bash
pyinstaller kiosk.spec               # -> dist/Kiosk/ (VLC bundle bilan)
# so'ng installer.iss ni Inno Setup bilan  -> Output/KioskSetup.exe
```

Poyezdda to'liq qulflash (alohida foydalanuvchi + shell almashtirish + watchdog +
registry siyosatlari + tiklanish yo'li): **[DEPLOYMENT-LOCKDOWN.md](DEPLOYMENT-LOCKDOWN.md)**.
Yordamchi: `setup_kiosk_user.ps1`, `lockdown_on.reg` / `lockdown_off.reg`.
