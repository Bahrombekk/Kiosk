"""
config.py — Foydalanuvchi ilovasining sozlamalari (bir joyda).

Bu yerda server manzili va ulanish parametrlari turadi. Har bir qurilmaga
o'rnatishda faqat SHU faylni (yoki KIOSK_SERVER muhit o'zgaruvchisini)
o'zgartirasiz — kodga tegmaysiz (TZ 11.3 — "Serverni topish").
"""
import os
import sys


def _external_server_url():
    """O'rnatilgan ilovada exe (yoki loyiha) yonidagi server.txt dan o'qiydi.

    Installer shu faylni yozadi; keyinchalik administrator oddiy bloknot
    bilan tahrirlashi mumkin — qayta o'rnatish shart emas."""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    try:
        with open(os.path.join(base, "server.txt"), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    return line
    except OSError:
        pass
    return None


# Server manzili. Statik IP tavsiya etiladi (TZ 11.3). Ustuvorlik:
#   1) KIOSK_SERVER muhit o'zgaruvchisi  2) server.txt  3) default
SERVER_URL = (os.environ.get("KIOSK_SERVER")
              or _external_server_url()
              or "http://192.168.136.69:8765")

# WebSocket manzili (SERVER_URL'dan avtomatik hosil qilinadi: http->ws)
WS_URL = SERVER_URL.replace("http://", "ws://").replace("https://", "wss://") + "/ws"

# HTTP so'rovlar uchun timeout (soniya)
REQUEST_TIMEOUT = 5

# Server uzilganda qayta ulanish oralig'i (millisekund) — TZ 12.2: har 5 soniyada
RECONNECT_INTERVAL_MS = 5000

# Boshlang'ich mavzu: "light" yoki "dark"
DEFAULT_THEME = "light"

# --- Maxfiy texnik chiqish (kiosk qulflangan bo'lsa ham ishlaydi) ---
# Navbar'dagi SOAT ustiga EXIT_TAPS marta tez-tez tegilsa PIN klaviatura
# ochiladi. To'g'ri PIN -> dastur yopiladi. Sensorli (klaviatura/sichqonsiz)
# monitorlarda ham ishlaydi. Soat ko'rinmasa ('ulanmoqda' ekrani) — zaxira:
# ekran yuqori-o'ng burchagi (EXIT_CORNER_PX zona).
# PIN'ni muhit o'zgaruvchisi orqali ham berish mumkin: KIOSK_EXIT_PIN=1234
EXIT_PIN = os.environ.get("KIOSK_EXIT_PIN", "7777")
EXIT_TAPS = 7              # nechta teginish kerak
EXIT_TAP_WINDOW_S = 4.0    # shu soniya ichida (sekin bosilsa hisob qaytadan)
EXIT_CORNER_PX = 90        # zaxira burchak zonasi (bazaviy px, miqyoslanadi)

# --- Zastavka (splash + screensaver, logotipli ekran) ---
# Dastur ochilganda SPLASH_SECONDS soniya logotip ko'rinadi. Keyin foydalanuvchi
# SCREENSAVER_IDLE_MIN daqiqa hech narsa bosmasa (va video/audio/kitob ochiq
# bo'lmasa) yana chiqadi; istalgan teginish yopadi — ilova qolgan joyidan
# davom etadi.
SPLASH_SECONDS = 4
SCREENSAVER_IDLE_MIN = 10
