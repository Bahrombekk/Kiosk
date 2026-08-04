"""
theme.py — Dizayn tokenlari (Figma'dan ajratilgan ranglar va o'lchamlar).
Butun ilova ranglari SHU YERDAN olinadi. Figma bilan 100% moslash uchun
faqat shu fayldagi qiymatlarni o'zgartirasiz — boshqa joyga tegmaysiz (TZ 9-bo'lim).
"""
import os

# Sahifa orqa fon rasmi (oq atlas tekstura — noshaffof, burmalari ko'rinadigan).
# Asl Background.png juda shaffof (alfa~24%) edi; och fon ustiga bakelangan.
BG_IMAGE = os.path.join(os.path.dirname(__file__), "..", "images",
                        "bg_satin.png").replace("\\", "/")

# Ranglar Figma eksportidan pixel-sampling orqali olingan.
# Aniq piksel qiymatlar kerak bo'lsa Figma "Inspect" dan tekshirib shu yerda o'zgartiring.
THEMES = {
    "light": {
        "bg":            "#E9EDF3",   # sahifa foni (Figma och gradient o'rtasi)
        "surface":       "#FFFFFF",   # kartochka / nav panel foni
        "surface2":      "#EFF4FB",   # ikkilamchi yuza / ikonka plitka foni
        "border":        "#E2E8F0",   # chegara
        "text":          "#20242E",   # asosiy matn (Figma)
        "text_secondary":"#7C8595",   # ikkilamchi matn (Figma)
        "accent":        "#2F68F4",   # ko'k urg'u (Figma — faol nav, O'qish)
        "accent_text":   "#FFFFFF",   # ko'k ustidagi matn
        "orange":        "#F59E0B",   # Tinglash tugmasi
        "nav_inactive":  "#1C2333",   # faol bo'lmagan nav ikonka rangi (to'q)
        "danger":        "#EF4444",   # xato / uzilish
        "ok":            "#22C55E",   # ulanish bor
        "scroll":        "rgba(32,36,46,0.28)",   # scrollbar dastasi
    },
    "dark": {
        "bg":            "#1E293B",
        "surface":       "#293143",
        "surface2":      "#334155",
        "border":        "#3B475C",
        "text":          "#F1F5F9",
        "text_secondary":"#94A3B8",
        "accent":        "#3B82F6",
        "accent_text":   "#FFFFFF",
        "orange":        "#F59E0B",
        "nav_inactive":  "#94A3B8",
        "danger":        "#F87171",
        "ok":            "#4ADE80",
        "scroll":        "rgba(148,163,184,0.38)",
    },
}

# Shrift (Figma sans-serif). "Inter" tavsiya etiladi; bo'lmasa tizim shrifti.
FONT_FAMILY = "Inter, 'Segoe UI', Arial, sans-serif"

# Shrift o'lchamlari (px)
FONT = {
    "title":      40,   # bo'lim sarlavhasi (XARITA, VIDEOLAR)
    "h2":         28,   # blok sarlavhasi (Tavsiya etamiz)
    "card_title": 22,   # kontent nomi
    "body":       16,   # asosiy matn
    "small":      14,   # janr, muallif
    "nav":        18,   # navigatsiya matni
    "clock":      30,   # soat
}

# Burchak yumaloqligi (px) — Figma: kartalar 26
RADIUS = {"card": 26, "button": 16, "pill": 32}

# Bo'shliqlar (px)
SPACE = {"page": 24, "gap": 16, "inner": 18}

# ----------------------------------------------------------------------------
# Moslashuvchan o'lcham (responsive scaling).
# Dastur turli monitorlarda ishlaydi (poyezdda kichik ham, katta ham bo'lishi
# mumkin). Barcha o'lchamlar 1920x1080 "bazaviy dizayn" uchun yozilgan; ishga
# tushganda haqiqiy ekran o'lchamiga qarab SCALE hisoblanadi va shu yagona
# koeffitsient orqali shrift/bo'shliq/o'lchamlar kichik yoki katta qilinadi —
# nisbatlar saqlanib qoladi. Qat'iy piksel yozilgan joylarda T.s(px) ishlating.
# ----------------------------------------------------------------------------
DESIGN_W, DESIGN_H = 1920, 1080
SCALE = 1.0
_BASE = None   # (FONT, SPACE, RADIUS) ning asl nusxasi — qayta hisoblash uchun


def s(px):
    """Bazaviy pikselni joriy ekran SCALE'iga moslab qaytaradi (butun son)."""
    return max(1, round(px * SCALE))


def init_scale(size, lo=0.8, hi=1.7):
    """Ekran o'lchamiga qarab global SCALE'ni o'rnatadi va FONT/SPACE/RADIUS
    lug'atlarini joyida qayta hisoblaydi. UI qurilmasdan OLDIN chaqirilishi shart
    (main.py). `size` — QSize (ekran o'lchami)."""
    global SCALE, _BASE
    if _BASE is None:
        _BASE = ({**FONT}, {**SPACE}, {**RADIUS})
    bf, bs, br = _BASE
    sc = min(size.width() / DESIGN_W, size.height() / DESIGN_H)
    SCALE = max(lo, min(hi, sc))
    FONT.update({k: max(1, round(v * SCALE)) for k, v in bf.items()})
    SPACE.update({k: max(1, round(v * SCALE)) for k, v in bs.items()})
    RADIUS.update({k: max(1, round(v * SCALE)) for k, v in br.items()})

# Navigatsiya bo'limlari: (kalit, ikonka fayli). Yorliq/sarlavha matnlari
# i18n.tr(f"nav.{kalit}") va tr(f"title.{kalit}") dan olinadi (3 til).
NAV_ITEMS = [
    ("home",   "home.svg"),
    ("map",    "map.svg"),
    ("videos", "video.svg"),
    ("books",  "book.svg"),
    ("sites",  "globe.svg"),
]


# --- Sensorbop ingichka scrollbar (barcha QScrollArea'larga qo'shiladi) ---
def scrollbar_qss(c):
    """Ingichka, strelkasiz, yumaloq scrollbar QSS (mavzu ranglariga mos)."""
    w, r = s(8), s(4)
    handle = c.get("scroll", "rgba(32,36,46,0.28)")
    return (
        f" QScrollBar:vertical {{ background: transparent; width: {w}px;"
        f"  margin: {s(4)}px {s(2)}px {s(4)}px 0; }}"
        f" QScrollBar::handle:vertical {{ background: {handle};"
        f"  border-radius: {r}px; min-height: {s(56)}px; }}"
        f" QScrollBar::handle:vertical:pressed {{ background: {c['accent']}; }}"
        f" QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical"
        f"  {{ height: 0; background: none; border: none; }}"
        f" QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical"
        f"  {{ background: none; }}"
        f" QScrollBar:horizontal {{ background: transparent; height: {w}px;"
        f"  margin: 0 {s(4)}px {s(2)}px {s(4)}px; }}"
        f" QScrollBar::handle:horizontal {{ background: {handle};"
        f"  border-radius: {r}px; min-width: {s(56)}px; }}"
        f" QScrollBar::handle:horizontal:pressed {{ background: {c['accent']}; }}"
        f" QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal"
        f"  {{ width: 0; background: none; border: none; }}"
        f" QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal"
        f"  {{ background: none; }}")


