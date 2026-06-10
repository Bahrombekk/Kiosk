"""
security.py — Maxfiy texnik chiqish mexanizmi (main.py dan ajratilgan).

Navbar'dagi SOAT ustiga EXIT_TAPS marta tez-tez teginish PIN klaviaturani
ochadi (sensorli, klaviaturasiz ekranlar uchun ham). To'g'ri PIN — `on_exit`
callback chaqiriladi (MainWindow._exit_app). Ctrl+Shift+Q/C ham shu
`ask_exit_pin()` orqali ishlaydi.
"""
import hmac
import os
import time

from PyQt6.QtCore import QPoint, QRect
from PyQt6.QtWidgets import QApplication

from core import cache
from core import config
from core import logsetup
from core import pinhash
from core import theme as T


class ExitGuard:
    """Maxfiy teginishlarni sanab, chiqish PIN'ini tekshiradigan qo'riqchi.

    MainWindow uni `ExitGuard(self, self._exit_app)` deb yaratadi:
      - `win`     — soat (win.nav.clock), mavzu (win.theme_name) va ekran uchun
      - `on_exit` — to'g'ri PIN kiritilganda chaqiriladigan callback
    """

    def __init__(self, win, on_exit):
        self.win = win
        self.on_exit = on_exit
        self._exit_taps = []
        self.pin_open = False        # PIN oynasi ochiqmi (zastavka/til bloklari)
        self._pin_block_until = 0    # brute-force bloki tugaydigan vaqt

    def register_tap(self, gpos):
        """Navbar'dagi SOAT ustiga ketma-ket teginishlarni sanaydi.

        Soat ko'rinmasa (masalan, 'ulanmoqda' ekrani) — zaxira sifatida ekran
        yuqori-o'ng burchagi ishlaydi (server o'chiq bo'lsa ham chiqib bo'lsin)."""
        lbl = self.win.nav.clock   # soat barcha sahifalarda ko'rinadi
        if lbl.isVisible() and lbl.width() > 0:
            # Soat yorlig'ining global to'rtburchagi + barmoq uchun qo'shimcha joy
            pad = T.s(18)
            zone = QRect(lbl.mapToGlobal(QPoint(0, 0)), lbl.size())
            zone = zone.adjusted(-pad, -pad, pad, pad)
            in_zone = zone.contains(gpos)
        else:
            g = (self.win.screen() or QApplication.primaryScreen()).geometry()
            size = T.s(config.EXIT_CORNER_PX)
            in_zone = (gpos.x() >= g.right() - size and gpos.y() <= g.top() + size)
        if not in_zone:
            self._exit_taps.clear()   # boshqa joyga tegilsa hisob qaytadan
            return
        now = time.monotonic()
        # Bitta fizik bosish filtrga ikki marta kelishi mumkin (QWindow + widget)
        # — 50ms ichidagi takrorni bitta teginish deb hisoblaymiz.
        if self._exit_taps and now - self._exit_taps[-1] < 0.05:
            return
        self._exit_taps.append(now)
        self._exit_taps = [t for t in self._exit_taps
                           if now - t <= config.EXIT_TAP_WINDOW_S]
        if len(self._exit_taps) >= config.EXIT_TAPS:
            self._exit_taps.clear()
            self.ask_exit_pin()

    def _verify_pin(self, entered):
        """Kiritilgan PIN to'g'rimi? Ustuvorlik:
          1) KIOSK_EXIT_PIN muhit o'zgaruvchisi (faqat ishlab chiqish)
          2) serverda admin o'rnatgan xesh (settings keshi — oflaynda ham bor)
          3) default PIN (config.EXIT_PIN)"""
        env_pin = os.environ.get("KIOSK_EXIT_PIN")
        if env_pin:
            return hmac.compare_digest(entered.encode(), env_pin.encode())
        hit = cache.load_json("settings")
        stored = hit[0].get("exit_pin_hash") if hit else None
        if stored:
            return pinhash.verify_secret(entered, stored)
        return hmac.compare_digest(entered.encode(),
                                   config.EXIT_PIN.encode())

    def ask_exit_pin(self):
        if self.pin_open:
            return
        # Urinishlar tugagan bo'lsa — 60 soniya blok (brute-force qiyinlashadi)
        if time.monotonic() < self._pin_block_until:
            return
        self.pin_open = True
        try:
            from widgets.pinpad import PinDialog
            dlg = PinDialog(self.win, self._verify_pin,
                            theme=self.win.theme_name)
            ok = dlg.exec()
            if dlg.lockout:
                self._pin_block_until = time.monotonic() + 60
                logsetup.get_logger(__name__).warning(
                    "PIN 5 marta noto'g'ri kiritildi — 60s blok")
        finally:
            self.pin_open = False
        if ok:
            self.on_exit()
