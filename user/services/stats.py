"""
stats.py — Kiosk foydalanish statistikasi (oflayn navbat + serverga batch).

Nima uchun kerak: operator (turizm bo'limi/temir yo'l) kioskdan QANCHA va
QANDAY foydalanilayotganini ko'rsin — kuniga nechta sessiya, qaysi bo'lim va
kontent mashhur, qaysi til tanlanadi, reklama necha marta o'ynadi
(proof-of-play). Ma'lumot admin oynasidagi «Statistika» sahifasida ko'rinadi.

Ishlash printsipi (oflayn-birinchi, mavjud kesh patterni bilan bir xil):
  - event() istalgan joydan chaqiriladi — yozuv DARHOL diskka (JSONL navbat)
    qo'shiladi, UI hech qachon kutmaydi;
  - StatsService davriy ravishda navbatni o'qib serverga POST /api/stats
    qiladi; tarmoq yo'q bo'lsa navbat saqlanib turadi (keyingi urinishda ketadi);
  - sessiya = zastavka yopilishidan keyingi faollik davri (session_start /
    session_end juftligi, davomiyligi bilan).
"""
import json
import logging
import os
import socket
import threading
import time
import uuid
from datetime import datetime

import requests
from PyQt6.QtCore import QObject, QThread, QTimer

from core import cache
from core import i18n
from core.threads import track

log = logging.getLogger(__name__)

QUEUE_FILE = os.path.join(cache.CACHE_DIR, "stats_queue.jsonl")
MAX_QUEUE_BYTES = 1_500_000   # oflayn to'planish chegarasi (eski yarmi tashlanadi)
FLUSH_MS = 60 * 1000          # serverga yuborish oralig'i
BATCH_MAX = 500               # bitta so'rovda nechta yozuv

DEVICE_ID = socket.gethostname()

_lock = threading.Lock()
_session = None               # joriy sessiya id (zastavka yopilganda boshlanadi)
_session_t0 = None


def event(name, **data):
    """Yengil hisob nuqtasi — istalgan joydan chaqiriladi, bloklamaydi.

    Diskka yozish xatosi statistika uchun ilovani hech qachon yiqitmasin —
    jim loglanadi (kiosk asosiy vazifasi statistikadan muhimroq)."""
    rec = {"ts": datetime.now().isoformat(timespec="seconds"),
           "session": _session, "event": name, "data": data}
    try:
        line = json.dumps(rec, ensure_ascii=False)
        with _lock:
            os.makedirs(cache.CACHE_DIR, exist_ok=True)
            _trim_if_huge()
            with open(QUEUE_FILE, "a", encoding="utf-8") as f:
                f.write(line + "\n")
    except (OSError, ValueError):
        log.debug("Statistika yozilmadi: %s", name, exc_info=True)


def _trim_if_huge():
    """Server uzoq vaqt yo'q bo'lsa navbat cheksiz o'smasin: chegaradan
    oshganda eng eski yarmini tashlaymiz (_lock ichida chaqiriladi)."""
    try:
        if (os.path.isfile(QUEUE_FILE)
                and os.path.getsize(QUEUE_FILE) > MAX_QUEUE_BYTES):
            with open(QUEUE_FILE, encoding="utf-8") as f:
                lines = f.readlines()
            keep = lines[len(lines) // 2:]
            tmp = QUEUE_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.writelines(keep)
            os.replace(tmp, QUEUE_FILE)
            log.warning("Statistika navbati qisqartirildi (%d -> %d yozuv)",
                        len(lines), len(keep))
    except OSError:
        pass


def session_start():
    """Yangi tashrif sessiyasi (zastavka yopilganda). Ochiq sessiya bo'lsa —
    hech narsa qilmaydi (idempotent)."""
    global _session, _session_t0
    if _session:
        return
    _session = uuid.uuid4().hex[:12]
    _session_t0 = time.monotonic()
    event("session_start", lang=i18n.get_lang())


def session_end():
    """Sessiyani yopadi (zastavka chiqqanda / ilova yopilganda)."""
    global _session, _session_t0
    if not _session:
        return
    dur = int(time.monotonic() - (_session_t0 or time.monotonic()))
    event("session_end", duration_s=dur)
    _session = None
    _session_t0 = None


class _Flusher(QThread):
    """Navbatdagi yozuvlarni serverga yuboradi (alohida oqim — UI kutmaydi)."""

    def __init__(self, api):
        super().__init__()
        self.api = api

    def run(self):
        try:
            with _lock:
                if not os.path.isfile(QUEUE_FILE):
                    return
                with open(QUEUE_FILE, encoding="utf-8") as f:
                    lines = f.readlines()
            batch = lines[:BATCH_MAX]
            events = []
            for ln in batch:
                try:
                    events.append(json.loads(ln))
                except ValueError:
                    pass   # buzilgan qator (yarim yozilgan) — tashlab ketamiz
            if not events:
                # fayl faqat buzilgan qatorlardan iborat — tozalaymiz
                self._drop(len(batch))
                return
            from core import netpin
            r = netpin.post(
                f"{self.api.base_url}/api/stats",
                json={"device_id": DEVICE_ID, "events": events},
                headers=self.api._headers, timeout=self.api.timeout)
            r.raise_for_status()
            self._drop(len(batch))
            log.debug("Statistika yuborildi: %d yozuv", len(events))
        except requests.RequestException:
            pass   # oflayn — navbat joyida qoladi, keyingi siklda yana urinamiz
        except Exception:
            log.warning("Statistika yuborishda xato", exc_info=True)

    @staticmethod
    def _drop(n):
        """Yuborilgan birinchi n qatorni navbatdan olib tashlaydi (atomik).

        Yuborish paytida kelgan yangi yozuvlar fayl oxirida — ular saqlanadi."""
        with _lock:
            try:
                with open(QUEUE_FILE, encoding="utf-8") as f:
                    lines = f.readlines()
                rest = lines[n:]
                tmp = QUEUE_FILE + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    f.writelines(rest)
                os.replace(tmp, QUEUE_FILE)
            except OSError:
                pass


class StatsService(QObject):
    """Davriy yuboruvchi (AdManager uslubida: QTimer + ishchi QThread)."""

    def __init__(self, parent, api):
        super().__init__(parent)
        self.api = api
        self._flusher = None
        self._timer = QTimer(self)
        self._timer.setInterval(FLUSH_MS)
        self._timer.timeout.connect(self.flush)

    def start(self):
        self._timer.start()
        # Birinchi yuborish kechiktirilmaydi — oldingi seansdan qolgan navbat
        # (masalan, kecha oflayn yig'ilgani) darhol ketsin.
        QTimer.singleShot(10_000, self.flush)

    def stop(self):
        self._timer.stop()

    def flush(self):
        if self._flusher is not None and self._flusher.isRunning():
            return   # oldingi yuborish hali tugamagan
        self._flusher = track(_Flusher(self.api))
        self._flusher.start()
