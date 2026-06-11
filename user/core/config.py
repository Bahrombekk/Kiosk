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
    """server.txt'ni o'qiydi: (url, api_key, qo'shimcha) qaytaradi.

    Fayl formati (installer yozadi, admin bloknotda tahrirlashi mumkin):
        # izoh
        http://192.168.1.10:8765
        key=AbCdEf...
        kiosk=6          # kiosk raqami (admin jadvalida ko'rinadi)
        xona=12          # xona/vagon raqami
        cache=0          # lokal media keshni o'chirish (standart: yoqiq)
    Birinchi oddiy qator — URL (eski format bilan mos), qolgan `k=v`
    qatorlari qo'shimcha sozlamalar lug'atiga tushadi."""
    url, key, extra = None, None, {}
    try:
        with open(os.path.join(_base_dir(), "server.txt"), encoding="utf-8") as f:
            for line in f:
                line = line.split("#", 1)[0].strip()   # qator oxiri izohlari
                if not line:
                    continue
                if "=" in line:
                    k, _, v = line.partition("=")
                    k, v = k.strip().lower(), v.strip()
                    if k == "key":
                        key = v
                    else:
                        extra[k] = v
                elif url is None:
                    url = line
    except OSError:
        pass
    return url, key, extra


_TXT_URL, _TXT_KEY, _TXT_EXTRA = _read_server_txt()

# Server manzili. Statik IP tavsiya etiladi (TZ 11.3). Ustuvorlik:
#   1) KIOSK_SERVER muhit o'zgaruvchisi  2) server.txt  3) default
SERVER_URL = (os.environ.get("KIOSK_SERVER")
              or _TXT_URL
              or "http://192.168.136.69:8765")

# API kalit — server admin oynasida ko'rinadi, o'rnatishda kiritiladi.
# Ustuvorlik: 1) KIOSK_API_KEY env  2) server.txt'dagi key= qatori
API_KEY = os.environ.get("KIOSK_API_KEY") or _TXT_KEY or ""

# Kiosk raqami va xona/vagon raqami — o'rnatuvchi server.txt'ga yozadi
# (kiosk= / xona= qatorlari); admin "Kiosklar" jadvalida ko'rinadi.
KIOSK_NO = (os.environ.get("KIOSK_NO")
            or _TXT_EXTRA.get("kiosk") or _TXT_EXTRA.get("kiosk_no") or "")
ROOM_NO = (os.environ.get("KIOSK_ROOM")
           or _TXT_EXTRA.get("xona") or _TXT_EXTRA.get("room") or "")

# Lokal media kesh: kontent fayllari fonda kiosk diskiga yuklab qo'yiladi
# (oflaynda ham ijro etiladi). server.txt'da `cache=0` — o'chiradi.
MEDIA_CACHE_DISABLED = (_TXT_EXTRA.get("cache", "").strip() == "0"
                        or os.environ.get("KIOSK_MEDIA_CACHE") == "0")

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
