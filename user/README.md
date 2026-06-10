# Kiosk — Foydalanuvchi (user) ilovasi

Roadmapdagi **3-bosqich** (user kiosk poydevori) amalga oshirilgan:
kiosk oyna + navigatsiya + soat + serverga ulanish + 5 bo'lim skeleti.
Haqiqiy ekranlar (Videolar, Kitoblar...) keyingi bosqichlarda qo'shiladi.

## Ishga tushirish
```bash
pip install -r requirements.txt
python main.py
```
Server manzilini berish (ixtiyoriy):
```bash
set KIOSK_SERVER=http://192.168.1.1:8765   # Windows
python main.py
```

## Sinov tugmalari (faqat ishlab chiqishda)
- `Ctrl+T` — Light/Dark almashtirish
- `Ctrl+Shift+Q` — admin chiqishi (kiosk'dan chiqish)

## Tuzilma
- `core/config.py` — server manzili va ulanish sozlamalari (SHU YERNI o'zgartiring).
- `core/theme.py` — barcha ranglar va o'lchamlar (Figma bilan moslash uchun).
- `services/api.py` — server REST API mijozi (health + katalog metodlari).
- `main.py` — kiosk oyna, ulanish boshqaruvi, navigatsiya, mavzu.
- `players/video.py` — to'liq ekran VLC video pleyer (boshqaruv, bufer, seek).
- `players/reader.py` — kitob matn o'quvchi (boblar, sahifalash, hisoblagich).
- `players/audio.py` — audiokitob pleyeri (progress, 10s, tezlik 1x/1.5x/2x).
- `widgets/navbar.py` — yuqori navigatsiya paneli.
- `widgets/cover.py` — muqovani serverdan yuklab ko'rsatuvchi label (SVG/rasm).
- `widgets/card.py` — kontent kartochkasi (muqova, nom, janr·davomiylik).
- `widgets/modal.py` — markaziy modal oyna asosi (xira fon + panel).
- `screens/` — bo'lim sahifalari (`base.py` umumiy asos; `videos.py` to'liq, qolganlari skelet).
- `screens/connecting.py` — boshlang'ich / ulanish ekrani.
- `assets/icons/` — navigatsiya ikonkalari (SVG).

> Eslatma: video o'ynatish uchun qurilmaga **VLC** o'rnatilgan bo'lishi shart
> (LibVLC). `python-vlc` shunga tayanadi.

## Holat (Roadmap bo'yicha)
- [x] 3-bosqich: kiosk oyna, navigatsiya, ulanish ekrani, 5 bo'lim skeleti
- [x] 4-bosqich: Videolar moduli (tablar, qidiruv, kartochkalar, detal modal, VLC pleyer)
- [x] 5-bosqich: Kitoblar moduli (kartochkalar, detal modal, matn o'quvchi, audio pleyer)
- [x] 6-bosqich: Asosiy (status, reklama, tavsiyalar) va Xarita (timeline + sxematik xarita)
- [x] 7-bosqich: Saytlar (kartochkalar + QR kod + yo'riqnoma)
- [ ] 8-bosqich: WebSocket real-time

> Eslatma: bu ilova ishlashi uchun server (2-bosqich) kerak. Server bo'lmasa
> "Serverga ulanmoqda..." ekrani ko'rsatiladi (bu kutilgan xatti-harakat).
