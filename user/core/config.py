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


def _read_trust_json():
    """trust.json'dagi url/api_key'ni qaytaradi (server.txt'ga muqobil/zaxira
    manba — o'rnatuvchi qo'ygan ishonch lavhasi). Kriptografik material
    (public_key, cert) core/trust.py orqali o'qiladi; bu yerda faqat ulanish
    uchun url va kalit kerak. Cycle bo'lmasin uchun JSON to'g'ridan o'qiladi."""
    import json
    try:
        with open(os.path.join(_base_dir(), "trust.json"), encoding="utf-8") as f:
            t = json.load(f)
        return (t.get("url") or "").strip() or None, t.get("api_key") or None
    except (OSError, ValueError):
        return None, None


_TXT_URL, _TXT_KEY, _TXT_EXTRA = _read_server_txt()
_TRUST_URL, _TRUST_KEY = _read_trust_json()

# Server manzili. Statik IP tavsiya etiladi (TZ 11.3), lekin endi qo'lda
# yozish SHART EMAS — yozilmasa discovery (imzolangan UDP beacon) topadi.
# Ustuvorlik:
#   1) KIOSK_SERVER env  2) server.txt  3) trust.json  4) discovery (runtime)
# Hech biri bo'lmasa — vaqtincha standart (discovery resolve qilmaguncha).
SERVER_URL = (os.environ.get("KIOSK_SERVER")
              or _TXT_URL
              or _TRUST_URL
              or "https://192.168.136.69:8765")

# Discovery topgan manzilmi? (qo'lda berilmagan bo'lsa True) — main shu holatda
# resolve_server() ni chaqiradi.
SERVER_CONFIGURED = bool(os.environ.get("KIOSK_SERVER")
                         or _TXT_URL or _TRUST_URL)

# API kalit — server admin oynasida ko'rinadi, o'rnatishda kiritiladi.
# Ustuvorlik: 1) KIOSK_API_KEY env  2) server.txt  3) trust.json
API_KEY = (os.environ.get("KIOSK_API_KEY") or _TXT_KEY or _TRUST_KEY or "")

# Discovery UDP porti (server config.DISCOVERY_PORT bilan bir xil bo'lishi shart)
DISCOVERY_PORT = int(os.environ.get("KIOSK_DISCOVERY_PORT", "8766"))

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

# WebSocket manzili (SERVER_URL'dan avtomatik hosil qilinadi: http->ws,
# https->wss). Kalit query param sifatida ketadi — server tomonda REST bilan
# bir xil tekshiriladi, websockets kutubxonasiga header berish shart emas.
def _build_ws_url():
    return (SERVER_URL.replace("http://", "ws://").replace("https://", "wss://")
            + "/ws" + (f"?k={API_KEY}" if API_KEY else ""))


WS_URL = _build_ws_url()


def is_tls():
    """Joriy server manzili shifrlangan (https/wss) kanalmi?"""
    return SERVER_URL.lower().startswith("https://")


def set_server(url, api_key=None):
    """Serverni runtime'da o'rnatadi (discovery topgan/tanlangan manzil).

    SERVER_URL, API_KEY va WS_URL'ni yangilaydi. ApiClient/WSClient bu
    qiymatlarni o'z konstruktorida o'qiganlari uchun — shu chaqiruv ULARDAN
    OLDIN (main'da, MainWindow yaratilishidan oldin) bajarilishi kerak."""
    global SERVER_URL, API_KEY, WS_URL
    SERVER_URL = url.rstrip("/")
    if api_key:
        API_KEY = api_key
    WS_URL = _build_ws_url()

# HTTP so'rovlar uchun timeout (soniya)
REQUEST_TIMEOUT = 5

# Server uzilganda qayta ulanish oralig'i (millisekund) — TZ 12.2: har 5 soniyada
RECONNECT_INTERVAL_MS = 5000

# Boshlang'ich mavzu: "light" yoki "dark"
DEFAULT_THEME = "light"

# --- Oyna rejimi: kiosk (fullscreen, qulfli) yoki oddiy ramkali oyna ---
# WINDOWED=True: ramkali oyna (min/max/close), fullscreen emas, OS qulfi yo'q —
# ishlab chiqish/sozlash uchun qulay.
# STANDART: frozen (build qilingan Kiosk.exe) -> KIOSK REJIM (fullscreen);
# manbadan (python main.py) -> oddiy oyna. Ya'ni o'rnatilgan kiosk avtomatik
# to'liq ekran bo'ladi. Aniq boshqarish: KIOSK_WINDOWED=1 (oddiy) / =0 (kiosk).
WINDOWED = os.environ.get(
    "KIOSK_WINDOWED", "0" if getattr(sys, "frozen", False) else "1") != "0"

# --- Maxfiy texnik chiqish (kiosk qulflangan bo'lsa ham ishlaydi) ---
# Navbar'dagi SOAT ustiga EXIT_TAPS marta tez-tez tegilsa PIN klaviatura
# ochiladi. To'g'ri PIN -> dastur yopiladi. Sensorli (klaviatura/sichqonsiz)
# monitorlarda ham ishlaydi. Soat ko'rinmasa ('ulanmoqda' ekrani) — zaxira:
# ekran yuqori-o'ng burchagi (EXIT_CORNER_PX zona).
# PIN'ni muhit o'zgaruvchisi orqali ham berish mumkin: KIOSK_EXIT_PIN=1234
EXIT_PIN = os.environ.get("KIOSK_EXIT_PIN", "7777")
EXIT_TAPS = 10             # nechta teginish kerak
EXIT_TAP_WINDOW_S = 4.0    # shu soniya ichida (sekin bosilsa hisob qaytadan)
EXIT_CORNER_PX = 90        # zaxira burchak zonasi (bazaviy px, miqyoslanadi)

# DASTURCHI (vendor) master PIN — mijoz PINidan mustaqil maxfiy chiqish.
# Endi kodda OCHIQ MATN sifatida saqlanmaydi (exe'dan `strings` bilan
# chiqarib olinardi — har bir kiosk lockdown'ini ochib berardi). Faqat
# PBKDF2 xesh ko'rinishida beriladi: KIOSK_DEV_PIN_HASH muhit o'zgaruvchisi
# (server bilan bir xil `pbkdf2$iter$salt$hash` format). O'rnatilmagan
# bo'lsa master PIN BUTUNLAY O'CHIQ (fail-closed). Xesh yaratish:
#   python -c "from core import pinhash; print(pinhash.hash_secret('PIN'))"
DEV_EXIT_PIN_HASH = os.environ.get("KIOSK_DEV_PIN_HASH", "")

# --- Zastavka (splash + screensaver, logotipli ekran) ---
# Dastur ochilganda SPLASH_SECONDS soniya logotip ko'rinadi. Keyin foydalanuvchi
# SCREENSAVER_IDLE_MIN daqiqa hech narsa bosmasa (va video/audio/kitob ochiq
# bo'lmasa) yana chiqadi; istalgan teginish yopadi — ilova qolgan joyidan
# davom etadi.
SPLASH_SECONDS = 4
SCREENSAVER_IDLE_MIN = 10
