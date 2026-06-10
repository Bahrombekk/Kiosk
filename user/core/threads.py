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
from PyQt6.QtCore import QObject, QThread


class _Registry(QObject):
    def __init__(self):
        super().__init__()
        self._alive = set()

    def track(self, thread):
        self._alive.add(thread)
        # Asosiy oqimdagi QObject'ga ulanish -> queued yetkazish. Slot ishlaganda
        # thread haqiqatan tugagan bo'ladi, shu sababli havolani olib tashlash xavfsiz.
        thread.finished.connect(self._retire)
        return thread

    def _retire(self):
        self._alive.discard(self.sender())


_registry = None


def track(thread):
    """QThread'ni u tugagunicha tirik saqlaydi (GC abort'ining oldini oladi)."""
    global _registry
    if _registry is None:
        _registry = _Registry()
    return _registry.track(thread)


def wait_all(timeout_ms=2000):
    """Ilova yopilishidan oldin kuzatilayotgan barcha thread'lar tugashini kutadi.
    `gc.get_objects()` bo'ylab yurish o'rniga aniq registr to'plamini ishlatadi —
    faqat O'ZIMIZNING worker'larga tegadi. Belgilangan vaqtda tugamasa (kamdan-kam,
    chunki HTTP so'rovlarda timeout bor) oxirgi chora sifatida terminate qiladi."""
    if _registry is None:
        return
    cur = QThread.currentThread()
    for th in list(_registry._alive):
        try:
            if th is cur or not th.isRunning():
                continue
            if not th.wait(timeout_ms):
                th.terminate()
                th.wait(500)
        except RuntimeError:
            pass   # C++ obyekti allaqachon o'chirilgan — e'tiborsiz
