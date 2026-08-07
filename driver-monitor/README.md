# Haydovchi uyqu/charchoq nazorati (`driver-monitor/`)

Web-kamera orqali haydovchi **uxlab qolган-qolmaganini** kuzatadigan mustaqil
Python ilova. Loyihaning boshqa qismlaridan **alohida** — hech narsaga bog'liq
emas, o'zi ishlaydi.

## Nima qiladi

- Kameradan (standart **0** — noutbuk/USB web-kamera) uzluksiz kadr o'qiydi.
- **OpenCV Haar cascade** bilan yuz va ko'zni aniqlaydi (qo'shimcha model yuklab
  olish SHART EMAS — `opencv-python` ichida keladi, oflayn ishlaydi).
- **Har 5 soniyada** holatni baholaydi: `UYG'OQ` / `UXLAB QOLGAN` / `YUZ KO'RINMAYDI`.
- Ko'z **uzluksiz ~2.5 s yumuq** bo'lsa — 5 soniyani kutmay **DARHOL** ogohlantiradi
  (mikrouyqu xavfli).
- Ogohlantirish: **ovozli signal** (Windows beep) + konsolда qizil xabar +
  (ixtiyoriy) ekranда video ustidа yozuv.

## O'rnatish va ishga tushirish

```bash
cd driver-monitor
pip install -r requirements.txt

python monitor.py                 # kamera 0, konsol rejimi
python monitor.py --show          # video oynasi bilan (oynada 'q' — chiqish)
python monitor.py --camera 1      # boshqa kamera
```

Ctrl+C bilan to'xtatiladi (yoki `--show` da oynada `q`).

## Sozlamalar (argumentlar)

| Argument | Standart | Vazifasi |
|---|---|---|
| `--camera N` | `0` | kamera indeksi |
| `--interval S` | `5` | necha soniyada bir baholash |
| `--closed-alarm S` | `2.5` | frontal yuzда ko'z uzluksiz shuncha s yumuq → darhol signal |
| `--min-frontal R` | `0.35` | 5s oynada frontal kadr ulushi shundan kam → "qaramayapti" (uyqu deб baholanmaydi) |
| `--show` | — | video oynasini ko'rsatish |
| `--max-seconds S` | `0` | shuncha s dan keyin o'zi to'xtaydi (sinov uchun) |

**Noto'g'ri signalни kamaytirish (muhim):** ilova ikki himoya bilan adashmaydi:
1. **Frontal-yuz darvozasi** — signal FAQAT yuz kameraga qaraб turганда. Yon/past/
   chetга qarasa "kameraga qaramayapti" bo'ladi (signalsiz), uxlab qolган EMAS.
2. **Davomiy yumilish** — tarqoq bitta-kadr xatolari emas, balki ko'z **uzluksiz**
   ~1.75–2.5 s yumuq bo'lgandagina uyqu deб hisoblanadi.

Ko'zoynak/kam yorug'lik ochiq-ko'z aniqlashni qiyinlashtiradi — bunда yorug'roq
joy yoki yaxshiroq kamera yordam beradi.

## Maxfiylik

Kadrlar **hech qayerga saqlanmaydi va yuborilmaydi** — faqat xotirada tahlil
qilinadi, hech qanday tarmoq aloqasi yo'q. Kamera faqat ilova ishlaganda yonadi.

## Qanday ishlaydi (texnik)

1. Har kadr: `haarcascade_frontalface_default`/`_alt2` bilan **frontal** (kameraga
   qaragan) yuz topiladi. **Topilmasa → `away`** (yon/past/chetга qaragan) —
   uyqu deб baholanmaydi, taymer nollanadi.
2. Frontal yuz bor bo'lsa, yuqori ~62% ida ikki cascade (`haarcascade_eye` +
   `_eye_tree_eyeglasses`) bilan ko'z qidiriladi — ochiq-ko'zni sezgirroq topish.
3. Ko'z topilса — **`open`**, topilmasa — **`closed`**.
4. Qaror **davomiy** yumilish bo'yicha: 5s oynadagi eng uzun **uzluksiz** yumuq
   ~1.75s dan oshsa, yoki ko'z uzluksiz 2.5s yumuq bo'lsa → uyqu. Tarqoq bitta-kadr
   Haar xatolari (ochiq-ko'z o'tkazib yuborilishi) signal bermaydi.

> **Yanada aniqroq variant:** ko'z ochiqlik nisbati (EAR) — yuz nuqtalari
> (landmark) bilan — ancha aniq. U MediaPipe/dlib talab qiladi; hozirgi
> Python 3.14'да MediaPipe `solutions` API yo'q, shuning uchun Haar ishlatilди
> (ishonchli, oflayn, 0 model). Python 3.11/3.12 da MediaPipe EAR ga o'tish mumkin.

## Qurilmага o'rnatish (haqiqiy foydalanish)

Haydovchi oldidagi mini-PC/kamerada avtostartга qo'ying (Windows: Task Scheduler
"logon"da `pythonw monitor.py`, yoki xizmat sifatida). Kelajakda uyqu hodisasini
KioskCloud'ga yuborish (masofadan ogohlantirish/log) qo'shilishi mumkin — hozircha
**mustaqil**.
