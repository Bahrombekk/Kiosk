"""
config.py — Foydalanuvchi ilovasining sozlamalari (bir joyda).

Bu yerda server manzili va ulanish parametrlari turadi. Har bir qurilmaga
o'rnatishda faqat SHU faylni (yoki KIOSK_SERVER muhit o'zgaruvchisini)
o'zgartirasiz — kodga tegmaysiz (TZ 11.3 — "Serverni topish").
"""
import os
import sys


def _base_dir():
    """Exe (frozen) yoki loyiha papkasi — server.txt/loglar shu yerda.

    MUHIM: bu fayl endi core/ ichida — manba rejimida bir pog'ona yuqoriga
    (user/ ildiziga) chiqamiz."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Ilova ildiz papkasi (exe yonidagi yoki user/ manba papkasi) — server.txt,
# cache/, logs/ shu yerda. Boshqa modullar ham shu yagona qiymatni ishlatadi.
APP_DIR = _base_dir()


def _read_server_txt():
    """server.txt'ni o'qiydi: (url, api_key) qaytaradi.

    Fayl formati (installer yozadi, admin bloknotda tahrirlashi mumkin):
        # izoh
        http://192.168.1.10:8765
        key=AbCdEf...
    Birinchi oddiy qator — URL (eski format bilan mos), `key=` qatori —
    API kalit."""
    url, key = None, None
    try:
        with open(os.path.join(_base_dir(), "server.txt"), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.lower().startswith("key="):
                    key = line[4:].strip()
                elif url is None:
                    url = line
    except OSError:
        pass
    return url, key


_TXT_URL, _TXT_KEY = _read_server_txt()

# Server manzili. Statik IP tavsiya etiladi (TZ 11.3). Ustuvorlik:
#   1) KIOSK_SERVER muhit o'zgaruvchisi  2) server.txt  3) default
SERVER_URL = (os.environ.get("KIOSK_SERVER")
              or _TXT_URL
              or "http://192.168.136.69:8765")

# API kalit — server admin oynasida ko'rinadi, o'rnatishda kiritiladi.
# Ustuvorlik: 1) KIOSK_API_KEY env  2) server.txt'dagi key= qatori
API_KEY = os.environ.get("KIOSK_API_KEY") or _TXT_KEY or ""

# WebSocket manzili (SERVER_URL'dan avtomatik hosil qilinadi: http->ws).
# Kalit query param sifatida ketadi — server tomonda REST bilan bir xil
# tekshiriladi, websockets kutubxonasiga header berish shart emas.
WS_URL = (SERVER_URL.replace("http://", "ws://").replace("https://", "wss://")
          + "/ws" + (f"?k={API_KEY}" if API_KEY else ""))

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
