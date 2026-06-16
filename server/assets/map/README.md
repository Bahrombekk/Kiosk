# Bekat xaritasi (oflayn vektor)

Bu papka admin oynasidagi **Bekatlar → Qo'shish/Tahrirlash** dialogidagi
interaktiv xaritani ta'minlaydi (MapLibre GL + PMTiles, OpenStreetMap ma'lumoti).

## Qanday ishlaydi

- Dialog ochilganda kichik **lokal HTTP server** (127.0.0.1, ixtiyoriy port)
  shu papkani beradi (`ui/mapserver.py`). PMTiles HTTP "Range" so'rovlarini
  talab qiladi — shuning uchun `file://` emas, lokal server orqali beriladi.
- `index.html` avval **lokal** kutubxonalarni (`vendor/`) yuklaydi; bo'lmasa
  CDN'dan (internet kerak).
- `data/uzbekistan.pmtiles` bo'lsa — **oflayn vektor** xarita (chiroyli,
  yozuvli). Bo'lmasa — **online raster** (OpenStreetMap) zaxira rejimi.

Demak: hech narsa qilmasangiz ham, internet bo'lsa xarita ishlaydi. To'liq
oflayn (internetsiz) qilish uchun quyidagini bajaring.

## Oflayn qilish (bir martalik, internet kerak)

Server papkasida:

```
py tools/fetch_map_assets.py
```

Bu `vendor/` (kutubxonalar) va `fonts/` (yozuvlar uchun glyph) ni yuklaydi.

So'ng **vektor ma'lumot** faylini oling (xarita rasmi, ~100-200 MB):

```
# go-pmtiles relizidagi 'pmtiles' bilan O'zbekiston bo'lagini ajratish:
pmtiles extract https://build.protomaps.com/<sana>.pmtiles \
        assets/map/data/uzbekistan.pmtiles --bbox=55.9,37.1,73.2,45.6
```

`<sana>` — build.protomaps.com dagi eng so'nggi fayl (masalan `20240601`).
Yoki tayyor `uzbekistan.pmtiles` faylni olib `data/` ga qo'ying.

URL ma'lum bo'lsa skript ham yuklab beradi:

```
py tools/fetch_map_assets.py --pmtiles-url https://.../uzbekistan.pmtiles
```

## Papka tuzilmasi

```
assets/map/
  index.html                 # xarita sahifasi (kodga kiritilgan)
  vendor/                    # maplibre-gl.js/.css, pmtiles.js, protomaps-themes-base.js
  fonts/<Shrift>/<range>.pbf # yozuv glyphlari
  data/uzbekistan.pmtiles    # vektor xarita ma'lumoti (alohida olinadi)
```

`vendor/`, `fonts/`, `data/` git'ga kiritilmaydi (katta/yuklab olinadigan).
Litsenziya: ma'lumot © OpenStreetMap (ODbL), Protomaps basemap.
