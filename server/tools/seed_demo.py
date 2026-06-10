"""
seed_demo.py — Kioskni ERKIN LITSENZIYALI namunaviy kontent bilan to'ldiradi.

Nega bu fayl bor:
  data.db dagi boshlang'ich seed faqat fayl NOMLARINI (baron.mp4 ...) yozadi,
  lekin haqiqiy media fayllar yo'q edi. Bu skript ochiq (Creative Commons /
  public domain) namunaviy media yuklab oladi va content jadvalini ularga
  moslab QAYTA YOZADI. Mualliflik huquqi bilan himoyalangan kino/musiqa
  YUKLANMAYDI — keyin admin paneli orqali haqiqiy litsenziyali fayllar bilan
  almashtiring.

Manbalar (barchasi erkin):
  - Blender ochiq filmlari (CC-BY): test-videos.co.uk, media.w3.org, archive.org
  - SoundHelix (erkin musiqa namunalari)
  - Lorem Picsum (erkin fotosuratlar — demo muqovalar)

Ishlatish (server/ ichida):
  py tools/seed_demo.py
"""
import os
import sys
import time
import json
import urllib.request

# Skript tools/ ichida — server ildizidagi config/db modullarini topish uchun
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import db

UA = {"User-Agent": "Mozilla/5.0 (KioskSeeder)"}


def download(candidates, dest, min_bytes=10_000, max_seconds=45):
    """candidates URL'larini ketma-ket sinaydi; birinchi to'liq yuklanganni saqlaydi.
    max_seconds — bitta yuklash uchun vaqt chegarasi (sekin manba butun skriptni
    qotirib qo'ymasligi uchun). Mavjud yetarli faylni qayta yuklamaydi."""
    name = os.path.basename(dest)
    done_marker = dest + ".done"
    # Faqat TO'LIQ yuklangan (.done belgisi bor) faylni o'tkazib yuboramiz
    if os.path.isfile(dest) and os.path.isfile(done_marker) \
            and os.path.getsize(dest) >= min_bytes:
        print(f"  [skip] mavjud: {name} ({os.path.getsize(dest)//1024} KB)", flush=True)
        return True
    for url in candidates:
        try:
            print(f"  [get] {name} <- {url}", flush=True)
            req = urllib.request.Request(url, headers=UA)
            t0 = time.time()
            with urllib.request.urlopen(req, timeout=20) as r:
                expected = r.headers.get("Content-Length")
                expected = int(expected) if expected else None
                with open(dest, "wb") as f:
                    while True:
                        if time.time() - t0 > max_seconds:
                            raise TimeoutError(f"deadline {max_seconds}s")
                        chunk = r.read(1 << 16)
                        if not chunk:
                            break
                        f.write(chunk)
            size = os.path.getsize(dest)
            if expected and size < expected:
                raise IOError(f"chala: {size}/{expected} bayt")
            if size >= min_bytes:
                open(done_marker, "w").close()
                print(f"        OK {size//1024} KB ({time.time()-t0:.1f}s)", flush=True)
                return True
            print(f"        juda kichik ({size} b)", flush=True)
        except Exception as e:
            print(f"        o'tkazildi: {e}", flush=True)
        # yarim/buzuq fayl qolmasin
        if os.path.isfile(dest) and os.path.getsize(dest) < min_bytes:
            try:
                os.remove(dest)
            except OSError:
                pass
    print(f"  [FAIL] {name}", flush=True)
    return False


def cover_url(seed, w=400, h=560):
    return [f"https://picsum.photos/seed/{seed}/{w}/{h}.jpg",
            f"https://picsum.photos/seed/{seed}/{w}/{h}"]


# ---- TEZ va ISHONCHLI video manbalar (test-videos.co.uk, media.w3.org) ----
# ---- + ixtiyoriy HAQIQIY ochiq filmlar (archive.org, sekin bo'lsa o'tkaziladi) ----
VIDEOS = [
    dict(key="sintel", type="movie", title="Sintel", author="Blender Foundation",
         genre="Fantastika", category_tab="Kinolar", duration=888, rec=1, big=False,
         desc="Blenderning ochiq qisqa filmi (CC-BY) — yo'qolgan ajdarni izlagan qiz.",
         file="sintel.mp4",
         urls=["https://test-videos.co.uk/vids/sintel/mp4/h264/720/Sintel_720_10s_20MB.mp4",
               "https://media.w3.org/2010/05/sintel/trailer.mp4",
               "https://test-videos.co.uk/vids/sintel/mp4/h264/720/Sintel_720_10s_5MB.mp4"]),
    dict(key="jellyfish", type="movie", title="Suv osti olami", author="Tabiat",
         genre="Hujjatli, Tabiat", category_tab="Kinolar", duration=10, rec=0, big=False,
         desc="Akvariumdagi meduzalarning tiniq video yozuvi (erkin namuna).",
         file="jellyfish.mp4",
         urls=["https://test-videos.co.uk/vids/jellyfish/mp4/h264/720/Jellyfish_720_10s_20MB.mp4",
               "https://test-videos.co.uk/vids/jellyfish/mp4/h264/720/Jellyfish_720_10s_5MB.mp4"]),
    dict(key="w3sample", type="movie", title="Namuna film (W3C)", author="W3C",
         genre="Namuna", category_tab="Kinolar", duration=28, rec=0, big=False,
         desc="Qisqa erkin video namunasi — striming sinovini ko'rsatadi.",
         file="w3sample.mp4",
         urls=["https://media.w3.org/2010/05/video/movie_300.mp4"]),
    # --- Haqiqiy ochiq filmlar (archive.org sekin bo'lsa, o'tkazib yuboriladi) ---
    dict(key="elephants_dream", type="movie", title="Elephants Dream",
         author="Blender Foundation", genre="Ilmiy-fantastika",
         category_tab="Kinolar", duration=654, rec=0, big=True,
         desc="Dunyodagi birinchi ochiq (open-source) animatsion film.",
         file="elephants_dream.mp4",
         urls=["https://archive.org/download/ElephantsDream/ed_1024_512kb.mp4",
               "https://archive.org/download/ElephantsDream/ed_hd_512kb.mp4"]),
    dict(key="tears_of_steel", type="movie", title="Tears of Steel",
         author="Blender Foundation", genre="Ilmiy-fantastika",
         category_tab="Kinolar", duration=734, rec=0, big=True,
         desc="Amsterdamda suratga olingan ochiq sci-fi qisqa film.",
         file="tears_of_steel.mp4",
         urls=["https://archive.org/download/tears_of_steel_1080p/tears_of_steel_1080p.mp4"]),
    # --- Multfilm ---
    dict(key="big_buck_bunny", type="cartoon", title="Big Buck Bunny",
         author="Blender Foundation", genre="Multfilm, Komediya",
         category_tab="Multfilmlar", duration=596, rec=0, big=False,
         desc="Mashhur ochiq animatsion multfilm — quyon va sho'x kemiruvchilar.",
         file="big_buck_bunny.mp4",
         urls=["https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/720/Big_Buck_Bunny_720_10s_20MB.mp4",
               "https://media.w3.org/2010/05/bunny/trailer.mp4",
               "https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/720/Big_Buck_Bunny_720_10s_5MB.mp4"]),
]

AUDIO = [
    dict(key="concert", type="music", title="Instrumental namuna",
         author="Erkin namuna", genre="Instrumental", category_tab="Musiqa",
         duration=372, rec=0, desc="Erkin litsenziyali namunaviy musiqa.",
         file="concert.mp3",
         urls=["https://cdn.jsdelivr.net/gh/rafaelreis-hotmart/Audio-Sample-files@master/sample.mp3",
               "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"]),
    dict(key="music2", type="music", title="Death Becomes Fur",
         author="Jan Morgenstern", genre="Saundtrek", category_tab="Musiqa",
         duration=180, rec=0,
         desc="Big Buck Bunny ochiq filmi saundtreki (CC-BY).",
         file="music2.mp4",
         urls=["https://media.w3.org/2010/07/bunny/04-Death_Becomes_Fur.mp4",
               "https://cdn.jsdelivr.net/gh/rafaelreis-hotmart/Audio-Sample-files@master/sample.mp3"]),
    dict(key="mehrob", type="audiobook", title="Audiokitob — Namuna bob",
         author="Erkin namuna", genre="Audiokitob", category_tab="Badiiy",
         duration=120, rec=0, desc="Audiokitob ko'rinishidagi namunaviy yozuv.",
         file="mehrob.wav",
         urls=["https://cdn.jsdelivr.net/gh/katspaugh/wavesurfer.js@master/examples/audio/audio.wav",
               "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-5.mp3"]),
]

DEMO_BOOK = {
    "title": "Bahor tongida",
    "author": "Namuna muallif",
    "chapters": [
        {"title": "1-bob. Yo'lga otlanish",
         "text": "Tong saharda poyezd vokzalga sekin yaqinlashar edi. Yo'lovchilar "
                 "deraza ortidan o'tib borayotgan dalalarga tikilib, har biri o'z "
                 "o'yiga botgan edi.\n\nBu — erkin litsenziyali namunaviy kitob matni. "
                 "Admin paneli orqali haqiqiy asar bilan almashtirilishi mumkin."},
        {"title": "2-bob. Suhbat",
         "text": "Vagon ichida tanishlar topishdi. Suhbat asnosida yo'l qisqarib, "
                 "manzil yaqinlashayotganini hech kim sezmay qoldi."},
        {"title": "3-bob. Manzil",
         "text": "Quyosh tikka kelganda poyezd Samarqand vokzaliga yetib keldi. "
                 "Yangi shahar, yangi taassurotlar ularni kutmoqda edi."},
    ],
}

BOOKS = [
    dict(key="otkan", type="book", title="O'tkan kunlar", author="Abdulla Qodiriy",
         genre="Badiiy", category_tab="Badiiy", pages=560, rec=1,
         desc="O'zbek adabiyotining durdona asari.", text="otkan.json"),
    dict(key="bahor", type="book", title="Bahor tongida", author="Namuna muallif",
         genre="Badiiy", category_tab="Badiiy", pages=120, rec=0,
         desc="Erkin litsenziyali namunaviy kitob.", text="bahor.json"),
]


def main():
    os.makedirs(config.MEDIA_DIR, exist_ok=True)
    os.makedirs(config.COVERS_DIR, exist_ok=True)
    os.makedirs(config.BOOKS_DIR, exist_ok=True)

    rows = []

    def add_media(it, min_bytes, deadline):
        dest = os.path.join(config.MEDIA_DIR, it["file"])
        if not download(it["urls"], dest, min_bytes=min_bytes, max_seconds=deadline):
            return
        cov = it["key"] + ".jpg"
        cover = cov if download(cover_url(it["key"]),
                                os.path.join(config.COVERS_DIR, cov),
                                min_bytes=2_000, max_seconds=20) else None
        rows.append((it["type"], it["title"], it["author"], it["genre"], it["desc"],
                     it["duration"], None, cover, it["file"], None,
                     it["category_tab"], it["rec"]))

    print("== Video / multfilm ==", flush=True)
    for it in VIDEOS:
        # haqiqiy (katta) filmlarga ko'proq, lekin cheklangan vaqt beramiz
        add_media(it, min_bytes=300_000, deadline=120 if it.get("big") else 60)

    print("== Audio ==", flush=True)
    for it in AUDIO:
        add_media(it, min_bytes=80_000, deadline=120)

    print("== Kitoblar ==", flush=True)
    with open(os.path.join(config.BOOKS_DIR, "bahor.json"), "w", encoding="utf-8") as f:
        json.dump(DEMO_BOOK, f, ensure_ascii=False, indent=2)
    for it in BOOKS:
        if not os.path.isfile(os.path.join(config.BOOKS_DIR, it["text"])):
            print(f"  [skip] kitob matni yo'q: {it['text']}", flush=True)
            continue
        cov = it["key"] + ".jpg"
        cover = cov if download(cover_url(it["key"], 400, 600),
                                os.path.join(config.COVERS_DIR, cov),
                                min_bytes=2_000, max_seconds=20) else None
        rows.append((it["type"], it["title"], it["author"], it["genre"], it["desc"],
                     None, it["pages"], cover, None, it["text"],
                     it["category_tab"], it["rec"]))

    # --- DB ni qayta yozish (faqat haqiqatan mavjud fayllar) ---
    conn = db.connect()
    conn.executescript(db.SCHEMA)
    conn.execute("DELETE FROM content")
    conn.executemany(
        """INSERT INTO content
           (type,title,author,genre,description,duration,pages,
            cover_path,file_path,text_path,category_tab,is_recommended)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", rows)
    conn.commit()
    n = conn.execute("SELECT COUNT(*) AS n FROM content").fetchone()["n"]
    conn.close()

    by_type = {}
    for r in rows:
        by_type[r[0]] = by_type.get(r[0], 0) + 1
    print(f"\nTAYYOR: content jadvalida {n} ta yozuv.", flush=True)
    print("Turlari:", by_type, flush=True)


if __name__ == "__main__":
    sys.exit(main())
