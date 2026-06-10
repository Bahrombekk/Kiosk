"""
i18n.py — Interfeys tarjimalari (UZ / RU / EN).

Faqat INTERFEYS matnlari tarjima qilinadi — kontent (kino nomlari, kitob
matnlari, bekat nomlari, e'lonlar) admin kiritgan tilda qoladi.

Ishlatish:
    from core.i18n import tr
    btn.setText(tr("videos.watch"))
    lbl.setText(tr("pin.wrong", n=3))

Til almashganda (i18n.set_lang) main.py sahifalarni qayta quradi — har bir
widget tr()ni qurilish paytida chaqirgani uchun retranslate mexanizmi kerak emas.
"""

LANGS = ("uz", "ru", "en")
DEFAULT = "uz"
_lang = DEFAULT


def set_lang(code):
    global _lang
    if code in LANGS:
        _lang = code


def get_lang():
    return _lang


def tr(key, **kw):
    """Joriy tildagi matn. Format argumentlari: tr("pin.wrong", n=3)."""
    txt = STRINGS[key][LANGS.index(_lang)]
    return txt.format(**kw) if kw else txt


def month_name(m):
    """Oy nomi (m = 1..12), joriy tilda. RU — roditelniy kelishik (sana uchun)."""
    return MONTHS[_lang][m - 1]


def fmt_duration(seconds):
    """Soniyani odam o'qiydigan davomiylikka aylantiradi (til-sezgir)."""
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return ""
    if seconds <= 0:
        return ""
    h, m = seconds // 3600, (seconds % 3600) // 60
    if h and m:
        return tr("dur.hour_min", h=h, m=m)
    if h:
        return tr("dur.hour", h=h)
    return tr("dur.min", m=m)


# Har kalit: (uz, ru, en)
STRINGS = {
    # --- Navigatsiya (theme.NAV_ITEMS kalitlari bilan mos) ---
    "nav.home":     ("Asosiy",   "Главная",  "Home"),
    "nav.map":      ("Xarita",   "Карта",    "Map"),
    "nav.videos":   ("Videolar", "Видео",    "Videos"),
    "nav.books":    ("Kitoblar", "Книги",    "Books"),
    "nav.sites":    ("Saytlar",  "Сайты",    "Websites"),
    "title.map":    ("Xarita",   "Карта",    "Map"),
    "title.videos": ("Videolar", "Видео",    "Videos"),
    "title.books":  ("Kitoblar", "Книги",    "Books"),
    "title.sites":  ("Saytlar",  "Сайты",    "Websites"),

    # --- Umumiy (bir nechta ekranda takrorlanadi) ---
    "common.loading":       ("Yuklanmoqda...",       "Загрузка...",           "Loading..."),
    "common.load_failed":   ("Yuklab bo'lmadi",      "Не удалось загрузить",  "Failed to load"),
    "common.nothing_found": ("Hech narsa topilmadi", "Ничего не найдено",     "Nothing found"),
    "common.back":          ("←  Ortga",             "←  Назад",              "←  Back"),
    "common.offline":       ("● Oflayn",             "● Офлайн",              "● Offline"),
    "common.listen":        (" Tinglash",            " Слушать",              " Listen"),
    "common.read":          (" O'qish",              " Читать",               " Read"),
    "common.tab_all":       ("Barchasi",             "Все",                   "All"),

    # --- Videolar ---
    "videos.tab.movies":   ("Kinolar",     "Фильмы",      "Movies"),
    "videos.tab.cartoons": ("Multfilmlar", "Мультфильмы", "Cartoons"),
    "videos.tab.music":    ("Musiqa",      "Музыка",      "Music"),
    "videos.search":       ("Nomi bo'yicha qidirish", "Поиск по названию", "Search by title"),
    "videos.watch":        ("▶  Tomosha qilish", "▶  Смотреть", "▶  Watch"),
    "videos.offline": ("Server bilan aloqa yo'q — video vaqtincha mavjud emas",
                       "Нет связи с сервером — видео временно недоступно",
                       "No server connection — video is temporarily unavailable"),
    "audio.offline":  ("Server bilan aloqa yo'q — audio vaqtincha mavjud emas",
                       "Нет связи с сервером — аудио временно недоступно",
                       "No server connection — audio is temporarily unavailable"),

    "books.pages": ("{n} sahifa", "{n} стр.", "{n} pages"),

    # --- Kitob tablari (faqat YORLIQ; filtr kaliti DB'dagi o'zbekcha qiymat) ---
    "books.tab.fiction":  ("Badiiy",    "Художественная", "Fiction"),
    "books.tab.history":  ("Tarixiy",   "Историческая",   "History"),
    "books.tab.business": ("Biznes",    "Бизнес",         "Business"),
    "books.tab.kids":     ("Bolalarga", "Детям",          "For kids"),

    # --- Asosiy ekran ---
    "home.speed":    ("Tezlik",  "Скорость",    "Speed"),
    "home.temp":     ("Harorat", "Температура", "Temperature"),
    "home.location": ("Joylashuv", "Расположение", "Location"),
    "home.location_wagon": ("Joylashuv: {wagon}-vagon",
                            "Расположение: вагон {wagon}",
                            "Location: car {wagon}"),
    "home.recommend": ("Tavsiya etamiz", "Рекомендуем", "Recommended"),

    # --- Xarita ---
    "map.train":    ("Poyezd",            "Поезд",            "Train"),
    "map.departed": ("Jo'nagan: {t}",     "Отправился: {t}",  "Departed: {t}"),
    "map.arrival":  ("Yetib kelish: {t}", "Прибытие: {t}",    "Arrival: {t}"),
    "map.depart":   ("Jo'nash: {t}",      "Отправление: {t}", "Departure: {t}"),
    "map.date_fmt": ("{day}-{month}, {year}", "{day} {month}, {year}",
                     "{month} {day}, {year}"),

    # --- Saytlar ---
    "sites.empty":    ("Saytlar yo'q", "Сайтов нет", "No websites"),
    "sites.qr_title": ("Telefoningizda oching", "Откройте на телефоне",
                       "Open on your phone"),
    "sites.step1": ("Telefon kamerasini QR kodga yo'llang",
                    "Наведите камеру телефона на QR-код",
                    "Point your phone camera at the QR code"),
    "sites.step2": ("Havolaga bosiladi — brauzerda ochiladi",
                    "Нажмите на ссылку — откроется в браузере",
                    "Tap the link — it opens in your browser"),
    "sites.step3": ("Xizmatdan uyda ham foydalanishingiz mumkin",
                    "Сервисом можно пользоваться и дома",
                    "You can also use the service at home"),

    # --- Ulanish ekrani ---
    "conn.connecting": ("Serverga ulanmoqda...", "Подключение к серверу...",
                        "Connecting to server..."),
    "conn.retry": ("Serverga ulanib bo'lmadi, qayta urinilmoqda...",
                   "Не удалось подключиться к серверу, повторная попытка...",
                   "Could not connect to the server, retrying..."),

    # --- Kitob o'quvchi ---
    "reader.text_failed": ("Matnni yuklab bo'lmadi", "Не удалось загрузить текст",
                           "Failed to load text"),

    # --- PIN klaviatura ---
    "pin.title":  ("Texnik chiqish", "Технический выход", "Technical exit"),
    "pin.cancel": ("Bekor qilish",   "Отмена",            "Cancel"),
    "pin.wrong":  ("Noto'g'ri PIN ({n} urinish qoldi)",
                   "Неверный PIN (осталось попыток: {n})",
                   "Wrong PIN ({n} attempts left)"),

    # --- Davomiylik formati ---
    "dur.hour_min": ("{h} soat {m} daqiqa", "{h} ч {m} мин", "{h} h {m} min"),
    "dur.hour":     ("{h} soat",            "{h} ч",         "{h} h"),
    "dur.min":      ("{m} daqiqa",          "{m} мин",       "{m} min"),
}

MONTHS = {
    "uz": ["Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
           "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"],
    # RU — roditelniy kelishik ("10 января, 2026" ko'rinishi uchun)
    "ru": ["января", "февраля", "марта", "апреля", "мая", "июня",
           "июля", "августа", "сентября", "октября", "ноября", "декабря"],
    "en": ["January", "February", "March", "April", "May", "June",
           "July", "August", "September", "October", "November", "December"],
}
