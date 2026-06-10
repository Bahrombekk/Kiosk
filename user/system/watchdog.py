"""
watchdog.py — Kiosk nazoratchisi (auto-restart).

Poyezddagi kiosk nazoratsiz ishlaydi: ilova qulasa (VLC segfault, xotira
tugashi, kutilmagan istisno) ekran qora bo'lib qolmasligi kerak. Shu skript
Kiosk.exe'ni ishga tushiradi va kuzatadi:

  - chiqish kodi 0  -> toza chiqish (PIN / Ctrl+Shift+Q) — watchdog ham yopiladi
  - boshqa kod      -> crash — 3 soniyadan keyin qayta ishga tushiradi

Himoyalar:
  - crash-loop: 120s ichida 5 marta qulasa, 60s kutadi (CPU bandligi va
    miltillagan qora ekran bo'lmasin)
  - yagona nusxa: Windows mutex orqali (login + installer ikkala marta
    ishga tushirsa ham bitta watchdog qoladi)

PyInstaller'da alohida KioskWatchdog.exe bo'lib chiqadi (kiosk.spec),
autostart registri Kiosk.exe o'rniga shuni ko'rsatadi (installer.iss).
Qt ishlatilmaydi — minimal, mustahkam.
"""
import ctypes
import logging
import logging.handlers
import os
import subprocess
import sys
import time

RESTART_DELAY_S = 3
LOOP_WINDOW_S = 120     # shu oynada...
LOOP_MAX_RESTARTS = 5   # ...shuncha restart bo'lsa -> uzun tanaffus
LOOP_COOLDOWN_S = 60

ERROR_ALREADY_EXISTS = 183


def _base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    # Manba rejimi: bu fayl system/ ichida — user/ ildiziga chiqamiz
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _setup_log():
    log_dir = os.path.join(_base_dir(), "logs")
    log = logging.getLogger("watchdog")
    log.setLevel(logging.INFO)
    try:
        os.makedirs(log_dir, exist_ok=True)
        fh = logging.handlers.RotatingFileHandler(
            os.path.join(log_dir, "watchdog.log"),
            maxBytes=500_000, backupCount=2, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s"))
        log.addHandler(fh)
    except OSError:
        pass
    if not getattr(sys, "frozen", False):
        log.addHandler(logging.StreamHandler())
    return log


def _single_instance():
    """Ikkinchi nusxa ishga tushmasin (True = davom et, False = chiqib ket)."""
    ctypes.windll.kernel32.CreateMutexW(None, False, "Global\\KioskWatchdog")
    return ctypes.windll.kernel32.GetLastError() != ERROR_ALREADY_EXISTS


def _kiosk_cmd():
    """Frozen: yonidagi Kiosk.exe; dev: python main.py (sinov uchun)."""
    if getattr(sys, "frozen", False):
        return [os.path.join(_base_dir(), "Kiosk.exe")]
    return [sys.executable, os.path.join(_base_dir(), "main.py")]


def main():
    if os.name != "nt":
        sys.exit("Bu watchdog faqat Windows uchun.")
    if not _single_instance():
        return
    log = _setup_log()
    cmd = _kiosk_cmd()
    log.info("Watchdog boshlandi: %s", " ".join(cmd))

    restarts = []   # so'nggi restart vaqtlari (monotonic)
    while True:
        try:
            proc = subprocess.Popen(cmd, cwd=_base_dir())
        except OSError as e:
            log.error("Kioskni ishga tushirib bo'lmadi: %s", e)
            time.sleep(LOOP_COOLDOWN_S)
            continue
        rc = proc.wait()
        if rc == 0:
            log.info("Kiosk toza yopildi (admin chiqishi) — watchdog tugaydi")
            return
        log.warning("Kiosk quladi (chiqish kodi %s) — qayta ishga tushiriladi", rc)

        now = time.monotonic()
        restarts = [t for t in restarts if now - t <= LOOP_WINDOW_S]
        restarts.append(now)
        if len(restarts) >= LOOP_MAX_RESTARTS:
            log.error("Crash-loop aniqlandi (%d restart / %ds) — %ds tanaffus",
                      len(restarts), LOOP_WINDOW_S, LOOP_COOLDOWN_S)
            time.sleep(LOOP_COOLDOWN_S)
            restarts.clear()
        else:
            time.sleep(RESTART_DELAY_S)


if __name__ == "__main__":
    main()
