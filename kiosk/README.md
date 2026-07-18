# Kiosk — veb-ilova (user qismi)

Poyezd kiosk tizimining **veb versiyasi** (Nuxt 4 SPA). Bu ilova [PyQt6 user
ilovasi](../user/)ning brauzerdagi muqobili: bir xil 5 bo'lim (Asosiy, Videolar,
Kitoblar, Xarita, Saytlar), mazmun esa mavjud **Python FastAPI serveridan**
([../server/](../server/)) olinadi.

## Arxitektura — Nuxt proksi

Brauzer to'g'ridan-to'g'ri Python serverga bormaydi. O'rtada **Nuxt server
(Nitro) proksi qatlami** turadi:

```
Brauzer (Vue)
    │  /api/movies, /api/status, /api/cover/12 ...
    ▼
Nuxt Nitro (server/api/*.ts)  ──  X-API-Key qo'shadi, self-signed TLS'ni ochadi
    │  https://<server>:8765/api/content, /api/status ...
    ▼
Python FastAPI server ([../server/](../server/))
```

Bu yondashuvning afzalliklari:
- **API kalit brauzerga chiqmaydi** — faqat Nitro (server tomon) ushlaydi.
- **Self-signed TLS** — server sertifikatini Nitro qabul qiladi (brauzer sertifikat xatosi bermaydi).
- **CORS muammosi yo'q** — brauzer faqat o'z originiga (Nuxt) so'rov yuboradi.
- **Media proksi** — `<img>`/`<video>` header yubora olmaydi; kalit `?k=` bilan server tomonda qo'shiladi.

## Ishga tushirish

Talab: **Node.js ≥ 20**, ishlayotgan Python server ([../server/](../server/)).

```bash
npm install
cp .env.example .env      # NUXT_KIOSK_SERVER va NUXT_KIOSK_API_KEY ni to'ldiring
npm run dev               # http://localhost:3000
```

Sozlamalar (`.env`):

| O'zgaruvchi | Vazifasi | Standart |
|---|---|---|
| `NUXT_KIOSK_SERVER` | Python server manzili (https/http) | `https://127.0.0.1:8765` |
| `NUXT_KIOSK_API_KEY` | Server API kaliti (admin Boshqaruv sahifasidan) | bo'sh |

Ishlab chiqarish:

```bash
npm run build && node .output/server/index.mjs
```

## Server (Nitro) API qatlami

`server/api/` — brauzer chaqiradigan, Python'ga proksi qiladigan endpointlar:

| Nuxt endpoint | Python manba | Vazifasi |
|---|---|---|
| `GET /api/movies` | `/api/content` (video turlar) | Videolar → `Video[]` |
| `GET /api/books` | `/api/content` (book/audiobook) | Kitoblar → `Book[]` |
| `GET /api/ads` | `/api/ads` | Reklama bannerlari → `Ad[]` |
| `GET /api/websites` | `/api/sites` | Saytlar → `Website[]` |
| `GET /api/status` | `/api/status` | Tezlik, harorat, joriy bekat, vagon |
| `GET /api/route` | `/api/route` + `/api/status` | Yo'nalish → `TrainRoute` |
| `GET /api/cover/:id` | `/api/content/:id/cover` | Muqova rasmi (proksi) |
| `GET /api/stream/:id` | `/api/stream/:id` | Video/audio striming (Range) |
| `GET /api/ad-media/:id` | `/api/ads/:id/media` | Reklama fayli (proksi) |
| `GET /api/book/:id/text` | `/api/book/:id/text` | Kitob matni (boblar) |

Yordamchi kod:
- `server/utils/backend.ts` — `backendFetch` (JSON, API kalit bilan) va `proxyMedia` (binar oqim, Range).
- `server/utils/map.ts` — Python yozuvlarini frontend tiplariga (`types/app.ts`) o'giradigan mapping.
- `server/plugins/backend-tls.ts` — self-signed TLS'ni qabul qiluvchi global dispatcher.

## Oflayn domen (`poyezd.uz`) va port 80

Kiosk qurilmalar veb'ni chiroyli nom bilan ochadi — **`http://poyezd.uz`** (port
yozish shart emas). Bu **internetsiz, DNS'siz** ishlaydi: har qurilmaning `hosts`
fayliga `poyezd.uz → server IP` yoziladi.

**Server tomoni — avtomatik (qo'lda hech narsa yo'q).** Server (`admin.py`) ishga
tushganda `ui/web_server.py`:
- veb'ni **80-portda** ishga tushiradi (`KIOSK_WEB_PORT`, std 80),
- server o'z hosts fayliga `127.0.0.1  poyezd.uz` yozadi,
- firewall'da 80-portni ochadi.

Domen `KIOSK_WEB_DOMAIN` (std `poyezd.uz`) bilan o'zgartiriladi.

**Kiosk qurilma tomoni.** Har qurilmada `hosts`ga server IP yoziladi — buni
[deploy/set-domain.ps1](deploy/set-domain.ps1) qiladi (kiosk installeri avtomatik
chaqiradi, server IP o'rnatishda kiritilgan):

```powershell
# admin PowerShell (idempotent, qayta ishga tushsa yangilaydi)
.\deploy\set-domain.ps1 -ServerIp 192.168.136.69
```

So'ng qurilma brauzeri **`http://poyezd.uz`** ochadi. Kiosk faqat 80-portga
ulanadi — Python backend (8765) tashqariga ochilmaydi (Nitro `localhost`da chaqiradi).

> Server IP qat'iy (statik) bo'lsin — router'da DHCP reservation qiling, aks holda
> IP o'zgarsa har qurilmada `set-domain.ps1` qayta ishga tushirilishi kerak.

## Bo'limlar (frontend)

- **Asosiy** — poyezd statusi (`/api/status`, har 5s yangilanadi) + reklama karusel + tavsiyalar.
- **Videolar** — kartochkalar, qidiruv, detal modal; ijro `/api/stream/:id` (Range/seek).
- **Kitoblar** — kartochkalar; bitta yozuv o'qiladi (`/api/book/:id/text`) va/yoki tinglanadi (`/api/stream/:id`).
- **Xarita** — Leaflet + timeline; yo'nalish `/api/route` (joriy bekat, o'tilganlar).
- **Saytlar** — kartochkalar + QR kod modal.

## Texnologiyalar

Nuxt 4 (SPA, `ssr: false`) · Nuxt UI + Tailwind CSS 4 · `@nuxtjs/i18n` (uz/ru/en) ·
`@nuxtjs/leaflet` · `@nuxtjs/color-mode` (light/dark) · `nuxt-svgo`.

> **Eslatma:** bu veb-ilova PyQt6 kioskning oflayn keshi, OS qulflashi, watchdog
> kabi tizim-darajali imkoniyatlariga ega emas — u brauzer/veb yetkazish uchun.
> To'liq qulflangan poyezd kioski uchun [../user/](../user/) ilovasi ishlatiladi.
