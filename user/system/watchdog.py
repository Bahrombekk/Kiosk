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

# UI liveness: Kiosk GUI oqimi har 10s `alive.beat`ni yangilaydi (main.py).
# Fayl shu seansda kamida bir marta yozilgan bo'lib, keyin STALL_S dan uzoq
# yangilanmasa — protsess tirik, lekin UI muzlagan (Qt deadlock / VLC hang):
# watchdog uni majburan o'ldirib qayta ochadi. 3 daqiqa — soat sinxronidagi
# kichik sakrashlar yolg'on-musbat bermasligi uchun ataylab keng olingan.
HEARTBEAT_FILE = "alive.beat"
STALL_S = 180
POLL_S = 10

ERROR_ALREADY_EXISTS = 183

# Operator/admin chiqishi shu faylni yaratsa, watchdog qayta ishga tushirmaydi
# (texnik xizmat uchun ilovani o'ldirish endi cheksiz relaunch bermaydi).
STOP_SENTINEL = "watchdog.stop"

_mutex = None   # MUHIM: handle'ni tirik saqlaymiz — aks holda mutex darhol bo'shaydi


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
    global _mutex
    # Handle modul-global'da saqlanadi — mahalliy o'zgaruvchi bo'lsa GC darhol
    # mutex'ni bo'shatib, yagona-nusxa himoyasini buzardi.
    _mutex = ctypes.windll.kernel32.CreateMutexW(None, False,
                                                 "Global\\KioskWatchdog")
    return ctypes.windll.kernel32.GetLastError() != ERROR_ALREADY_EXISTS


def _stop_requested():
    return os.path.isfile(os.path.join(_base_dir(), STOP_SENTINEL))


def _clear_stop():
    try:
        os.remove(os.path.join(_base_dir(), STOP_SENTINEL))
    except OSError:
        pass


def _kiosk_cmd():
    """Frozen: yonidagi Kiosk.exe; dev: python main.py (sinov uchun)."""
    if getattr(sys, "frozen", False):
        return [os.path.join(_base_dir(), "Kiosk.exe")]
    return [sys.executable, os.path.join(_base_dir(), "main.py")]


def _ensure_desktop_shell():
    """Toza chiqishda: agar BIZ Windows shell bo'lsak (explorer ishlamayapti —
    ya'ni shell almashtirilgan kiosk), texnik xizmat uchun explorer.exe ni
    ishga tushiramiz. Aks holda (oddiy rejim, explorer allaqachon ishlayapti)
    hech narsa qilmaymiz — ortiqcha oyna ochilmasin."""
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq explorer.exe", "/NH"],
            capture_output=True, text=True, timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if "explorer.exe" not in (out.stdout or "").lower():
            subprocess.Popen(["explorer.exe"])
    except Exception:                                # noqa: BLE001
        pass


def main():
    if os.name != "nt":
        sys.exit("Bu watchdog faqat Windows uchun.")
    if not _single_instance():
        return
    log = _setup_log()
    _clear_stop()   # oldingi seansdan qolgan sentinel'ni tozalaymiz
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
        # Blokirovkali wait() o'rniga poll — protsess tirik bo'lsa ham UI
        # muzlagan bo'lishi mumkin (exit-code buni hech qachon ko'rsatmaydi).
        spawn_t = time.time()
        beat = os.path.join(_base_dir(), HEARTBEAT_FILE)
        while True:
            try:
                rc = proc.wait(timeout=POLL_S)
                break
            except subprocess.TimeoutExpired:
                pass
            try:
                mt = os.path.getmtime(beat)
            except OSError:
                continue   # heartbeat fayli hali yo'q (eski build) — kuzatmaymiz
            if mt <= spawn_t:
                continue   # bu seansda hali yozilmagan (ilova ochilmoqda)
            if time.time() - mt > STALL_S:
                log.error("UI muzladi (heartbeat %.0fs yangilanmadi) — "
                          "majburan qayta ochiladi", time.time() - mt)
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    capture_output=True,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                rc = proc.wait()
                if rc == 0:
                    rc = 1   # majburiy o'ldirish toza chiqish emas — restart
                break
        if rc == 0:
            log.info("Kiosk toza yopildi (admin chiqishi) — watchdog tugaydi")
            _ensure_desktop_shell()   # shell bo'lsak — explorer ochamiz (xizmat)
            return
        # Texnik xizmat: admin/operator stop-sentinel qoldirgan bo'lsa, ilova
        # tashqaridan o'ldirilgan bo'lsa ham qayta tirkamaymiz.
        if _stop_requested():
            log.info("Stop-sentinel topildi — watchdog qayta tushirmaydi")
            _clear_stop()
            _ensure_desktop_shell()
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
