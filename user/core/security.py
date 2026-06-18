"""
security.py — Maxfiy texnik chiqish mexanizmi (main.py dan ajratilgan).

Navbar'dagi SOAT ustiga EXIT_TAPS marta tez-tez teginish PIN klaviaturani
ochadi (sensorli, klaviaturasiz ekranlar uchun ham). To'g'ri PIN — `on_exit`
callback chaqiriladi (MainWindow._exit_app). Ctrl+Shift+Q/C ham shu
`ask_exit_pin()` orqali ishlaydi.
"""
import hmac
import os
import sys
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

    # Brute-force bloki: har lockout'dan keyin eksponensial o'sadi (60s, 2m, 4m,
    # ... 1 soatgacha). Diskka saqlanadi — ilovani qayta ishga tushirib reset
    # qilib bo'lmaydi.
    _LOCK_FILE = "exit_lockout"
    _LOCK_BASE_S = 60
    _LOCK_CAP_S = 3600

    def __init__(self, win, on_exit):
        self.win = win
        self.on_exit = on_exit
        self._exit_taps = []
        self.pin_open = False        # PIN oynasi ochiqmi (zastavka/til bloklari)

    def _lock_state(self):
        hit = cache.load_json(self._LOCK_FILE)
        data = hit[0] if hit and isinstance(hit[0], dict) else {}
        return int(data.get("fails", 0)), float(data.get("block_until", 0))

    def _blocked(self):
        _fails, until = self._lock_state()
        return time.time() < until

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
        # Na env, na serverdan kelgan xesh bor — qattiq kodlangan default PIN.
        # Bu XAVFSIZ EMAS (umumiy/ma'lum kod). Frozen (production) build'da uni
        # UMUMAN qabul qilmaymiz: chiqish faqat KIOSK_EXIT_PIN yoki serverdan
        # kelgan xesh bilan ochiladi (fail-closed). Faqat ishlab chiqishda (dev)
        # qulaylik uchun default ishlaydi.
        if getattr(sys, "frozen", False):
            logsetup.get_logger(__name__).warning(
                "Chiqish PINi sozlanmagan va default rad etildi (production build). "
                "Admin paneldan PIN o'rnating yoki KIOSK_EXIT_PIN bering.")
            return False
        if not getattr(self, "_default_pin_warned", False):
            logsetup.get_logger(__name__).warning(
                "Chiqish PINi sozlanmagan — qattiq kodlangan default ishlatilmoqda "
                "(faqat dev). Production'da admin PIN yoki KIOSK_EXIT_PIN kerak.")
            self._default_pin_warned = True
        return hmac.compare_digest(entered.encode(),
                                   config.EXIT_PIN.encode())

    def ask_exit_pin(self):
        if self.pin_open:
            return
        # Diskka saqlangan blok hali tugamagan bo'lsa — ochmaymiz (qayta ishga
        # tushirish blokni o'chirmaydi, har lockout bilan blok uzayadi).
        if self._blocked():
            return
        self.pin_open = True
        try:
            from widgets.pinpad import PinDialog
            dlg = PinDialog(self.win, self._verify_pin,
                            theme=self.win.theme_name)
            ok = dlg.exec()
            dlg.deleteLater()   # GC'ni kutmasdan darhol tozalashga qo'yamiz
            if dlg.lockout:
                fails, _until = self._lock_state()
                fails += 1
                block = min(self._LOCK_BASE_S * (2 ** (fails - 1)),
                            self._LOCK_CAP_S)
                cache.save_json(self._LOCK_FILE, {
                    "fails": fails, "block_until": time.time() + block})
                logsetup.get_logger(__name__).warning(
                    "PIN 5 marta noto'g'ri — %ds blok (jami %d marta)",
                    block, fails)
        finally:
            self.pin_open = False
        if ok:
            # Muvaffaqiyatli chiqish — brute-force hisoblagichini tozalaymiz.
            cache.save_json(self._LOCK_FILE, {"fails": 0, "block_until": 0})
            self.on_exit()
