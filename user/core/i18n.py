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

import logging

log = logging.getLogger(__name__)

LANGS = ("uz", "ru", "en")
DEFAULT = "uz"
_lang = DEFAULT


def set_lang(code):
    global _lang
    if code in LANGS:
        _lang = code


def get_lang():
    return _lang


def content_visible(item):
    """Kontent joriy interfeys tilida ko'rinsinmi? (qat'iy til filtri)

    Admin har kontentga til belgilaydi: 'uz'/'ru'/'en' — faqat shu til
    tanlanganda ko'rinadi; bo'sh (None) — "barcha tillarda" (instrumental
    musiqa kabi) har tilda chiqadi."""
    lang = (item.get("lang") or "").strip()
    return not lang or lang == _lang


def tr(key, **kw):
    """Joriy tildagi matn. Format argumentlari: tr("pin.wrong", n=3).

    Kalit topilmasa yoki format mos kelmasa — yiqilmaymiz: kalitning o'zini
    (yoki formatlanmagan matnni) qaytaramiz, bitta typo butun ekranni buzmasin."""
    entry = STRINGS.get(key)
    if entry is None:
        log.warning("i18n: topilmagan kalit %r", key)
        return key
    txt = entry[LANGS.index(_lang)]
    if not kw:
        return txt
    try:
        return txt.format(**kw)
    except (KeyError, IndexError, ValueError):
        log.warning("i18n: format mos emas (kalit %r)", key)
        return txt


# Janr/bo'lim nomlari odatda admin tilida (o'zbekcha) kiritiladi. RU/EN tanlanса
# tab/bo'lim sarlavhalari aralash ko'rinmasin — KENG TARQALGAN janrlarni
# tarjima qilamiz; ro'yxatda yo'q (maxsus) janr xom holicha qoladi.
_GENRE_MAP = {
    "badiiy": ("Художественная", "Fiction"),
    "tarixiy": ("Историческая", "Historical"),
    "bolalar adabiyoti": ("Детская литература", "Children's"),
    "bolalar": ("Детская", "Children's"),
    "biznes": ("Бизнес", "Business"),
    "ilmiy": ("Научная", "Science"),
    "ilmiy-fantastika": ("Научная фантастика", "Sci-Fi"),
    "fantastika": ("Фантастика", "Fantasy"),
    "detektiv": ("Детектив", "Detective"),
    "komediya": ("Комедия", "Comedy"),
    "drama": ("Драма", "Drama"),
    "melodrama": ("Мелодрама", "Melodrama"),
    "jangari": ("Боевик", "Action"),
    "triller": ("Триллер", "Thriller"),
    "multfilm": ("Мультфильм", "Cartoon"),
    "hujjatli": ("Документальная", "Documentary"),
    "zamonaviy": ("Современная", "Modern"),
    "instrumental": ("Инструментальная", "Instrumental"),
    "saundtrek": ("Саундтрек", "Soundtrack"),
    "audiokitob": ("Аудиокнига", "Audiobook"),
    "namuna": ("Образец", "Sample"),
}


def genre_label(name):
    """Janr/bo'lim nomini joriy tilда qaytaradi. Ma'lum janr tarjima qilinadi,
    noma'lumi — xom holicha (admin kiritgan tilда)."""
    if not name:
        return name
    pair = _GENRE_MAP.get(name.strip().lower())
    if pair is None or _lang == "uz":
        return name
    return pair[0] if _lang == "ru" else pair[1]


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
    if m:
        return tr("dur.min", m=m)
    # 1 daqiqadan kam (qisqa klip) — "0 daqiqa" emas, soniya ko'rsatamiz
    return tr("dur.sec", s=seconds)


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

    # --- Server tanlash (bir nechta server topilganda) ---
    "conn.choose_title": ("Server tanlang", "Выберите сервер", "Choose server"),
    "conn.choose_label": ("Bir nechta server topildi. Qaysi biriga ulanamiz?",
                          "Найдено несколько серверов. К какому подключиться?",
                          "Multiple servers found. Which one to connect to?"),
    "common.other":         ("Boshqa",               "Другое",                "Other"),

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
    # Oflayn rejim: faqat lokal keshga yuklab olingan kontent ko'rinadi
    "offline.local_only": ("Oflayn rejim — faqat yuklab olingan kontent",
                           "Офлайн режим — только загруженный контент",
                           "Offline mode — only downloaded content"),
    "offline.last_sync":  ("oxirgi sinx", "последняя синхр.", "last sync"),
    "offline.empty":      ("Oflayn — yuklab olingan kontent yo'q",
                           "Офлайн — нет загруженного контента",
                           "Offline — no downloaded content"),

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
    "map.qr_title": ("Manzilni telefoningizga oling",
                     "Возьмите адрес с собой на телефоне",
                     "Take the location on your phone"),
    "map.qr_hint": ("Telefon kamerasini QR kodga yo'llang — bekat xarita "
                    "ilovasida ochiladi",
                    "Наведите камеру телефона на QR-код — станция откроется "
                    "в приложении карт",
                    "Point your phone camera at the QR code — the station "
                    "opens in your maps app"),

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

    # --- Favqulodda ma'lumot (SOS) ---
    "sos.btn":   ("SOS", "SOS", "SOS"),
    "sos.title": ("Favqulodda holatlar", "Экстренные службы", "Emergency"),
    "sos.unified":   ("Yagona qutqaruv xizmati", "Единая служба спасения",
                      "Unified emergency service"),
    "sos.fire":      ("Yong'in xizmati", "Пожарная служба", "Fire service"),
    "sos.police":    ("Politsiya", "Полиция", "Police"),
    "sos.ambulance": ("Tez tibbiy yordam", "Скорая помощь", "Ambulance"),
    "sos.location":  ("Siz shu yerdasiz: {loc}", "Вы находитесь здесь: {loc}",
                      "You are here: {loc}"),
    "sos.hint": ("Qo'ng'iroq qilganda joylashuvingizni ayting",
                 "При звонке назовите ваше местоположение",
                 "Tell the operator your location when calling"),

    # --- PIN klaviatura ---
    "pin.title":  ("Texnik chiqish", "Технический выход", "Technical exit"),
    "pin.cancel": ("Bekor qilish",   "Отмена",            "Cancel"),
    "pin.wrong":  ("Noto'g'ri PIN ({n} urinish qoldi)",
                   "Неверный PIN (осталось попыток: {n})",
                   "Wrong PIN ({n} attempts left)"),

    # --- Audio/kitob pleyeri ---
    "player.now_playing": ("Hozir ijro etilmoqda", "Сейчас играет", "Now playing"),
    "player.speed":       ("Tezlik", "Скорость", "Speed"),
    "player.chapters":    ("Boblar", "Главы", "Chapters"),
    "player.timer":       ("Taymer", "Таймер", "Timer"),
    "player.timer_val":   ("Taymer · {t}", "Таймер · {t}", "Timer · {t}"),
    "player.shuffle":     ("Aralash", "Перемешать", "Shuffle"),
    "player.favorites":   ("Sevimlilar", "Избранное", "Favorites"),
    "player.favorite":    ("Sevimli", "В избранном", "Favorite"),
    "player.playlist":    ("Pleylist", "Плейлист", "Playlist"),
    "player.play":        ("O'ynatish", "Воспроизвести", "Play"),
    "player.fav_add":     ("Sevimlilarga qo'shish", "Добавить в избранное",
                           "Add to favorites"),
    "player.fav_remove":  ("Sevimlidan olib tashlash", "Удалить из избранного",
                           "Remove from favorites"),
    "player.mark_pos":    ("Joriy joyni belgilash", "Отметить текущее место",
                           "Bookmark current position"),
    "player.timer_off":   ("O'chirish", "Выключить", "Off"),
    "player.note_title":  ("Eslatma qo'shish", "Добавить заметку", "Add note"),
    "player.note_body":   ("Joriy vaqt: {t}\nIzoh (ixtiyoriy):",
                           "Текущее время: {t}\nЗаметка (необязательно):",
                           "Current time: {t}\nNote (optional):"),
    "player.notes":       ("Eslatmalar", "Заметки", "Notes"),
    "player.no_notes":    ("Hozircha eslatma yo'q", "Заметок пока нет",
                           "No notes yet"),
    "player.goto":        ("O'tish", "Перейти", "Go"),
    "player.clear":       ("Tozalash", "Очистить", "Clear"),
    "player.chapter_fmt": ("{cur} / {total} BOB", "{cur} / {total} гл.",
                           "{cur} / {total} ch."),

    # --- Davomiylik formati ---
    "dur.hour_min": ("{h} soat {m} daqiqa", "{h} ч {m} мин", "{h} h {m} min"),
    "dur.hour":     ("{h} soat",            "{h} ч",         "{h} h"),
    "dur.min":      ("{m} daqiqa",          "{m} мин",       "{m} min"),
    "dur.sec":      ("{s} soniya",          "{s} сек",       "{s} sec"),

    # --- Qulf ekrani (sinov muddati / litsenziya bloki) ---
    "lock.title": ("Dastur vaqtincha ishlamayapti",
                   "Программа временно недоступна",
                   "Service temporarily unavailable"),
    "lock.sub":   ("Iltimos, ma'muriyat bilan bog'laning.",
                   "Пожалуйста, обратитесь к администрации.",
                   "Please contact the administration."),
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
