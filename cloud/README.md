# KioskCloud — markaziy bulut admin paneli (`cloud/`)

Barcha poyezd serverlarini **bir joydan, internet orqali** boshqarish: kontent
yuklash/tarqatish/o'chirish, kiosklarni kuzatish, statistika va loglar.

Dizayn manbasi — [`docs/design/kiosk-cloud-admin.dc.html`](../docs/design/kiosk-cloud-admin.dc.html)
(prototipdagi "Texnik reja" sahifasi shu implementatsiyaning spetsifikatsiyasi).

## Asosiy g'oya: server O'ZI ulanadi

Poyezdda oq IP yo'q, SIM-internet uzilib turadi. Shuning uchun bulut poyezdga
**hech qachon o'zi ulanmaydi** — teskarisi:

```
   POYEZD (server/)                            BULUT (cloud/)  — VPS, oq IP
 ┌──────────────────────┐                   ┌──────────────────────────────┐
 │ FastAPI + SQLite     │   chiquvchi WSS   │  /agent   (WebSocket)        │
 │ cloud_client.py      │ ────────────────► │  /api/enroll                 │
 │  · heartbeat 30s     │                   │  /dl/<imzolangan-token>      │
 │  · buyruqlar (imzo)  │ ◄──────────────── │  /api/admin/*  + static/     │
 │  · fayl tortish      │   Range + sha256  │  SQLite + storage/ (sha256)  │
 └──────────────────────┘                   └──────────────────────────────┘
        ▲ LAN                                          ▲ brauzer
   kiosklar (kiosk/, web/)                        admin (parol)
```

Poyezdda port ochish, statik IP, VPN — **kerak emas**.

## Nega `web/` papkasida emas?

Ikkisi turli mashinada, turli auditoriya uchun ishlaydi va hech qachon bir joyda
turmaydi:

| | `web/` | `cloud/static/` |
|---|---|---|
| Kim ko'radi | **yo'lovchi** | **super admin** |
| Qayerda ishlaydi | poyezd serveri ichida (vagonda) | VPS (internetda) |
| Internet | kerak emas | shart |
| Nima bilan tarqaladi | `KioskServerSetup.exe` ichida | VPS'ga alohida qo'yiladi |
| Texnologiya | Nuxt 4 + Node.js | statik JS, bulut FastAPI beradi |

Super-admin panelini `web/` ga qo'yish xato bo'lardi: u **har bir poyezdga
tarqatilardi** va vagon Wi-Fi'idan ochilib qolardi. Shuning uchun bulut paneli
bulutning o'z jarayoni bilan keladi.

## Ishga tushirish (lokal sinov)

```bash
cd cloud
pip install -r backend/requirements.txt
CLOUD_ADMIN_PASS=<parol> python backend/main.py   # http://0.0.0.0:9000
```

## VPS'ga qo'yish (ishlab chiqarish)

`cloud/` — **mustaqil**: `server/`, `web/`, `kiosk/` papkalari kerak emas,
PyQt ham, Node.js ham kerak emas (kodi ~1 MB, 3 ta Python paketi).

Batafsil qadamlar, systemd xizmati va nginx sozlamasi:
**[deploy/README.md](deploy/README.md)** — ichida `kioskcloud.service` va
`nginx-kioskcloud.conf` tayyor holda.

Qisqacha: `scp -r cloud root@VPS:/opt/kioskcloud` → venv + requirements →
`kioskcloud.service` → nginx + certbot → poyezd serverlarida faqat domenni
ko'rsatasiz.

Parol berilmasa birinchi ishga tushishда tasodifiy parol yaratiladi va konsolga
**bir marta** chiqariladi (keyin xesh ko'rinishida bazada saqlanadi).

### Muhit o'zgaruvchilari

| O'zgaruvchi | Standart | Vazifasi |
|---|---|---|
| `CLOUD_HOST` / `CLOUD_PORT` | `0.0.0.0` / `9000` | tinglash manzili |
| `CLOUD_ADMIN_PASS` | — | admin paroli (berilsa har ishga tushishda yangilanadi) |
| `CLOUD_DB` | `cloud/cloud.db` | SQLite bazasi |
| `CLOUD_STORAGE` | `cloud/storage/` | fayl ombori |
| `CLOUD_TLS_CERT` / `CLOUD_TLS_KEY` | — | to'g'ridan-to'g'ri HTTPS (aks holda reverse-proxy) |
| `CLOUD_DL_TTL` | `86400` | yuklab olish havolasining muddati (soniya) |
| `CLOUD_OFFLINE_AFTER` | `90` | shu vaqtdan keyin server "offlayn" |
| `CLOUD_MAX_UPLOAD` | 8 GB | bitta faylning chegarasi |

Ishlab chiqarishda **reverse-proxy ortida** (nginx/caddy) TLS bilan ishlatish
tavsiya etiladi. Yuklab olish havolalari nisbiy (`/dl/…`) — agent ularni o'zi
ulangan manzilga nisbatan yechadi, shuning uchun proxy ortida ham to'g'ri
ishlaydi (tashqi manzilni sozlash shart emas).

## Poyezd serverini ulash — faqat DOMEN

Token kerak emas. Poyezd serveriga **faqat bulut domeni** yoziladi:

1. Admin oynasi → **Sozlamalar → Markaziy bulut** → `cloud.poyezd.uz` → Saqlash
   (yoki `server/cloud.txt` ichiga `url=cloud.poyezd.uz`, yoki
   `KIOSK_CLOUD_URL` muhit o'zgaruvchisi). Sxema (`https://`) yozilmasa
   o'zi qo'shiladi.
2. Serverni qayta ishga tushiring — u o'zi ro'yxatga turadi.
3. Panelda **Boshqaruv** yoki **Serverlar** bo'limida «Yangi server ulanmoqchi»
   bloki chiqadi → **Tasdiqlash**.

Tasdiqlanmaguncha serverga **kontent ham, buyruq ham, sozlama ham yuborilmaydi**
va uning statistikasi qabul qilinmaydi — domenni bilgan begona qurilma hech
narsa olmaydi. (Agent ham tasdiqlanmaguncha statistikani yubormaydi, shuning
uchun bir dona event yo'qolmaydi.)

Build vaqtida `server/config.py` dagi `CLOUD_URL_DEFAULT` ga domenni yozib
qo'ysangiz — o'rnatuvchi **hech narsa kiritmaydi**, server o'zi ulanadi.

**Ulash kalitlari (ixtiyoriy).** Ko'p serverni bir yo'la o'rnatayotgan bo'lsangiz,
panelda kalit yaratib `KIOSK_CLOUD_ENROLL=<token>` bilan bersangiz — o'sha server
**darhol tasdiqlangan** bo'ladi, qo'lда bosish kerak emas. Kalit bir martalik.

**Bulutni boshqa serverga ko'chirish.** Domen ishlatilganда poyezdlarda hech
narsa o'zgartirilmaydi — DNS'ni yangi IP'ga qaratasiz. Ko'chirish kerak bo'lgan
fayllar: `cloud.db`, `storage/` va **`cloud_signing_key.pem`** (kalit almashsa
serverlar buyruqlarni rad etadi). Bir xil qurilma qayta enroll qilса dublikat
yozuv yaratilmaydi (`hw_id` bo'yicha topib, tokenni yangilaydi).

## Kontent qanday tarqaladi (desired state)

Eng muhim tushuncha: bulut "shu serverда shu kontent **bo'lishi kerak**" deb
to'liq ro'yxat (`manifest`) yuboradi, har o'zgarishда `rev` raqami oshadi.

```
assignments (bulut)                 manifest {rev, items[]}
      │  desired_rev = 7            ────────────────────►  agent
      │                                                      │
      ▼                                                      ├─ yo'q faylni yuklaydi
server.applied_rev = 6  ◄─────── {"type":"applied","rev":7} ─┤   (Range + sha256)
                                                             └─ ro'yxatда yo'q
                                                                BULUT kontentini
                                                                o'chiradi
```

Shundan kelib chiqadigan xossalar:

- **Yuklash va o'chirish — bitta mexanizm.** Alohida "delete" buyrug'i yo'q.
- **Uzilish xavfsiz.** Server oflayn bo'lса ish `queued` bo'lib turadi;
  ulanganda `register` → farq ko'rinadi → manifest keladi. Qayta bosish shart emas.
- **Trafik tejaladi.** Fayl sha256 bo'yicha solishtiriladi: serverда bor bo'lsa
  qayta yuklanmaydi. Uzilgan yuklash `Range: bytes=<davom>-` bilan to'xtagan
  joyidan davom etadi, oxirida sha256 tekshiriladi (buzuq fayl qabul qilinmaydi).
- **Qo'lда qo'shilgan kontentga tegilmaydi.** Faqat `origin='cloud'` yozuvlar
  bulut boshqaruvida; poyezdда admin o'zi qo'shgan kontent (`origin='local'`)
  hech qachon o'chirilmaydi.
- **O'z-o'zini tuzatish.** Heartbeatда `applied_rev != desired_rev` ko'rinса
  bulut manifestni qaytadan yuboradi — yo'qolgan buyruq muammo tug'dirmaydi.

## Xavfsizlik

| Qatlam | Nima qiladi |
|---|---|
| **Enroll token** | bir martalik, xeshlangan; ishlatilgach kuchdan qoladi |
| **server_token** | doimiy, xeshlangan (pbkdf2); WS ulanishда tekshiriladi |
| **Ed25519 imzo** | har bir buyruq bulut kaliti bilan imzolanadi, agent tekshiradi — kanalga tushgan begona "o'chir" buyrug'i ishlamaydi |
| **Yuklab olish tokeni** | HMAC + muddat + `server_id` ichida; oshkor bo'lsa ham boshqa serverda va muddatdan keyin ishlamaydi |
| **Admin sessiyasi** | parol pbkdf2, sessiya faqat xotirada (restartда hamma chiqadi), IP bo'yicha urinish chegarasi (8 marta → 5 daqiqa blok) |
| **Yuklash chegarasi** | 8 GB, oqim bilan diskka (xotirada bufer yo'q) |

> `cloud_signing_key.pem` — **zaxira nusxa olinishi shart**. U almashsa
> ro'yxatdan o'tgan serverlar buyruqlarni rad etadi (ochiq kalit ularда
> saqlangan) va har birini qaytadan ulash kerak bo'ladi.

## Tuzilma

```
cloud/
├── backend/          # Python FastAPI (server tomoni)
│   ├── main.py       FastAPI: /agent WS, /api/enroll, /dl/{token}, /api/admin/*
│   ├── relay.py      ulangan agentlar reyestri + manifest/buyruq yuborish
│   ├── db.py         SQLite: servers, content, assignments, jobs, stats, events
│   ├── storage.py    sha256 ombori (dedup, Range, yetim blob tozalash)
│   ├── security.py   Ed25519 imzo, yuklab olish tokenlari, admin parol/sessiya
│   ├── config.py     muhit o'zgaruvchilari (CLOUD_*); BASE_DIR = cloud/ (ota-papka)
│   ├── ws.py  tools/  requirements.txt
├── web/              # frontend SPA (build'siz: statik JS, backend /static da beradi)
│   ├── index.html  app.js  styles.css  default-hero*.  uz_stations.json
├── Dockerfile  docker-compose.yml  Caddyfile  deploy/   # deploy
└── (runtime, git-ignore) cloud.db  storage/  cloud_signing_key.pem  .env  logs/
```

> **Ma'lumot `cloud/` ILDIZIDA** (kod `backend/` da): `config.BASE_DIR` kod
> papkasining ota-papkasi — shuning uchun `cloud.db`, `storage/`, imzo kaliti,
> `.env` joyida qoladi. Ishga tushirish har doim `cloud/` dan: `python backend/main.py`.

Poyezd tomoni: [`../server/cloud_client.py`](../server/cloud_client.py) —
enroll, heartbeat, buyruqlar, downloader, manifest qo'llash, statistika/loglar.

## Panel ekranlari

| Ekran | Nima ko'rinadi va nima qilinadi |
|---|---|
| Boshqaruv | 4 KPI, tasdiqlash kutayotgan serverlar, serverlar holati, faol navbat, ombor, hodisalar |
| Serverlar | jadval: kiosklar, sinxronizatsiya (rev), disk, litsenziya, oxirgi aloqa |
| Server tafsiloti | **veb ilovani yoqish/o'chirish**, **server sozlamalarini masofadan tahrirlash**, **har bir kioskка buyruq** (sinxronlash / kesh tozalash / keshni o'chirish / ro'yxatdan olib tashlash), kontent, sessiyalar, loglar, e'lon |
| Kontent kutubxonasi | turlar bo'yicha, ko'p tanlash → tarqatish yoki o'chirish, **tahrirlash** (metadata + fayl almashtirish) |
| Tarqatish (3 qadam) | kontent → serverlar → tasdiq (sha256 dedup, tungi rejim) |
| Navbat | jonli progress, offlayn serverlar `navbatda`, nishon bo'yicha holat |
| Statistika | **kiosk / veb manba filtri**, sessiyalar, noyob qurilmalar, kunlik grafik, top kontent, serverlar, faol qurilmalar + **"hali ko'chirilmagan" ko'rsatkichi** |
| Loglar | daraja va server bo'yicha filtr |
| Ulash kalitlari | ulash yo'riqnomasi + (ixtiyoriy) bir martalik kalitlar |

### Masofadan boshqarish nimalarni qamraydi

| Soha | Bulutdan boshqariladi |
|---|---|
| Kontent | qo'shish, tahrirlash, fayl almashtirish, tarqatish, o'chirish |
| Server sozlamalari | vagon/poyezd/yo'nalish/jo'nash, tezlik va ob-havo, reklama oralig'i va algoritmi, kesh chegarasi, SOS, mavzu, veb yoqilishi, Wi-Fi (qayta ishga tushirishда qo'llanadi) |
| Veb ilova | holat (ishlayaptimi) + yoqish/o'chirish |
| Kiosklar | kesh sinxronlash, kesh tozalash, keshni yoqish/o'chirish, ro'yxatdan olib tashlash |
| Umumiy | e'lon yuborish, hammasini sinxronlash, statistika va loglarni ko'rish |

**Bulutdan boshqarilMAYDIGAN** (ataylab): `api_key`, admin paroli, litsenziya va
sinov muddati kalitlari, `cloud_token` — bular xavfsizlik chegarasi, faqat
joyidagi admin oynasidan o'zgartiriladi. Oq ro'yxat **poyezd tomonida**
(`server/cloud_client.py` → `REMOTE_SETTINGS`), shuning uchun bulut nimani
yuborishidan qat'i nazar server faqat ruxsat berilganini yozadi.

Panel mobil ekranда ham ishlaydi (kuzatuv uchun): sidebar burger tugmasi ostiga
tushadi, jadval ustunlari qisqaradi.

## Eslatmalar

- Statistika bulutga **batch** bilan keladi (standart 5 daqiqa,
  `KIOSK_CLOUD_STATS`) — navbat sifatida poyezd serverining o'z bazasi ishlaydi,
  shuning uchun oflaynда hech narsa yo'qolmaydi.
- Loglarга faqat WARNING/ERROR va muhim hodisalar yuboriladi (SIM-trafik).
- Masofadan **qayta ishga tushirish ataylab bajarilmaydi** — poyezdда kioskni
  ishlamay qoldirish xavfi bor; buyruq faqat logда qayd etiladi.
- Bulut faqat kontent tarqatadi: reklama, saytlar va bekatlar hozircha har
  serverning o'z admin oynasida boshqariladi.
