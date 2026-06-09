# Kiosk — Foydalanuvchi ilovasi (poydevor)

Bu — 3-bosqich poydevori: kiosk oyna + Figma'dagi navigatsiya + soat + 5 bo'lim.
Haqiqiy ekranlar (Asosiy, Videolar, Kitoblar...) keyingi bosqichlarda qo'shiladi.

## Ishga tushirish
```bash
pip install PyQt6
python main.py
```

## Sinov tugmalari (faqat ishlab chiqishda)
- `Ctrl+T` — Light/Dark almashtirish (Figma bilan solishtirish uchun)
- `Ctrl+Shift+Q` — admin chiqishi (kiosk'dan chiqish)

## Fayllar
- `theme.py` — barcha ranglar va o'lchamlar SHU YERDA. Figma bilan moslash uchun shu faylni tahrirlang.
- `main.py` — kiosk oyna, navigatsiya, bo'limlar.
- `widgets/navbar.py` — yuqori navigatsiya paneli.
- `assets/icons/` — ikonkalar (Figma "Icons" sahifasidan eksport qilib almashtiring).

## Figma'ga 100% moslash uchun
1. Figma "Icons" sahifasidan 5 ikonkani SVG qilib eksport qiling
   (home, map, video, book, globe) va `assets/icons/` ichidagilarni almashtiring.
2. Figma "Inspect" panelidan aniq ranglarni (HEX) olib `theme.py` ga qo'ying.
3. Shrift: "Inter" o'rnatilsa Figma bilan bir xil bo'ladi.
