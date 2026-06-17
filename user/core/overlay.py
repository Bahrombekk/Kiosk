"""
overlay.py — Pleyer/o'quvchi oynalarini KIOSK OYNASI ICHIDA ko'rsatadi.

Pleyer alohida OS oynasi (top-level) bo'lib ochilmaydi — kiosk oynasining
BOLASI (child) sifatida butun oynani qoplaydi (xuddi ilova ichidagi sahifa).
Shu sabab dev/oynali rejimda ham, to'liq ekran rejimida ham "alohida oyna"
ko'rinmaydi. Oyna o'lchami o'zgarsa — overlay ergashadi.

host=None bo'lsa — eski xatti-harakat (mustaqil to'liq ekran oyna).
"""
from PyQt6.QtCore import QObject, QEvent, Qt


class _FollowFilter(QObject):
    """Host oynasi o'lchami/holati o'zgarsa overlay'ni qayta to'ldiradi."""

    def __init__(self, overlay, host):
        super().__init__(host)
        self._ov = overlay
        self._host = host

    def eventFilter(self, obj, e):
        if obj is self._host and e.type() in (
                QEvent.Type.Resize, QEvent.Type.WindowStateChange):
            try:
                self._ov.setGeometry(self._host.rect())
            except RuntimeError:
                pass   # overlay allaqachon yopilgan
        return False


def show_over_host(overlay, host):
    """overlay'ni host oynasining ICHIDA (child) butun sohani qoplab ko'rsatadi.
    host=None bo'lsa — mustaqil to'liq ekran (eski xatti-harakat)."""
    if host is None:
        overlay.showFullScreen()
        return
    # Top-level window bayroqlarini olib tashlab, host bolasiga aylantiramiz
    overlay.setParent(host)
    overlay.setWindowFlags(Qt.WindowType.Widget)
    overlay.setGeometry(host.rect())
    overlay.raise_()
    overlay.show()
    overlay.setFocus()
    # Oyna o'lchami o'zgarsa ergashsin; overlay yopilganda filtrni olib tashlaymiz
    filt = _FollowFilter(overlay, host)
    host.installEventFilter(filt)
    overlay._host_filter = filt

    def _detach(*_a):
        # Overlay yo'q qilinganda filtrni olib tashlaymiz. Ilova yopilayotgan
        # bo'lsa host (MainWindow) ALLAQACHON o'chgan bo'lishi mumkin —
        # RuntimeError'ni yutamiz (aks holda excepthook fail-fast qiladi va
        # tarmoq oqimini yarim yo'lda uzib access violation keltiradi).
        try:
            host.removeEventFilter(filt)
        except RuntimeError:
            pass
    overlay.destroyed.connect(_detach)
