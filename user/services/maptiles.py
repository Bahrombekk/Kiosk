"""
maptiles.py — OSM xarita plitkalarini LOKAL keshga yuklab oladi (offline kiosk).

Kiosk internetga ulanmaydi, shuning uchun marshrut hududidagi (Toshkent–Samarqand)
xarita plitkalarini bir marta (internet bor paytda) yuklab olamiz va
`user/map_tiles/{z}/{x}/{y}.png` ga saqlaymiz. Keyin xarita to'liq offline ishlaydi.

Ishlatish (user/ ichida, internet bor paytda):
  py services/maptiles.py
"""
import os
import math
import time
import urllib.request

TILES_DIR = os.path.join(os.path.dirname(__file__), "..", "map_tiles")
# CARTO "voyager" bazaviy xaritasi (OSM ma'lumotidan, ruxsat etilgan, rangli, nomli).
# OSM rasmiy serveri bulk yuklashni bloklaydi, shuning uchun CARTO ishlatamiz.
TILE_URL = "https://a.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) KioskTrainMap/1.0"}

# Marshrut hududi (chekka bilan): kenglik/uzunlik chegaralari
# Toshkent(41.30,69.24) ... Samarqand(39.65,66.96)
LAT_MIN, LAT_MAX = 39.3, 41.6
LON_MIN, LON_MAX = 66.5, 69.6
ZOOMS = [7, 8, 9, 10]


def deg2num(lat, lon, z):
    """Geo koordinatani (lat,lon) zoom z dagi kasrli tile raqamiga aylantiradi."""
    n = 2 ** z
    x = (lon + 180.0) / 360.0 * n
    lat_r = math.radians(lat)
    y = (1.0 - math.asinh(math.tan(lat_r)) / math.pi) / 2.0 * n
    return x, y


def tile_path(z, x, y):
    return os.path.join(TILES_DIR, str(z), str(x), f"{y}.png")


def have_tile(z, x, y):
    p = tile_path(z, x, y)
    return os.path.isfile(p) and os.path.getsize(p) > 0


def download_region(lat_min=LAT_MIN, lat_max=LAT_MAX,
                    lon_min=LON_MIN, lon_max=LON_MAX, zooms=ZOOMS):
    got = skip = fail = 0
    for z in zooms:
        x1, y1 = deg2num(lat_max, lon_min, z)   # yuqori-chap
        x2, y2 = deg2num(lat_min, lon_max, z)   # quyi-o'ng
        xs = range(int(math.floor(x1)), int(math.floor(x2)) + 1)
        ys = range(int(math.floor(y1)), int(math.floor(y2)) + 1)
        print(f"zoom {z}: {len(list(xs))}x{len(list(ys))} tile", flush=True)
        for x in xs:
            for y in ys:
                if have_tile(z, x, y):
                    skip += 1
                    continue
                dest = tile_path(z, x, y)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                url = TILE_URL.format(z=z, x=x, y=y)
                try:
                    req = urllib.request.Request(url, headers=UA)
                    with urllib.request.urlopen(req, timeout=25) as r:
                        data = r.read()
                    if data and len(data) > 100:
                        with open(dest, "wb") as f:
                            f.write(data)
                        got += 1
                        time.sleep(0.08)   # OSM serveriga hurmat
                    else:
                        fail += 1
                except Exception as e:
                    fail += 1
                    print(f"  [FAIL] {z}/{x}/{y}: {e}", flush=True)
    print(f"\nTAYYOR: yuklandi={got}, mavjud={skip}, xato={fail}", flush=True)
    return got


if __name__ == "__main__":
    download_region()
