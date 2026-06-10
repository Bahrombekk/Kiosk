"""
seed_route_xiva.py — Toshkent—Xiva yo'nalishini bazaga yozadi.

Manba: rasmiy jadval Excel fayllari ("Поезд 076Ф Ташкент — Хива.xlsx" va
"Поезд_Ташкент_—_Хива,_Хива_Ташкент.xlsx" — loyiha ildizida). Vaqtlar
Excel'dagi kun-ulushi formatidan HH:MM ga o'girilgan.

Ishlatish (server papkasida):
    py tools/seed_route_xiva.py             # 076Ф Toshkent -> Xiva
    py tools/seed_route_xiva.py --reverse   # 056Ж Xiva -> Toshkent

route_stops jadvali TOZALANIB qayta yoziladi; settings'dagi train_name,
route va depart_time ham mos yangilanadi. Kontent/reklama/saytlarga tegmaydi.

DIQQAT: yirik shaharlar koordinatalari aniq; kichik bekatlar (Zirabuloq,
Ziyovuddin, Jayhun...) TAXMINIY — admin oynasining "Bekatlar" sahifasida
lat/lng ni aniqlashtirish mumkin (xaritadagi nuqta shunga qarab chiziladi).
"""
import os
import sys

# Skript tools/ ichida — server ildizidagi db modulini topish uchun
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db

# (nom, kelish, jo'nash, lat, lng, km)
# 076Ф Toshkent—Xiva (jo'nash 22:34, yetib kelish 13:33 — ertasi kun)
TASHKENT_XIVA = [
    ("Toshkent-Janubiy", None,    "22:34", 41.2646, 69.2163, 0),
    ("Guliston",         "23:47", "23:50", 40.4897, 68.7842, 112),
    ("Jizzax",           "01:01", "01:04", 40.1158, 67.8422, 237),
    ("Samarqand",        "02:21", "03:00", 39.6542, 66.9597, 350),
    ("Jum'a",            "03:25", "03:32", 39.7203, 66.6648, 380),
    ("Kattaqo'rg'on",    "04:00", "04:02", 39.8989, 66.2614, 425),
    ("Zirabuloq",        "04:20", "04:34", 39.9400, 66.0000, 450),   # taxminiy
    ("Ziyovuddin",       "04:53", "04:55", 39.9510, 65.6820, 480),   # taxminiy
    ("Navoiy",           "05:12", "05:17", 40.0844, 65.3792, 506),
    ("Qiziltepa",        "05:49", "05:54", 40.0336, 64.8511, 555),
    ("Buxoro-1",         "06:28", "06:48", 39.7220, 64.5447, 599),
    ("Jayhun",           "10:22", "10:39", 39.2000, 63.6000, 830),   # taxminiy
    ("Hazorasp",         "12:04", "12:09", 41.3194, 61.0742, 972),
    ("Urganch",          "12:53", "13:03", 41.5500, 60.6333, 1016),
    ("Xiva",             "13:33", None,    41.3783, 60.3639, 1049),
]
TASHKENT_XIVA_META = {
    "train_name": "076Ф TOSHKENT — XIVA",
    "route": "Toshkent → Xiva",
    "depart_time": "22:34",
    "duration": "14s 59d",
}

# 056Ж Xiva—Toshkent (jo'nash 16:20, yetib kelish 07:09 — ertasi kun)
XIVA_TASHKENT = [
    ("Xiva",             None,    "16:20", 41.3783, 60.3639, 0),
    ("Urganch",          "16:50", "17:20", 41.5500, 60.6333, 33),
    ("Hazorasp",         "18:02", "18:07", 41.3194, 61.0742, 77),
    ("Buxoro-1",         "23:15", "23:45", 39.7220, 64.5447, 450),
    ("Navoiy",           "00:58", "01:02", 40.0844, 65.3792, 543),
    ("Samarqand",        "02:39", "03:11", 39.6542, 66.9597, 699),
    ("Jizzax",           "04:36", "04:38", 40.1158, 67.8422, 812),
    ("Guliston",         "05:51", "05:53", 40.4897, 68.7842, 937),
    ("Toshkent-Janubiy", "07:09", None,    41.2646, 69.2163, 1049),
]
XIVA_TASHKENT_META = {
    "train_name": "056Ж XIVA — TOSHKENT",
    "route": "Xiva → Toshkent",
    "depart_time": "16:20",
    "duration": "14s 49d",
}


def seed(reverse=False):
    db.init_db()
    stops = XIVA_TASHKENT if reverse else TASHKENT_XIVA
    meta = XIVA_TASHKENT_META if reverse else TASHKENT_XIVA_META

    conn = db.connect()
    try:
        conn.execute("DELETE FROM route_stops")
        conn.executemany(
            """INSERT INTO route_stops
               (name, arrival_time, departure_time, latitude, longitude,
                distance_km, sort_order)
               VALUES (?,?,?,?,?,?,?)""",
            [(n, arr, dep, lat, lng, km, i)
             for i, (n, arr, dep, lat, lng, km) in enumerate(stops)])
        conn.commit()
    finally:
        conn.close()

    for k, v in meta.items():
        db.set_setting(k, v)
    db.log_action("route_seeded", meta["route"])

    # Windows konsoli (cp1251) → kabi belgilarni chiqara olmaydi — ASCII print
    route_ascii = meta["route"].replace("→", "->")
    print(f"OK: {len(stops)} ta bekat yozildi - {route_ascii}")
    print(f"    Poyezd: {meta['train_name']}, jo'nash {meta['depart_time']}")
    print("Eslatma: kichik bekatlar koordinatalari taxminiy - admin")
    print("'Bekatlar' sahifasida aniqlashtirishingiz mumkin.")


if __name__ == "__main__":
    seed(reverse="--reverse" in sys.argv)
