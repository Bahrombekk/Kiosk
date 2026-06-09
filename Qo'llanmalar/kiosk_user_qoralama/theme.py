"""
theme.py — Dizayn tokenlari (Figma'dan ajratilgan ranglar).
Butun ilova ranglari SHU YERDAN olinadi. Figma bilan 100% moslash uchun
faqat shu fayldagi qiymatlarni o'zgartirasiz — boshqa joyga tegmaysiz.
"""

# Ranglar Figma eksportidan pixel-sampling orqali olingan.
# Aniq piksel qiymatlar kerak bo'lsa Figma "Inspect" dan tekshirib shu yerda o'zgartiring.
THEMES = {
    "light": {
        "bg":            "#EDF1F4",   # sahifa foni
        "surface":       "#FFFFFF",   # kartochka / nav panel foni
        "surface2":      "#F4F7FA",   # ikkilamchi yuza
        "border":        "#E2E8F0",   # chegara
        "text":          "#1E293B",   # asosiy matn
        "text_secondary":"#64748B",   # ikkilamchi matn
        "accent":        "#2563EB",   # ko'k urg'u (faol element, O'qish tugmasi)
        "accent_text":   "#FFFFFF",   # ko'k ustidagi matn
        "orange":        "#F59E0B",   # Tinglash tugmasi
        "nav_inactive":  "#475569",   # faol bo'lmagan nav ikonka rangi
    },
    "dark": {
        "bg":            "#1E293B",
        "surface":       "#293143",
        "surface2":      "#334155",
        "border":        "#3B475C",
        "text":          "#F1F5F9",
        "text_secondary":"#94A3B8",
        "accent":        "#2563EB",
        "accent_text":   "#FFFFFF",
        "orange":        "#F59E0B",
        "nav_inactive":  "#94A3B8",
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

# Burchak yumaloqligi (px)
RADIUS = {"card": 18, "button": 14, "pill": 28}

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
