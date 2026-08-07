# Avtobus — lokal veb-kiosk

Avtobuslar uchun **faqat veb** tizim: yo'lovchi telefondan avtobus Wi-Fi'iga
ulanib kino/multfilm/musiqa, kitob/audiokitob ko'radi, yo'nalish (bekatlar) va
reklamani ko'radi. **Kiosk ekrani / desktop KERAK EMAS** — hammasi telefonda.

Ikki o'rnatish yo'li bor:

| | **Native (Windows)** — TAVSIYA | Docker (Linux/alt) |
|---|---|---|
| Qurilma | Windows mini-PC | Linux / Raspberry Pi (yoki Windows+Docker) |
| Ko'rinishi | `AvtobusSetup.exe` (bitta o'rnatgich) | `git clone` + `docker compose` |
| Kod himoyasi | **Kuchli** — manba `.py` qurilmaga tushmaydi, maxfiy modullar mashina kodida (Nuitka) | Zaif — image ичida `.py` ochiq |
| Afto-start | **Windows Service** (boot'da, login shart emas) + watchdog | Docker `restart: unless-stopped` |
| Node/ffmpeg | Bundle qilingan (alohida o'rnatilmaydi) | Konteyner ичida |

Quyida asosan **native (Windows)** yo'li tavsiflanadi. Docker yo'li oxirida.

---

## 1. Arxitektura (native)

```
AVTOBUS qurilmasi (Windows mini-PC)  —  C:\Avtobus\
┌───────────────────────────────────────────────────────────┐
│  "Avtobus" Windows XIZMATI (NSSM) — boot'da avto, login yo'q │
│    └─ Avtobus.exe  (compiled backend, FastAPI, headless)    │──WSS──► KioskCloud
│         ├─ 127.0.0.1:8765  API/WS  (faqat lokal)            │◄─manifest─ (bulut)
│         └─ node.exe .output  → 0.0.0.0:80  (Nuxt veb)       │
│  AvtobusWatchdog (rejalashtirilgan vazifa) — hang bo'lsa qayta│
│  Ma'lumot: data.db + content\  (oflayn kesh, saqlanadi)     │
└───────────────────────────────────────────────────────────┘
        ▲ yo'lovchilar: http://<qurilma-IP>/   (avtobus Wi-Fi, HTTP)
```

- **Bitta jarayon** — `Avtobus.exe` backend'ni ko'taradi VA yonidagi `node.exe`
  bilan Nuxt veb'ni 80-portда ishga tushiradi (Docker/konteyner shart emas).
- Backend faqat `127.0.0.1` da; yo'lovchilar faqat 80-portдаgi veb'ni ko'radi.
- Qurilma bulutga o'zi ulanadi (chiquvchi WSS) — oq IP kerak emas.

---

## 2. Build (DASTURCHI mashinasida — mijozda emas)

> Bu bosqich **sizning** kompyuteringizda bir marta bajariladi. Natija —
> `AvtobusSetup.exe`. Mijoz faqat shu faylni oladi (manba kodni emas).

### 2.1. Talablar (build mashinasi)
- **Python 3.11** (`py -3.11`), so'ng: `pip install pyinstaller nuitka`
- **Node.js + npm** (web build uchun)
- **Visual Studio Build Tools (MSVC)** — Nuitka C kompilyatori uchun
- **Inno Setup 6** — o'rnatgichni yasash uchun (https://jrsoftware.org/isdl.php)
- `bus\vendor\` ichiga: `node.exe`, `ffmpeg.exe`, `nssm.exe`
  (qarang: [vendor/README.md](vendor/README.md))

### 2.2. Buyruqlar (PowerShell, `bus\` ichida)
```powershell
.\build.ps1                          # web build → Nuitka → PyInstaller → release\Avtobus\
$env:AVTOBUS_SETUP_PASS = "kuchli-parol"
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
# Natija: Output\AvtobusSetup.exe  (shifrlangan, parol bilan)
```

`build.ps1` bayroqlari: `-NoHarden` (Nuitka'siz, tez), `-SkipWeb` (web `.output`
tayyor bo'lsa qayta qurmaslik).

### 2.3. Kod himoyasi qatlamlari
1. **PyInstaller** — exe ичida faqat `.pyc` (manba `.py` YO'Q). Python 3.11
   bayt-kodini ommaviy dekompilyatorlar ishonchli ocholmaydi.
2. **Nuitka** — maxfiy modullar (`licensing`, `security`, `cloud_client`)
   `.pyd` (haqiqiy **mashina kodi**) — dekompilyatsiya qilinmaydi. Manba `.py`
   build vaqtida o'chiriladi, exe'ga tushmaydi.
3. **Ed25519 HW-lock litsenziya** — exe boshqa kompyuterга ko'chirilsa
   ishlamaydi (`data.db`/fayllarni ko'chirish foyda bermaydi).
4. **Inno Setup** — o'rnatgichning o'zi shifrlangan + parol bilan.

---

## 3. Litsenziya (majburiy — frozen exe litsenziyasiz BLOKLANADI)

Litsenziya har bir avtobus qurilmasiga **alohida** (uning HARDWARE ID siга)
bog'lanadi. Oqim:

1. **Qurilmadан HW ID olish** — o'rnatgandan keyin qurilmada Ish stolidagi
   **«Avtobus — holat»** yorlig'ini oching (yoki):
   ```
   C:\Avtobus\Avtobus.exe --hwid
   ```
2. **HW ID ni vendorga (sizga) yuboring.**
3. **Litsenziya yasash** (vendor mashinasida, maxfiy kalit bilan):
   ```
   py -3 ..\server\tools\license_tool.py issue --hw <HW-ID> \
       --customer "Avtobus X" --days 365 --kiosks 1 -o license.key
   ```
   (bus va poyezd bir xil vendor kalit juftligidan foydalanadi.)
4. **Litsenziyani o'rnatish** (qurilmada):
   ```
   C:\Avtobus\Avtobus.exe --license C:\yo'l\license.key
   ```
   Xizmat faylni avtomatik qayta o'qiydi (restart shart emas). Tekshirish:
   `Avtobus.exe --license-status`.

> Eng qulay: qurilmani sotishdan oldin build mashinasida license.key ni
> `release\Avtobus\` ga qo'ysangiz — installerга kirib ketadi (lekin u holda
> HW ID ni oldindan bilishingiz kerak).

---

## 4. O'rnatish (avtobus qurilmasida)

1. `AvtobusSetup.exe` ni ishga tushiring (admin). Parolni kiriting.
2. Sehrgar so'raydi: **bulut domeni** (masalan `cloud.poyezd.uz`), **avtobus
   nomi**, ixtiyoriy **ulash kaliti**.
3. Tugagach: xizmat ishga tushadi, veb 80-portда, firewall ochiladi.
4. Litsenziyani o'rnating (3-bo'lim) — aks holda ekran bloklangan bo'ladi.
5. Bulut panelida qurilmani **«Tasdiqlang»** (ulash kaliti berilган bo'lsa
   avtomatik).

Yo'lovchi: avtobus Wi-Fi → brauzerда `http://<qurilma-IP>/`.

---

## 5. "O'chib qolsa afto yonib qolsin" — chidamlilik

| Holat | Nima qoplaydi |
|---|---|
| Dastur **qulasa** (crash) | NSSM xizmat 3 soniyada avto-restart |
| Qurilma **qayta yuklansa** (reboot) | Xizmat `Automatic` — boot'da o'zi yonadi, **login SHART EMAS** |
| Dastur **osilib qolsa** (hang) | `AvtobusWatchdog` (har 2 daq.) — 3 marta ketma-ket `/api/health` javob bermasa qayta yoqadi |
| **Tok uzilib, keyin qaytsa** | ⚠ Buni faqat **BIOS** qila oladi — pastga qarang |

### BIOS: tok qaytганda avto-yoqilish (bir martalik sozlama)
Qurilma BIOS/UEFI ga kiring (odatda `Del`/`F2`) va toping:
**«Restore on AC Power Loss»** / «AC Back» / «After Power Failure» →
**«Power On»** (yoki «Last State») ga qo'ying. Shundан keyin tok kelганда
qurilma o'zi yonadi, Windows boot bo'ladi, xizmat ishga tushadi — hech kim
tegмaydi.

---

## 6. Boshqarish (qurilmada, admin PowerShell)

```powershell
C:\Avtobus\nssm.exe status  Avtobus      # holat
C:\Avtobus\nssm.exe restart Avtobus      # qayta ishga tushirish
C:\Avtobus\nssm.exe stop    Avtobus      # to'xtatish (watchdog tegmaydi)
Get-Content C:\Avtobus\logs\service.log -Tail 50   # loglar
Get-Content C:\Avtobus\logs\web.log     -Tail 50   # veb (node) loglari
```

**Yangilash:** yangi `AvtobusSetup.exe` ni ustidan ishga tushiring — `data.db`,
`content\`, `license.key` **saqlanadi**, faqat dastur fayllari yangilanadi.

**O'chirish:** «Dasturlar qo'shish/o'chirish» → Avtobus. Xizmat, watchdog va
firewall qoidasi olib tashlanadi.

---

## 7. Docker / Linux yo'li (muqobil)

Windows'siz (Raspberry Pi, Linux mini-PC yoki Docker'li Windows) uchun eski yo'l
saqlangan — lekin **kod himoyasi zaif** (image ичида `.py` ochiq):

```bash
git clone <repo> /opt/avtobus && cd /opt/avtobus/bus
bash setup.sh            # Linux    (yoki .\setup.ps1  — Windows+Docker)
```
`.env`: `KIOSK_API_KEY`, `KIOSK_NAME`, `KIOSK_CLOUD_URL`. Boshqarish:
`docker compose logs -f | restart | down`, yangilash `git pull && docker compose up -d --build`.

---

## 8. Tuzilma

```
bus/
├── backend/            headless FastAPI (PyQt YO'Q)
│   ├── main.py         API/WS + veb'ni ko'taradi (--hwid/--license CLI)
│   ├── web_server.py   Nuxt (node) bola jarayonini boshqaradi
│   ├── licensing.py security.py cloud_client.py   ← Nuitka .pyd bo'ladi
│   ├── avtobus.spec    PyInstaller (build.ps1 vaqtinchalik nusxada ishlatadi)
│   └── requirements.txt
├── web/                Nuxt SPA (ssr:false) + Nitro proksi
├── vendor/             node.exe / ffmpeg.exe / nssm.exe (repoga kirmaydi)
├── build.ps1           web → Nuitka → PyInstaller → release\Avtobus\
├── installer.iss       Inno Setup → Output\AvtobusSetup.exe
├── watchdog.ps1        hang bo'lsa xizmatni qayta yoqadi
├── holat.bat           HW ID / litsenziya holatini ko'rsatadi
└── docker-compose.yml setup.sh setup.ps1   (Docker/Linux muqobil yo'li)
```

## Eslatma
- Ma'lumot `data.db` + `content\` da — yangilash/restart'да **saqlanadi**.
  Bulut uzilса ham avtobus ishlaydi (mavjud kontent bilan).
- `KIOSK_API_KEY` avtomatik yaratiladi (`data.db`) — veb undан foydalanadi.
- Bir nechta avtobusни bir bulutдан boshqarasiz — har biri alohida qurilma.
