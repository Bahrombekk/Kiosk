# Bulutni serverga (VPS) qo'yish

`cloud/` — **mustaqil ilova**. Ko'chirish uchun boshqa hech narsa kerak emas:
`server/`, `web/`, `kiosk/` — hech biri. PyQt ham, Node.js ham kerak emas.

```
VPS ga ko'chiriladigan narsa:      cloud/  (kodi ~1 MB)
Kerak bo'ladigan narsa:            Python 3.10+ va 3 ta paket
```

> **Nega super-admin paneli `web/` papkasida emas?**
> `web/` — YO'LOVCHILAR uchun (poyezd.uz), poyezd serverining ichida, vagon
> Wi-Fi'ida, internetsiz ishlaydi va `KioskServerSetup.exe` ichiga qo'shiladi.
> Agar super-admin paneli ham o'sha yerda bo'lsa, u **har bir poyezdga
> tarqatilardi** va vagon Wi-Fi'idan ochilib qolardi. Bulut paneli esa
> `cloud/static/` da — bulut jarayonining o'zi beradi, faqat internetда,
> parol ostida. Ikkisi hech qachon bir mashinada turmaydi.

---

## 1. Fayllarni ko'chirish

```bash
# Kompyuterda (Windows) — faqat kodni yig'amiz
scp -r cloud root@<VPS_IP>:/opt/kioskcloud
```

`storage/`, `cloud.db`, `logs/`, `cloud_signing_key.pem` — **ko'chirilmaydi**
(yangi serverда o'zi yaratiladi). Agar mavjud bulutni KO'CHIRAYOTGAN bo'lsangiz,
aynan shu 3 narsani ham olib o'tish kerak — pastdagi "Ko'chirish" bo'limiga qarang.

## 2. Python va paketlar

```bash
apt update && apt install -y python3 python3-venv python3-pip nginx
cd /opt/kioskcloud
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

## 3. Xizmat sifatida ishga tushirish (systemd)

```bash
cp deploy/kioskcloud.service /etc/systemd/system/
# Parolni o'zgartiring:
nano /etc/systemd/system/kioskcloud.service     # CLOUD_ADMIN_PASS=...
systemctl daemon-reload
systemctl enable --now kioskcloud
systemctl status kioskcloud          # ishlayaptimi
journalctl -u kioskcloud -f          # loglar
```

## 4. Domen va HTTPS (nginx + Let's Encrypt)

```bash
cp deploy/nginx-kioskcloud.conf /etc/nginx/sites-available/kioskcloud
ln -s /etc/nginx/sites-available/kioskcloud /etc/nginx/sites-enabled/
nano /etc/nginx/sites-available/kioskcloud       # server_name -> o'z domeningiz
nginx -t && systemctl reload nginx

apt install -y certbot python3-certbot-nginx
certbot --nginx -d cloud.poyezd.uz               # o'z domeningiz
```

DNS'da `cloud.poyezd.uz` → VPS IP (A yozuvi) bo'lishi kerak.

## 5. Poyezd serverlarini ulash

Har bir poyezd serverida faqat domenni ko'rsatasiz:

```
server/cloud.txt:
url=cloud.poyezd.uz
```

Yoki admin oynasi → **Sozlamalar → Markaziy bulut** → domen → Saqlash →
serverni qayta ishga tushirish. So'ng bulut panelida **Tasdiqlash**.

Build vaqtida `server/config.py` dagi `CLOUD_URL_DEFAULT` ga domenni yozib
qo'ysangiz, o'rnatuvchi hech narsa kiritmaydi.

---

## Zaxira nusxa (juda muhim)

Uch narsa: bazani, omborni va **imzo kalitini**.

```bash
systemctl stop kioskcloud
tar czf /root/kioskcloud-$(date +%F).tar.gz \
    -C /opt/kioskcloud cloud.db cloud_signing_key.pem storage
systemctl start kioskcloud
```

> `cloud_signing_key.pem` yo'qolsa — ro'yxatdan o'tgan **barcha serverlar**
> bulut buyruqlarini rad etadi (ochiq kalit ularda saqlangan) va har birini
> qaytadan ulash kerak bo'ladi. Shu faylni albatta saqlab qo'ying.

## Bulutni boshqa serverga ko'chirish

Domen ishlatilganда poyezdlarda **hech narsa o'zgartirilmaydi**:

1. Yangi VPSда 1–3 qadamlarni bajaring (xizmatni hali yoqmang).
2. Eski serverdan `cloud.db`, `cloud_signing_key.pem` va `storage/` ni
   yangisiga ko'chiring (`/opt/kioskcloud/` ichiga).
3. `systemctl start kioskcloud`, so'ng DNS'ni yangi IP'ga qaratasiz.
4. Serverlar TTL o'tishi bilan o'zi qayta ulanadi — hech qanday sozlama
   o'zgartirmaydi.

## Diskni rejalashtirish

Ombor sha256 bo'yicha **dedup** qiladi: bir xil fayl ikki marta yuklansa diskda
bitta nusxa. Taxminan: 100 kino × 1.5 GB ≈ 150 GB. Panelning **Boshqaruv**
sahifasidagi "Ombor" kartasi band va bo'sh joyni ko'rsatadi.

## Muhit o'zgaruvchilari

`kioskcloud.service` ichida beriladi (yoki `.env` fayl bilan):

| O'zgaruvchi | Vazifasi |
|---|---|
| `CLOUD_ADMIN_PASS` | admin paroli (berilса har startda shunga qaytadi) |
| `CLOUD_PORT` | ichki port (nginx shunga proksi qiladi), standart 9000 |
| `CLOUD_DB` / `CLOUD_STORAGE` | baza va ombor yo'llari |
| `CLOUD_MAX_UPLOAD` | fayl chegarasi (bayt), standart 8 GB |
| `CLOUD_DL_TTL` | yuklab olish havolasining muddati (soniya) |

Parolni keyin almashtirish: `venv/bin/python tools/set_password.py <parol>`
(bulutni to'xtatish shart emas).
