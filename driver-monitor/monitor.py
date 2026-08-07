#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Haydovchi uyqu/charchoq nazorati — web-kamera orqali.

MUHIM tamoyil (noto'g'ri signalni oldini olish):
  Ogohlantirish FAQAT yuz KAMERAGA QARAB turганда va ko'z uzoq yumuq bo'lса
  beriladi. Haydovchi boshqa yoqqa/yonga qaraса (frontal yuz yo'qoladi) — bu
  "kameraga qaramayapti" holati, u UXLAB QOLGAN bilan ARALASHTIRILMAYDI va
  signal BERILMAYDI (avvalgi versiya shu yerда adashardi).

Holatlar:
  • open   — frontal yuz + ko'z ochiq (kamida bitta ko'z aniqlangan)
  • closed — frontal yuz + ko'z topilmadi (yumuq) → uxlab qolish nomzodi
  • away   — frontal yuz YO'Q (yon/past/chetga qaragan) → SIGNAL EMAS

Chiqishlar:
  • Ko'z UZLUKSIZ ~2.5 s yumuq (yuz frontal turganда) → DARHOL ovozli signal.
  • Har 5 s: UYG'OQ / UXLAB QOLGAN / KAMERAGA QARAMAYAPTI holati.
    (KAMERAGA QARAMAYAPTI — yumshoq eslatma, signalsiz.)

MAXFIYLIK: kadrlar saqlanmaydi/yuborilmaydi — faqat xotirada tahlil, tarmoq yo'q.

Ishlatish:
  pip install -r requirements.txt
  python monitor.py                 # kamera 0
  python monitor.py --show          # video oynasi bilan (q — chiqish)
"""
import argparse
import collections
import sys
import time

import cv2

try:
    import winsound

    def beep():
        try:
            winsound.Beep(1100, 500)
        except RuntimeError:
            sys.stdout.write("\a"); sys.stdout.flush()
except ImportError:
    def beep():
        sys.stdout.write("\a"); sys.stdout.flush()


class C:
    R = "\033[91m"; G = "\033[92m"; Y = "\033[93m"; DIM = "\033[90m"; X = "\033[0m"


class Classifier:
    """Kadrni open/closed/away ga ajratadi. Frontal yuz darvozasi bilan —
    yon qaragan (frontal yuz yo'q) 'away' bo'ladi, 'closed' EMAS."""

    def __init__(self):
        d = cv2.data.haarcascades
        self.face = cv2.CascadeClassifier(d + "haarcascade_frontalface_default.xml")
        self.face_alt = cv2.CascadeClassifier(d + "haarcascade_frontalface_alt2.xml")
        # Ikki ko'z-cascade — OCHIQ ko'zni sezgirroq topish (xato 'closed' kamayadi)
        self.eye = cv2.CascadeClassifier(d + "haarcascade_eye.xml")
        self.eye_g = cv2.CascadeClassifier(d + "haarcascade_eye_tree_eyeglasses.xml")

    def ok(self):
        return not (self.face.empty() or self.eye.empty())

    def _frontal_face(self, gray):
        """Eng katta FRONTAL yuz (kameraga qarab turган). Topilmasa None."""
        faces = self.face.detectMultiScale(gray, 1.2, 6, minSize=(110, 110))
        if len(faces) == 0 and not self.face_alt.empty():
            faces = self.face_alt.detectMultiScale(gray, 1.2, 6, minSize=(110, 110))
        if len(faces) == 0:
            return None
        return max(faces, key=lambda f: f[2] * f[3])

    def _find_eyes(self, roi, w, h):
        ms = (max(18, int(w * 0.10)), max(12, int(h * 0.08)))
        eyes = self.eye.detectMultiScale(roi, 1.1, 4, minSize=ms)
        if len(eyes) == 0 and not self.eye_g.empty():
            eyes = self.eye_g.detectMultiScale(roi, 1.1, 4, minSize=ms)
        return eyes

    def classify(self, gray):
        face = self._frontal_face(gray)
        if face is None:
            return "away", None, []            # kameraga qaramayapti
        x, y, w, h = face
        roi = gray[y:y + int(h * 0.62), x:x + w]
        eyes = self._find_eyes(roi, w, h)
        state = "open" if len(eyes) >= 1 else "closed"
        boxes = [(x + ex, y + ey, ew, eh) for (ex, ey, ew, eh) in eyes]
        return state, (x, y, w, h), boxes


def open_camera(index):
    """Kamerani bir necha backend bilan ochishga urinadi (Windows DSHOW ba'zan
    band/noturg'un). Ochilib, haqiqiy kadr bersa qaytaradi, aks holda None."""
    if sys.platform == "win32":
        backends = [(cv2.CAP_DSHOW, "DSHOW"), (cv2.CAP_MSMF, "MSMF"), (0, "default")]
    else:
        backends = [(0, "default")]
    for be, name in backends:
        cap = cv2.VideoCapture(index, be)
        if cap.isOpened():
            ok, _ = cap.read()
            if ok:
                return cap
        cap.release()
    return None


def main():
    ap = argparse.ArgumentParser(description="Haydovchi uyqu nazorati")
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--interval", type=float, default=5.0, help="baholash oralig'i (s)")
    ap.add_argument("--closed-alarm", type=float, default=2.5,
                    help="frontal yuzда ko'z uzluksiz shuncha s yumuq → DARHOL signal")
    ap.add_argument("--min-frontal", type=float, default=0.35,
                    help="oynada frontal kadr ulushi shundan kam bo'lsa — 'qaramayapti' (uyqu deб baholanmaydi)")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--max-seconds", type=float, default=0)
    args = ap.parse_args()

    clf = Classifier()
    if not clf.ok():
        print(f"{C.R}Haar cascade yuklanmadi (opencv-python to'liqmi?){C.X}")
        return 2

    cap = open_camera(args.camera)
    if cap is None:
        print(f"{C.R}Kamera {args.camera} ochilmadi. Boshqa dastur (Zoom/kamera ilovasi) "
              f"band qilmaganini yoki --camera boshqa indeksni tekshiring.{C.X}")
        return 1

    print(f"{C.G}Nazorat boshlandi{C.X} — kamera {args.camera}. Signal FAQAT kameraga "
          f"qarab turib ko'z yumuq bo'lganда. To'xtatish: Ctrl+C.")

    win = collections.deque()          # (ts, state)
    closed_since = None
    alarm_latched = False
    last_report = time.monotonic()
    start = time.monotonic()
    frames = 0

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.05); continue
            frames += 1
            now = time.monotonic()
            gray = cv2.equalizeHist(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
            state, face, eyes = clf.classify(gray)

            win.append((now, state))
            horizon = max(args.interval, args.closed_alarm) + 1
            while win and now - win[0][0] > horizon:
                win.popleft()

            # ── DARHOL signal: FAQAT frontal yuz + ko'z uzluksiz yumuq ──────────
            # 'away' (kameraga qaramayapti) yoki 'open' — taymerni NOLLAYDI,
            # shuning uchun boshqa yoqqa qarash signal BERMAYDI.
            if state == "closed":
                if closed_since is None:
                    closed_since = now
                elif now - closed_since >= args.closed_alarm and not alarm_latched:
                    print(f"{C.R}⚠  UXLAB QOLDI! Ko'z {now - closed_since:.1f}s uzluksiz "
                          f"yumuq (kameraga qarab) — OGOHLANTIRISH!{C.X}")
                    beep()
                    alarm_latched = True
            else:
                closed_since = None
                alarm_latched = False

            # ── Har `interval` s: baholash ──────────────────────────────────────
            if now - last_report >= args.interval:
                seg = [(t, s) for (t, s) in win if now - t <= args.interval]
                total = len(seg) or 1
                frontal = [s for (t, s) in seg if s in ("open", "closed")]
                frontal_ratio = len(frontal) / total
                # ENG UZUN UZLUKSIZ yumilish (tarqoq Haar-shovqini emas, davomiy
                # yumilishni o'lchaydi — noto'g'ri signalni keskin kamaytiradi).
                max_run, run0 = 0.0, None
                for t, s in seg:
                    if s == "closed":
                        run0 = t if run0 is None else run0
                        max_run = max(max_run, t - run0)
                    else:
                        run0 = None
                sleep_thr = args.closed_alarm * 0.7   # ~1.75s davomiy yumilish

                if frontal_ratio < args.min_frontal:
                    # Ko'p vaqt frontal yuz yo'q → kameraga qaramayapti (SIGNAL EMAS)
                    print(f"{C.Y}•  KAMERAGA QARAMAYAPTI{C.X} {C.DIM}(frontal "
                          f"{len(frontal)}/{total} kadr) — uyqu deb baholanmadi{C.X}")
                elif max_run >= sleep_thr:
                    print(f"{C.R}✗  UXLAB QOLGAN / CHARCHAGAN — ko'z {max_run:.1f}s "
                          f"davomiy yumuq (kameraga qarab).{C.X}")
                    beep()
                else:
                    print(f"{C.G}✓  UYG'OQ{C.X} {C.DIM}(frontal {len(frontal)}/{total}, "
                          f"uzluksiz-yumuq {max_run:.1f}s){C.X}")
                last_report = now
                frames = 0

            # ── Ixtiyoriy video oynasi ──────────────────────────────────────────
            if args.show:
                if face:
                    x, y, w, h = face
                    col = (0, 0, 255) if state == "closed" else (0, 200, 0)
                    cv2.rectangle(frame, (x, y), (x + w, y + h), col, 2)
                    for (ex, ey, ew, eh) in eyes:
                        cv2.rectangle(frame, (ex, ey), (ex + ew, ey + eh), (0, 200, 0), 1)
                label = {"open": "KO'Z OCHIQ", "closed": "KO'Z YUMUQ",
                         "away": "KAMERAGA QARAMAYAPTI"}[state]
                col = (0, 200, 0) if state == "open" else (
                    (0, 0, 255) if state == "closed" else (0, 190, 255))
                cv2.putText(frame, label, (12, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.9, col, 2)
                cv2.imshow("Haydovchi nazorati (q - chiqish)", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            if args.max_seconds and now - start >= args.max_seconds:
                print(f"{C.DIM}(--max-seconds tugadi){C.X}")
                break
    except KeyboardInterrupt:
        print(f"\n{C.DIM}To'xtatildi.{C.X}")
    finally:
        cap.release()
        if args.show:
            cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
