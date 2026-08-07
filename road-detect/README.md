# Yo'l to'siqlari detektori — YOLOv4-tiny (`road-detect/`)

1 ta web-kamera + **OpenCV `dnn`** bilan, **CPU'da** ishlaydigan mustaqil ilova.
Oldда **odam, mashina, avtobus, yuk mashina, velosiped, mototsikl** ni aniqlaydi
(YOLOv4-tiny, COCO) va o'lchamидан **taxminiy masofani** hisoblab, chegaradan
(standart **1.5 m**) yaqin bo'lsa ovozli signal beradi. Har **3 soniyada** bir marta.

`front-obstacle/` (Haar/HOG) dan **kuchliroq** — turli sinflarni, turli
o'lchamlarda aniqlaydi.

## Model fayllari (yuklab olingan)

`models/` ичida: `yolov4-tiny.cfg`, `yolov4-tiny.weights` (~23 MB), `coco.names`.
Boshqa kompyuterда qayta yuklab olish (PowerShell):

```powershell
$b="https://raw.githubusercontent.com/AlexeyAB/darknet/master"
mkdir models -Force
iwr "$b/cfg/yolov4-tiny.cfg"  -OutFile models/yolov4-tiny.cfg
iwr "$b/data/coco.names"      -OutFile models/coco.names
iwr "https://github.com/AlexeyAB/darknet/releases/download/darknet_yolo_v4_pre/yolov4-tiny.weights" -OutFile models/yolov4-tiny.weights
```

## O'rnatish va ishga tushirish

```bash
cd road-detect
pip install -r requirements.txt

python detect.py                    # kamera 0, har 3s, 1.5 m
python detect.py --warn-dist 3 --show
python detect.py --conf 0.3         # sezgirroq (ko'proq aniqlaydi)
```

## Sozlamalar

| Argument | Standart | Vazifasi |
|---|---|---|
| `--camera N` | `0` | kamera indeksi |
| `--interval S` | `3` | necha soniyada bir tekshirish |
| `--warn-dist M` | `1.5` | shundan yaqin (m) → signal |
| `--focal PX` | (kalib/600) | kamera fokusi (piksel). Berilmasa: saqlangan kalib yoki 600 |
| `--calibrate M` | — | odam shu masofada (m) turib fokusni o'lchaydi va SAQLAYDI |
| `--conf R` | `0.4` | aniqlash ishonch chegarasi (past = sezgirroq) |
| `--show` | — | video oynasi (ramkалар + masofa) |
| `--model-dir` | `models` | model fayllar papkasi |

## Aniqlangan sinflar + masofa

| Sinf | O'zbekcha | Masofa o'lchovi |
|---|---|---|
| person | odam | bo'y ~1.7 m |
| car | mashina | eni ~1.8 m |
| bus | avtobus | eni ~2.9 m |
| truck | yuk mashina | eni ~2.5 m |
| bicycle | velosiped | ~1.1 m |
| motorbike | mototsikl | ~1.1 m |

Masofa: `d ≈ fokus × real_o'lcham / piksel_o'lcham` — **taxminiy** (1 kamera aniq
metr o'lchay olmaydi).

### Masofani aniqlash — KALIBRLASH (muhim)

Standart `fokus = 600` har kameraда har xil → masofa adashadi. Bir marta kalibrlang:
bir odam kameradан **aniq masofada** (masalan 3 m) **to'liq gavdasi ko'rinib** tursin:

```bash
python detect.py --calibrate 3      # odam 3 m da turibdi
# → "fokus <qiymat> (saqlandi: models/calib.txt)"
python detect.py                    # endi saqlangan fokus AVTO ishlatiladi
```

Kalibrlangach masofa ancha aniq bo'ladi.

**Odam masofasi ikki usulda** (avtomatik): yuz ko'rinса — **yuz enidан** (~15 sm,
YAQIN masofада ishonchli, chunki yaqinда gavda kadrга sig'maydi); yuz yo'q bo'lса
(uzoqроq/orqаga o'girilган) — **gavda balandligидан** (~1.7 m). Shu tufayli juda
yaqin odam endi ~2 m emas, to'g'ri ~0.5 m deб ko'rsatiladi.

Eslatma: **mashina/avtobus eni** ko'rish burchagiga bog'liq (old/yon) — shuning
uchun ular odamдан kamroq aniq.

## Halol cheklovlar

- ✅ **Yo'l oldi**: masofадаgi (bir necha metr) mashina/odam/avtobus — yaxshi ishlaydi.
- ⚠️ **Juda yaqin** (yuz kadrни to'ldirса) — YOLO "person"ni gavda ko'rinmagani uchun
  o'tkazib yuborishi mumkin. Bunда `front-obstacle/` (yuz asosli) to'ldiradi.
- ❌ **Aniq metr / bo'sh devor / yon tomon** — 1 kamera bilan bo'lmaydi:
  ultratovush sensor yoki 2 kamera (stereo, `StereoSGBM`) kerak.

## Ishlash / CPU

YOLOv4-tiny CPU'да yengil; tekshiruv 3 soniyada bir bo'lgani uchun protsessor
bo'sh turadi. GPU shart emas (`DNN_TARGET_CPU`).

## Maxfiylik
Kadrlar saqlanmaydi/yuborilmaydi. Tarmoq aloqasi yo'q (model bir marta yuklangan).

> Sinovda tasdiqlandi: real fotolarда odamlarni ishonchli aniqladi (person 0.56–0.81).
> Kamera "band" desa — ochiq kamera-ilova yoki eski `python` jarayonini yoping.
