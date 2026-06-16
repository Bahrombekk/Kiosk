"""
fetch_map_assets.py — Bekat xaritasi uchun OFLAYN assetlarni yuklab oladi.

Nima yuklanadi (assets/map/ ichiga):
  - vendor/  : maplibre-gl.js + .css, pmtiles.js, protomaps-themes-base.js
  - fonts/   : MapLibre glyph (.pbf) — yozuvlar (label) chiqishi uchun
  - data/uzbekistan.pmtiles : VEKTOR xarita ma'lumoti (alohida, --pmtiles-url
               berilsa yuklanadi; aks holda qanday olish ko'rsatiladi)

Ishlatish (server papkasida, internet kerak — bir martalik):
    py tools/fetch_map_assets.py
    py tools/fetch_map_assets.py --pmtiles-url https://.../uzbekistan.pmtiles

Yuklab bo'lgach xarita TO'LIQ OFLAYN ishlaydi (internetsiz). Bu skript
ishlatilmasa ham xarita internet bo'lganda online (raster) rejimda ishlayveradi.
"""
import os
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
MAP_DIR = os.path.join(os.path.dirname(HERE), "assets", "map")
VENDOR = os.path.join(MAP_DIR, "vendor")
FONTS = os.path.join(MAP_DIR, "fonts")
DATA = os.path.join(MAP_DIR, "data")

VENDOR_FILES = {
    "maplibre-gl.js":  "https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js",
    "maplibre-gl.css": "https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css",
    "pmtiles.js":      "https://unpkg.com/pmtiles@3.2.1/dist/pmtiles.js",
    "protomaps-themes-base.js":
        "https://unpkg.com/protomaps-themes-base@4.0.1/dist/protomaps-themes-base.js",
}

# Protomaps "light" temasi ishlatadigan shriftlar va diapazonlar.
# Diapazonlar: Lotin + Lotin kengaytmasi + Kirill (o'zbek nomlari uchun yetarli).
FONT_STACKS = ["Noto Sans Regular", "Noto Sans Medium", "Noto Sans Italic"]
FONT_RANGES = ["0-255", "256-511", "512-767", "768-1023", "1024-1279"]
FONT_BASE = ("https://raw.githubusercontent.com/protomaps/basemaps-assets/"
             "main/fonts")

# O'zbekiston chegaralovchi to'rtburchak (lon_min, lat_min, lon_max, lat_max)
UZ_BBOX = "55.9,37.1,73.2,45.6"


def _get(url, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "kiosk-map-fetch"})
    with urllib.request.urlopen(req, timeout=60) as r, open(dst, "wb") as f:
        f.write(r.read())


def fetch_vendor():
    print("== Vendor kutubxonalar ==")
    for name, url in VENDOR_FILES.items():
        dst = os.path.join(VENDOR, name)
        try:
            _get(url, dst)
            print(f"  OK  {name}")
        except Exception as e:                        # noqa: BLE001
            print(f"  XATO {name}: {e}")


def fetch_fonts():
    print("== Shriftlar (glyphs) ==")
    ok = 0
    for stack in FONT_STACKS:
        for rng in FONT_RANGES:
            url = f"{FONT_BASE}/{urllib.parse.quote(stack)}/{rng}.pbf"
            dst = os.path.join(FONTS, stack, f"{rng}.pbf")
            try:
                _get(url, dst)
                ok += 1
            except Exception as e:                    # noqa: BLE001
                print(f"  XATO {stack}/{rng}: {e}")
    print(f"  {ok} ta glyph fayli yuklandi")


def fetch_pmtiles(url):
    print("== Vektor ma'lumot (PMTiles) ==")
    dst = os.path.join(DATA, "uzbekistan.pmtiles")
    try:
        _get(url, dst)
        mb = os.path.getsize(dst) / 1e6
        print(f"  OK  uzbekistan.pmtiles ({mb:.0f} MB)")
    except Exception as e:                            # noqa: BLE001
        print(f"  XATO: {e}")


def pmtiles_help():
    print("== Vektor ma'lumot (PMTiles) — qo'lda olish ==")
    print("  uzbekistan.pmtiles fayli alohida olinadi (xarita rasmi). Eng oson:")
    print("  1) https://github.com/protomaps/go-pmtiles relizidan 'pmtiles' ni oling")
    print("  2) O'zbekiston bo'lagini ajratib oling:")
    print("       pmtiles extract https://build.protomaps.com/<sana>.pmtiles \\")
    print(f"               assets/map/data/uzbekistan.pmtiles --bbox={UZ_BBOX}")
    print("     (<sana> — build.protomaps.com dagi eng so'nggi fayl, masalan 20240601)")
    print("  Yoki tayyor faylni olib assets/map/data/uzbekistan.pmtiles ga qo'ying.")
    print("  Bu fayl bo'lmasa ham xarita internet bo'lganda (raster) ishlaydi.")


def main():
    os.makedirs(MAP_DIR, exist_ok=True)
    fetch_vendor()
    fetch_fonts()
    pm_url = None
    if "--pmtiles-url" in sys.argv:
        i = sys.argv.index("--pmtiles-url")
        if i + 1 < len(sys.argv):
            pm_url = sys.argv[i + 1]
    if pm_url:
        fetch_pmtiles(pm_url)
    else:
        pmtiles_help()
    print("\nTayyor. Xarita endi assets/map/ dan ishlaydi.")


if __name__ == "__main__":
    main()
