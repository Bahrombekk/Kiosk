# Kontent sinxronlash (LAN orqali)

Bu kompyuterdagi kontentni (media fayllar + baza yozuvlari) boshqa
kompyuterdagi o'rnatilgan **Kiosk Server** exe'siga **qo'shish** vositasi.

Rejim: **xavfsiz qo'shish** — nishon serverning `api_key`, litsenziyasi,
ulangan kiosklari va statistikasi saqlanadi. Faqat `content`, `ads`, `sites`,
`route_stops` yozuvlari (dublikatsiz) va yetishmagan media fayllar ko'chiriladi.
Ikkala kompyuter bitta LAN'da bo'lishi kerak.

## 1-qadam — NISHON kompyuterda (kontent boradigan)

`receiver.ps1` ni o'sha kompyuterga ko'chiring va PowerShell'da ishga tushiring:

```powershell
powershell -ExecutionPolicy Bypass -File receiver.ps1
```

Papka standart joyda (`C:\KioskServer`) bo'lmasa yoki server ishlamayotgan bo'lsa:

```powershell
powershell -ExecutionPolicy Bypass -File receiver.ps1 -BaseDir "D:\KioskServer"
```

U ekranga shunga o'xshash qatorlar chiqaradi — **bittasini** (LAN IP'sini)
manba kompyuterga bering:

```
--host 192.168.1.151 --port 8799 --token b8bfd4285abf46b0
```

Python kerak emas — Windows'ning tayyor PowerShell'i yetarli. Admin ham shart emas.

## 2-qadam — MANBA kompyuterda (shu kompyuter)

Nishon bergan qatorni qo'shib ishga tushiring:

```powershell
py -3 sender.py --host 192.168.1.151 --port 8799 --token b8bfd4285abf46b0
```

U avtomatik:
1. nishon serverini to'xtatadi,
2. bazasini oladi va bizning kontentni qo'shadi (dublikatsiz),
3. yetishmagan media fayllarni yuklaydi (bor bo'lganini o'tkazadi),
4. yangilangan bazani yuboradi,
5. serverni qayta ishga tushiradi.

Manba papka standart `server/`. Boshqa joyda bo'lsa `--source "C:\yo'l\server"`.

## Xususiyatlar

- **Resume**: uzilib qolsa, qayta ishga tushiring — mavjud fayllar va yozuvlar
  o'tkazib yuboriladi, dublikat yaratilmaydi.
- **Xavfsiz**: nishonning sozlamalari/kalitlari/kiosklari tegilmaydi.
- Katta fayllar bo'lakma-bo'lak (stream) ketadi, RAM'ni to'ldirmaydi.

## Eslatma

Nishon kompyuterda Windows Xavfsizlik devori (firewall) `receiver.ps1` uchun
port so'rasa — **Ruxsat berish** (Allow) ni bosing. Yoki oldindan:

```powershell
netsh advfirewall firewall add rule name="KioskSync" dir=in action=allow protocol=TCP localport=8799
```
