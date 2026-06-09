"""
theme.py — Dizayn tokenlari (Figma'dan ajratilgan ranglar va o'lchamlar).
Butun ilova ranglari SHU YERDAN olinadi. Figma bilan 100% moslash uchun
faqat shu fayldagi qiymatlarni o'zgartirasiz — boshqa joyga tegmaysiz (TZ 9-bo'lim).
"""
import os

# Sahifa orqa fon rasmi (oq atlas tekstura — noshaffof, burmalari ko'rinadigan).
# Asl Background.png juda shaffof (alfa~24%) edi; och fon ustiga bakelangan.
BG_IMAGE = os.path.join(os.path.dirname(__file__), "images",
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

# Navigatsiya bo'limlari: (kalit, ko'rinadigan nom, ikonka fayli, sarlavha)
NAV_ITEMS = [
    ("home",   "Asosiy",   "home.svg",  ""),
    ("map",    "Xarita",   "map.svg",   "XARITA"),
    ("videos", "Videolar", "video.svg", "VIDEOLAR"),
    ("books",  "Kitoblar", "book.svg",  "KITOBLAR"),
    ("sites",  "Saytlar",  "globe.svg", "SAYTLAR"),
]
