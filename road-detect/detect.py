#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Yo'l to'siqlari detektori — YOLOv4-tiny (OpenCV dnn), CPU'da.

1 ta web-kamera orqali oldда ODAM, MASHINA, AVTOBUS, YUK MASHINA, VELOSIPED,
MOTOTSIKL ni aniqlaydi (COCO 80 sinf ичidan yo'lga tegishlilari) va o'lchamидан
TAXMINIY masofani hisoblaydi. Har 3 soniyada bir marta tekshiradi. Belgilangan
chegaradan (standart 1.5 m) yaqin bo'lsa — ovozli signal.

CHEKLOV (halol): 1 kamera masofани ANIQ o'lchay olmaydi — masofa "pinhole" modeli
bilan TAXMINIY (real o'lcham ma'lum sinflarга). Aniq metr / devor / yon tomon uchun
ultratovush sensor yoki 2 kamera (stereo) kerak.

Model fayllari `models/` da (yolov4-tiny.cfg, .weights, coco.names) — yuklab olingan.

Ishlatish:
  pip install -r requirements.txt
  python detect.py                     # kamera 0, har 3s, 1.5 m
  python detect.py --warn-dist 3 --show
"""
import argparse
import os
import sys
import time

import cv2

try:
    import winsound

    def beep():
        try:
            winsound.Beep(1300, 500)
        except RuntimeError:
            sys.stdout.write("\a"); sys.stdout.flush()
except ImportError:
    def beep():
        sys.stdout.write("\a"); sys.stdout.flush()


class C:
    R = "\033[91m"; G = "\033[92m"; Y = "\033[93m"; DIM = "\033[90m"; X = "\033[0m"

# Yo'lга tegishli sinflar + REAL o'lchami (masofa uchun): (o'lchov, metr)
#   'h' = balandlik bo'yicha, 'w' = kenglik bo'yicha
ROAD = {
    "person": ("h", 1.70), "bicycle": ("h", 1.10), "car": ("w", 1.80),
    "motorbike": ("h", 1.10), "motorcycle": ("h", 1.10), "bus": ("w", 2.90),
    "truck": ("w", 2.50),
}
UZ = {"person": "odam", "bicycle": "velosiped", "car": "mashina",
      "motorbike": "mototsikl", "motorcycle": "mototsikl", "bus": "avtobus",
      "truck": "yuk mashina"}


def open_camera(index):
    backends = ([(cv2.CAP_DSHOW, "d"), (cv2.CAP_MSMF, "m"), (0, "x")]
                if sys.platform == "win32" else [(0, "x")])
    for be, _ in backends:
        cap = cv2.VideoCapture(index, be)
        if cap.isOpened():
            ok, _f = cap.read()
            if ok:
                try:
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                except cv2.error:
                    pass
                return cap
        cap.release()
    return None


def grab_fresh(cap, flush=4):
    frame = None
    for _ in range(flush):
        ok, f = cap.read()
        if ok:
            frame = f
    return frame


class Yolo:
    def __init__(self, mdir):
        cfg = os.path.join(mdir, "yolov4-tiny.cfg")
        weights = os.path.join(mdir, "yolov4-tiny.weights")
        names = os.path.join(mdir, "coco.names")
        for p in (cfg, weights, names):
            if not os.path.isfile(p):
                raise FileNotFoundError(p)
        with open(names, encoding="utf-8") as f:
            self.names = [x.strip() for x in f if x.strip()]
        self.net = cv2.dnn.readNetFromDarknet(cfg, weights)
        self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)   # CPU
        self.out_layers = self.net.getUnconnectedOutLayersNames()
        # Yuz (Haar) — YAQIN masofада odam masofasini aniqroq o'lchash uchun
        # (yaqinда gavda kadrга sig'maydi, yuz esa doim ~15 sm — ishonchli).
        self.face = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

    FACE_W = 0.15   # odam yuzi eni (m)

    def person_distance(self, gray, box, focal):
        """Odam masofasi: yuz ko'rinса — yuz enidан (yaqinда ishonchli),
        aks holda gavda balandligидан. (masofa_m, usul) qaytaradi."""
        x, y, w, h = box
        y0, x0 = max(0, y), max(0, x)
        roi = gray[y0:y0 + int(h * 0.55), x0:x0 + w]
        if roi.size:
            faces = self.face.detectMultiScale(roi, 1.15, 5, minSize=(38, 38))
            if len(faces):
                fw = max(faces, key=lambda f: f[2])[2]
                if fw > 0:
                    return focal * self.FACE_W / fw, "yuz"
        return (focal * ROAD["person"][1] / h, "gavda") if h > 0 else (None, None)

    def detect(self, frame, conf_thr=0.4, nms_thr=0.4):
        h, w = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(frame, 1 / 255.0, (416, 416),
                                     swapRB=True, crop=False)
        self.net.setInput(blob)
        outs = self.net.forward(self.out_layers)
        boxes, confs, ids = [], [], []
        for out in outs:
            for det in out:
                scores = det[5:]
                cid = int(scores.argmax())
                conf = float(scores[cid])
                if conf < conf_thr:
                    continue
                cx, cy, bw, bh = det[0] * w, det[1] * h, det[2] * w, det[3] * h
                x, y = int(cx - bw / 2), int(cy - bh / 2)
                boxes.append([x, y, int(bw), int(bh)])
                confs.append(conf)
                ids.append(cid)
        keep = cv2.dnn.NMSBoxes(boxes, confs, conf_thr, nms_thr)
        res = []
        for i in (keep.flatten() if len(keep) else []):
            name = self.names[ids[i]] if ids[i] < len(self.names) else "?"
            res.append((name, confs[i], boxes[i]))
        return res


def calib_path(mdir):
    return os.path.join(mdir, "calib.txt")


def load_focal(mdir):
    """Saqlangan (kalibrlangan) fokus, bo'lmasa None."""
    try:
        with open(calib_path(mdir), encoding="utf-8") as f:
            return float(f.read().strip())
    except (OSError, ValueError):
        return None


def save_focal(mdir, focal):
    with open(calib_path(mdir), "w", encoding="utf-8") as f:
        f.write(f"{focal:.1f}")


def distance_of(name, box, focal):
    """Sinf REAL o'lchamидан taxminiy masofa (m). Noma'lum sinf → None."""
    if name not in ROAD:
        return None
    dim, real = ROAD[name]
    x, y, w, h = box
    px = w if dim == "w" else h
    return (focal * real / px) if px > 0 else None


def main():
    ap = argparse.ArgumentParser(description="Yo'l to'siqlari detektori (YOLOv4-tiny, CPU)")
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--interval", type=float, default=3.0)
    ap.add_argument("--warn-dist", type=float, default=1.5, help="shundan yaqin (m) → signal")
    ap.add_argument("--focal", type=float, default=None,
                    help="kamera fokusi (piksel). Berilmasa: saqlangan kalib yoki 600")
    ap.add_argument("--calibrate", type=float, default=0.0,
                    help="ODAM shu masofada (m) TO'LIQ ko'rinib turib fokusni o'lchaydi va saqlaydi")
    ap.add_argument("--conf", type=float, default=0.4, help="aniqlash ishonch chegarasi")
    ap.add_argument("--model-dir", default=os.path.join(os.path.dirname(__file__), "models"))
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--max-seconds", type=float, default=0)
    args = ap.parse_args()

    try:
        yolo = Yolo(args.model_dir)
    except FileNotFoundError as e:
        print(f"{C.R}Model fayli topilmadi: {e}\n  models/ ичida yolov4-tiny.cfg, "
              f".weights, coco.names bo'lishi kerak (README ga qarang).{C.X}")
        return 2

    cap = open_camera(args.camera)
    if cap is None:
        print(f"{C.R}Kamera {args.camera} ochilmadi (band yoki noto'g'ri indeks).{C.X}")
        return 1

    # ── Kalibrlash rejimi: odam ma'lum masofada → fokusni o'lchab saqlaydi ──────
    if args.calibrate:
        print(f"{C.Y}KALIBRLASH: bir odam kameradан ANIQ {args.calibrate:.1f} m da, "
              f"TO'LIQ gavdasi ko'rinib tursin…{C.X}")
        time.sleep(2)
        frame = grab_fresh(cap)
        persons = [b for (n, c, b) in yolo.detect(frame, args.conf)
                   if n == "person"] if frame is not None else []
        if persons:
            hpx = max(persons, key=lambda b: b[3])[3]           # eng baland gavda
            focal = hpx * args.calibrate / ROAD["person"][1]    # f = px·d / real
            save_focal(args.model_dir, focal)
            print(f"{C.G}Gavda {hpx}px @ {args.calibrate:.1f} m → fokus {focal:.0f} "
                  f"(saqlandi: models/calib.txt). Endi oddiy ishga tushiring.{C.X}")
        else:
            print(f"{C.R}Odam topilmadi — to'liq gavda ko'rinsin, yorug'roq joyда qayta urining.{C.X}")
        cap.release()
        return 0

    # Fokus: --focal (berilса) > saqlangan kalib > standart 600
    focal = args.focal or load_focal(args.model_dir) or 600.0
    src = ("--focal" if args.focal else
           ("kalibrlangan" if load_focal(args.model_dir) else "standart"))
    print(f"{C.G}Yo'l detektori yoqildi{C.X} (YOLOv4-tiny, CPU) — kamera {args.camera}, "
          f"har {args.interval:.0f}s, chegara {args.warn_dist:.1f} m, fokus {focal:.0f} "
          f"({src}). Ctrl+C — chiqish.")
    start = time.monotonic()
    try:
        while True:
            frame = grab_fresh(cap)
            if frame is None:
                time.sleep(0.2); continue
            dets = yolo.detect(frame, args.conf)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            road = []
            for name, conf, box in dets:
                if name == "person":
                    d, _how = yolo.person_distance(gray, box, focal)
                else:
                    d = distance_of(name, box, focal)
                if d is not None:
                    road.append((d, name, conf, box))

            if road:
                road.sort(key=lambda r: r[0])
                near_d, near_n, _c, _b = road[0]
                summary = ", ".join(f"{UZ.get(n, n)} ~{d:.1f}m" for d, n, _cc, _bb in road[:4])
                if near_d <= args.warn_dist:
                    print(f"{C.R}⚠  OLDDA {UZ.get(near_n, near_n).upper()} YAQIN — "
                          f"~{near_d:.1f} m! [{summary}]{C.X}")
                    beep()
                else:
                    print(f"{C.G}✓  toza{C.X} {C.DIM}[{summary}]{C.X}")
            else:
                print(f"{C.DIM}·  yo'l to'sig'i yo'q{C.X}")

            if args.show and frame is not None:
                for d, name, conf, (x, y, w, h) in road:
                    col = (0, 0, 255) if d <= args.warn_dist else (0, 200, 0)
                    cv2.rectangle(frame, (x, y), (x + w, y + h), col, 2)
                    cv2.putText(frame, f"{UZ.get(name, name)} ~{d:.1f}m", (x, max(20, y - 8)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, col, 2)
                cv2.imshow("Yo'l detektori (q - chiqish)", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            if args.max_seconds and time.monotonic() - start >= args.max_seconds:
                print(f"{C.DIM}(--max-seconds tugadi){C.X}")
                break
            slept = 0.0
            while slept < args.interval:
                if args.show:
                    if cv2.waitKey(30) & 0xFF == ord("q"):
                        raise KeyboardInterrupt
                    slept += 0.03
                else:
                    time.sleep(0.1); slept += 0.1
    except KeyboardInterrupt:
        print(f"\n{C.DIM}To'xtatildi.{C.X}")
    finally:
        cap.release()
        if args.show:
            cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
