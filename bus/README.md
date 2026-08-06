# Avtobus — lokal veb-kiosk (web-only)

Avtobuslar uchun **faqat veb** variant: yo'lovchi telefondan avtobus Wi-Fi'iga
ulanib kino/multfilm/musiqa, kitob/audiokitob ko'radi, yo'nalish (bekatlar) va
reklamani ko'radi. **Kiosk ekrani / desktop KERAK EMAS** — hammasi telefonда.

Poyezd tizimining ukasi: bir xil **KioskCloud** (markaziy bulut) dan boshqariladi
— huddi poyezddek. Farqi: PyQt kiosk/desktop yo'q, faqat **backend + web**.

```
AVTOBUS (lokal mini-PC / Raspberry Pi + Wi-Fi)
┌──────────────────────────────────────────────┐
│  docker compose:                              │
│   ├─ backend  (FastAPI, headless — server/    │   ──chiquvchi WSS──►  KioskCloud
│   │   backend'i, PyQt'siz; /api, striming, WS)│   ◄──manifest (imzo)──   (bulut)
│   └─ web      (Nuxt SPA — AVTOBUS.UZ)         │
│  Ma'lumot: busdata volume (oflayn kesh)       │
└──────────────────────────────────────────────┘
        ▲ yo'lovchilar: http://<qurilma-IP>/  (avtobus Wi-Fi, HTTP)
```

## Ishga tushirish (avtobus qurilmasида) — 1 buyruq

Faqat **Docker** o'rnatilган bo'lsin. Keyin o'rnatgichni ishga tushiring — u
API kalitни o'zi yaratadi, bulut domeni + avtobus nomini so'raydi, image'ni
quradi va ishga tushiradi:

```bash
git clone <repo> /opt/avtobus && cd /opt/avtobus/bus
bash setup.sh              # Linux / mini-PC / Raspberry Pi
```

Windows qurilmasida (PowerShell):

```powershell
.\setup.ps1
```

Skript so'raydi: **bulut domeni** (masalan `cloud.poyezd.uz`), **avtobus nomi**,
va ixtiyoriy **ulash kaliti**. Tugagach manzilni ko'rsatadi.

Qo'lда (skriptsiz) ham bo'ladi:
```bash
cp .env.example .env && nano .env    # KIOSK_API_KEY, KIOSK_NAME, KIOSK_CLOUD_URL
docker compose up -d --build
```

Yo'lovchi: avtobus Wi-Fi → brauzerда `http://<qurilma-IP>/`.

## Boshqarish

```bash
docker compose logs -f        # loglar
docker compose restart        # qayta ishga tushirish
docker compose down           # to'xtatish (ma'lumot busdata volume'да saqlanadi)
git pull && docker compose up -d --build    # yangilash (kod), kontent bulutдан
```

## Bulutga ulash (KioskCloud)

Poyezddagi kabi: `.env`da `KIOSK_CLOUD_URL=cloud.poyezd.uz` → qurilma o'zi
ulanadi → **bulut panelида «Tasdiqlash»**. Shundan keyin bulutдан kontent,
reklama, yo'nalish tarqatiladi (desired-state manifest, sha256 dedup, oflayn
navbat). `KIOSK_CLOUD_ENROLL=<token>` bersangiz — darhol tasdiqlanadi.

## Poyezddan farqlari (moslashtirildi)

| | Poyezd | Avtobus |
|---|---|---|
| Kiosk ekrani (PyQt) | bor | **yo'q** (faqat veb) |
| Desktop admin | bor | **yo'q** (bulutдан boshqariladi) |
| Bo'limlar | Kino, Kitob, Xarita, **Saytlar** | Kino, Kitob, Xarita (**Saytlar olib tashlandi**) |
| Brend | POYEZD.UZ | **AVTOBUS.UZ** |
| LAN beacon/discovery | bor (kiosklar topadi) | **o'chiq** (kiosk yo'q) |
| TLS | LAN pinning | ichki HTTP (lokal tarmoq) |

## Tuzilma

```
bus/
├── backend/            headless FastAPI (server backend'i, PyQt'siz) + Dockerfile
│   ├── main.py db.py cloud_client.py ws.py config.py ...
│   └── requirements.txt
├── web/                Nuxt SPA (poyezd.uz'dan moslab) + Dockerfile
├── docker-compose.yml  backend + web (web :80)
└── .env.example
```

## Eslatma
- Ma'lumot `busdata` volume'da — konteyner qayta qurilса ham **oflayn kesh
  saqlanadi**. Bulut uzilса ham avtobus ishlaydi (mavjud kontent bilan).
- `KIOSK_API_KEY` — backend va web bir xil ishlatadi (.env'дан).
- Bir nechta avtobusни bir bulutдан boshqarasiz — har biri alohida qurilma
  sifatida panelда ko'rinadi.
