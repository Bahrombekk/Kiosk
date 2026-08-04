# Kiosk qurilmasini to'liq qulflash — texnik qo'llanma

Bu hujjat poyezdga o'rnatiladigan kiosk kompyuterini yo'lovchi chiqib keta
olmaydigan holatga keltirish bosqichlarini tushuntiradi.

## Himoya qatlamlari (nima nimadan himoya qiladi)

| Qatlam | Nima qiladi | Qayerda |
|---|---|---|
| Ilova (Qt) | Esc, Alt+F4, o'ng tugma bloklangan; chiqish faqat PIN bilan | `main.py` |
| Klaviatura hook | Win, Alt+Tab, Alt+Esc, Ctrl+Esc bloklanadi | `system/lockdown.py` (frozen buildda avto) |
| Registry siyosatlari | Task Manager, Win+L, Win tugmalari o'chadi | installer "lockdown" vazifasi |
| Watchdog | Ilova qulasa avto qayta ochadi | `KioskWatchdog.exe` (autostart) |
| Maxsus foydalanuvchi + shell | Explorer (ish stoli/panel) umuman yuklanmaydi | quyidagi qo'lda bosqich |

**Eslatma:** Ctrl+Alt+Del ni hech qaysi dastur bloklay olmaydi (Windows
himoyalangan ketma-ketligi). Lekin registry siyosatlari tufayli u ochadigan
menyuda Task Manager va Qulflash ishlamaydi — faqat "Chiqish" qoladi, undan
keyin esa autostart kioskni qayta ochadi.

## 1. Oddiy o'rnatish (minimal)

1. `KioskSetup.exe` ni ishga tushiring (parol so'raladi).
2. Server manzili va **API kalit**ni kiriting (kalit server admin oynasining
   Boshqaruv sahifasida, "Nusxalash" tugmasi).
3. "Kiosk qulflash siyosatlarini yoqish" belgisini qoldiring.
4. O'rnatish tugagach kiosk avtomatik ochiladi.

Bu darajada: ilova fullscreen, klaviatura kombinatsiyalari va Task Manager
bloklangan, crash bo'lsa watchdog qayta ochadi.

## 2. To'liq qulflash (tavsiya etiladi — yo'lovchi ko'p muhitda)

Maqsad: kiosk **admin bo'lmagan alohida foydalanuvchi**da ishlasin va
Explorer o'rnida to'g'ridan-to'g'ri kiosk ochilsin (ish stoli umuman yo'q).

### 2.1. Kiosk foydalanuvchisini yaratish (admin sifatida)

PowerShell (admin):

```powershell
# Yangi standart foydalanuvchi (parol kiriting va yozib qo'ying)
net user kiosk * /add
# MUHIM: Administrators guruhiga QO'SHMANG — standart bo'lib qolsin
```

Yoki tayyor skript: `setup_kiosk_user.ps1` (shu papkada).

### 2.2. Avto-kirish (auto-logon)

1. `Win+R` → `netplwiz`
2. `kiosk` foydalanuvchisini tanlang, "Users must enter a user name and
   password..." belgisini OLIB TASHLANG → OK → kiosk parolini kiriting.

### 2.3. Shell almashtirish (Explorer o'rnida Kiosk)

`kiosk` foydalanuvchisi sifatida kirib (yoki uning HKCU'siga), registry:

```
HKEY_CURRENT_USER\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon
  Shell = C:\Kiosk\KioskWatchdog.exe     (REG_SZ)
```

Endi bu foydalanuvchi kirganda ish stoli/panel o'rniga to'g'ridan-to'g'ri
kiosk ochiladi — chiqadigan joyning o'zi yo'q.

### 2.4. Tiklanish yo'li (texnik xizmat)

1. Ctrl+Alt+Del → "Chiqish" (Sign out)
2. Kirish ekranida **admin** hisobiga kiring (parol bilan)
3. Admin muhitida hamma narsa odatdagidek (Explorer, Task Manager*)

\* Agar registry siyosatlari xalal bersa: `C:\Kiosk\lockdown_off.reg` ni
ishga tushiring, ishni tugatgach `C:\Kiosk\lockdown_on.reg` bilan qaytaring.

### Muqobil: Windows Assigned Access / Shell Launcher

Windows 10/11 **Pro/Enterprise**'da Microsoft'ning rasmiy kiosk rejimi bor
(Sozlamalar → Hisoblar → Boshqa foydalanuvchilar → "Kiosk sozlash" yoki
Shell Launcher xizmati). UWP bo'lmagan ilovalar uchun Shell Launcher kerak —
yuqoridagi Winlogon Shell usuli soddaroq va bir xil natija beradi.

## 3. Tarmoq tavsiyasi

Kiosk va server **alohida VLAN yoki alohida Wi-Fi SSID**da bo'lsin —
yo'lovchi Wi-Fi'sidan ajratilgan. API kalit begona so'rovlarni to'sadi,
lekin tarmoq darajasidagi ajratish eng arzon va kuchli himoya.

## 4. Tekshirish ro'yxati (o'rnatishdan keyin)

- [ ] Win tugmasi ishlamaydi, Alt+Tab ishlamaydi
- [ ] Ctrl+Alt+Del → Task Manager kulrang/yo'q, Qulflash yo'q
- [ ] Esc, Alt+F4 kioskni yopmaydi
- [ ] Soatga 7 marta teginish → PIN → chiqish ishlaydi
- [ ] Task Managersiz: `taskkill` o'rniga kompyuterni o'chirib yoqing —
      kiosk avtomatik qaytadi (watchdog + autostart)
- [ ] Tarmoq kabelini chiqaring — kiosk "Oflayn" rejimda ishlashda davom etadi
