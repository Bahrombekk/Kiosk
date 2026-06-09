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
    from threads import track
    self._loader = track(_Loader(self.api))
    self._loader.start()
"""
from PyQt6.QtCore import QObject


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
