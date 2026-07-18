"""
threads.py — Worker (QThread) oqimlarini xavfsiz boshqarish.

Muammo: kod ko'p joyda `self._x = SomeThread(...); self._x.start()` qiladi. Yangi
thread eskisini almashtirganda, eski thread'ning yagona Python havolasi yo'qoladi.
Agar u hali ISHLAB TURGAN bo'lsa, Python axlat yig'uvchisi (GC) QThread C++
obyektini o'chiradi va Qt jarayonni `abort()` qiladi:

    QThread: Destroyed while thread '' is still running

Bu Python traceback'siz "jim crash" beradi — ilova o'zidan o'zi yopiladi.

Yechim: `track()` har bir thread'ni TUGAGUNICHA global to'plamda tirik saqlaydi.
Shunday qilib GC ishlab turgan QThread'ni hech qachon o'chira olmaydi. Thread
tugagach (`finished` signali asosiy oqimga queued yetkaziladi), havola olib
tashlanadi va obyekt odatdagidek yig'iladi.

Foydalanish:
    from core.threads import track
    self._loader = track(_Loader(self.api))
    self._loader.start()
"""
import logging
import os
import threading
import time

from PyQt6.QtCore import QObject, QThread

log = logging.getLogger(__name__)


class _Registry(QObject):
    def __init__(self):
        super().__init__()
        self._alive = set()
        self._lock = threading.Lock()

    def track(self, thread):
        with self._lock:
            self._alive.add(thread)
        # Asosiy oqimdagi QObject'ga ulanish -> queued yetkazish. Slot ishlaganda
        # thread haqiqatan tugagan bo'ladi, shu sababli havolani olib tashlash xavfsiz.
        thread.finished.connect(self._retire)
        return thread

    def _retire(self):
        with self._lock:
            self._alive.discard(self.sender())


_registry = None
_registry_lock = threading.Lock()


def track(thread):
    """QThread'ni u tugagunicha tirik saqlaydi (GC abort'ining oldini oladi)."""
    global _registry
    with _registry_lock:
        if _registry is None:
            _registry = _Registry()
    return _registry.track(thread)


# Qotib qolgan worker uchun ikkinchi (uzun) kutish — HTTP so'rov timeoutlari
# (8–20s) tugashiga imkon beradi.
_STUCK_GRACE_S = 10


def wait_all(timeout_ms=2000):
    """Ilova yopilishidan oldin kuzatilayotgan barcha thread'lar tugashini kutadi.
    `gc.get_objects()` bo'ylab yurish o'rniga aniq registr to'plamini ishlatadi —
    faqat O'ZIMIZNING worker'larga tegadi.

    MUHIM: terminate() ISHLATILMAYDI — requests/OpenSSL ichida ishlayotgan
    thread'ni majburiy o'ldirish shutdown'da access-violation (native crash)
    berardi. O'rniga: interruption so'raymiz -> timeout kutamiz -> qotganlar
    uchun HTTP timeoutlar o'tguncha uzun kutamiz -> shunda ham tugamasa
    jarayonni os._exit(0) bilan yakunlaymiz (Python/Qt teardown o'tkazib
    yuboriladi — GC 'QThread destroyed' abort'i ham bo'lmaydi; kod 0 —
    watchdog qayta ochmaydi)."""
    if _registry is None:
        return
    cur = QThread.currentThread()
    with _registry._lock:
        pending = list(_registry._alive)
    stuck = []
    for th in pending:
        try:
            if th is cur or not th.isRunning():
                continue
            th.requestInterruption()   # hamkorlikdagi to'xtash signali
        except RuntimeError:
            pass   # C++ obyekti allaqachon o'chirilgan — e'tiborsiz
    for th in pending:
        try:
            if th is cur or not th.isRunning():
                continue
            if not th.wait(timeout_ms):
                stuck.append(th)
        except RuntimeError:
            pass
    if not stuck:
        return
    deadline = time.monotonic() + _STUCK_GRACE_S
    for th in stuck:
        try:
            remain_ms = max(0, int((deadline - time.monotonic()) * 1000))
            if th.wait(remain_ms):
                continue
            log.error("Worker thread %r tugamadi — jarayon toza os._exit(0) "
                      "bilan yakunlanadi (terminate o'rniga)", th)
            logging.shutdown()
            os._exit(0)
        except RuntimeError:
            pass
