"""
emergency.py — Favqulodda ma'lumot modali (SOS).

Navbar'dagi qizil SOS tugmasidan ochiladi: favqulodda xizmat raqamlari,
kioskning joylashuvi (admin Sozlamalar -> "Kiosk joylashuvi") va qisqa
ko'rsatma. Raqamlar ro'yxatini admin panel (Sozlamalar -> "Favqulodda
raqamlar", har qatorda "RAQAM - Tavsif") orqali o'zgartirish mumkin; bo'sh
qoldirilsa standart 112/101/102/103 ro'yxati joriy interfeys tilida
ko'rsatiladi. Ma'lumot to'liq oflayn (settings keshidan o'qiladi).
"""
import math

from PyQt6.QtWidgets import (QLabel, QFrame, QHBoxLayout, QVBoxLayout,
                             QGridLayout)
from PyQt6.QtCore import Qt

from core import cache
from core import theme as T
from core.i18n import tr
from widgets.modal import Modal
from widgets.icons import svg_pixmap

# Standart ro'yxat: (raqam, tr-kalit) — admin o'zgartirmagan bo'lsa shu chiqadi.
# Raqamlar O'zbekiston bo'ylab yagona, tarjima shart emas.
DEFAULT_NUMBERS = (
    ("112", "sos.unified"),
    ("101", "sos.fire"),
    ("102", "sos.police"),
    ("103", "sos.ambulance"),
)

# "RAQAM - Tavsif" qatoridagi ajratgichlar (raqam ichidagi '-' ga tegmaslik
# uchun chiziqcha faqat ikki tomoni bo'shliq bilan qabul qilinadi).
_SEPARATORS = (" - ", " — ", " – ", "|", ":")


def _rgba(hex_color, alpha):
    """'#RRGGBB' -> 'rgba(r,g,b,a)' — QSS uchun yumshoq (tint) rang."""
    h = hex_color.lstrip("#")
    return (f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},"
            f"{int(h[4:6], 16)},{alpha})")


def _settings():
    """Server sozlamalari (oflayn keshdan ham o'qiladi)."""
    hit = cache.load_json("settings")
    return (hit[0] or {}) if hit else {}


def sos_enabled():
    """SOS tugmasi ko'rsatilsinmi? Admin Sozlamalar -> "SOS tugmasi" dan
    o'chirib qo'ygan bo'lsa False — navbar'da tugma umuman chiqmaydi."""
    return (_settings().get("sos_enabled") or "0") != "0"


def _numbers():
    """Admin kiritgan qatorlar; birortasi ham bo'lmasa — standart ro'yxat."""
    items = []
    for line in (_settings().get("sos_numbers") or "").splitlines():
        line = line.strip()
        if not line:
            continue
        for sep in _SEPARATORS:
            if sep in line:
                num, _, desc = line.partition(sep)
                break
        else:
            num, _, desc = line.partition(" ")
        if num.strip() and desc.strip():
            items.append((num.strip(), desc.strip()))
    return items or [(num, tr(key)) for num, key in DEFAULT_NUMBERS]


class EmergencyModal(Modal):
    def __init__(self, parent, theme_name):
        nums = _numbers()
        loc = (_settings().get("kiosk_location") or "").strip()
        rows = math.ceil(len(nums) / 2)
        card_h, gap = T.s(128), T.s(14)
        grid_h = rows * card_h + (rows - 1) * gap
        # Balandlik tarkibdan aniq hisoblanadi (sarlavha bloki ~252px) —
        # pastda ortiqcha bo'sh joy qolmasin; uzun ro'yxatda ekrandan oshmasin.
        height = min(T.s(252) + grid_h + (T.s(64) if loc else 0), T.s(980))
        super().__init__(parent, width=T.s(660), height=height)
        c = T.THEMES[theme_name]
        soft = _rgba(c["danger"], 0.10)    # yumshoq qizil fon
        edge = _rgba(c["danger"], 0.22)    # karta chegarasi

        # --- Sarlavha: dumaloq qizil belgida telefon + matn ---
        # MUHIM: radius = aynan o'lchamning yarmi (T.s yaxlitlashida yarmidan
        # 1px oshsa Qt yumaloqlashni o'chirib kvadrat chizadi).
        bsz = T.s(76)
        badge = QLabel()
        badge.setFixedSize(bsz, bsz)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setPixmap(svg_pixmap("phone", c["danger"], T.s(36)))
        badge.setStyleSheet(
            f"background: {soft}; border-radius: {bsz // 2}px;")
        brow = QHBoxLayout()
        brow.addStretch(1)
        brow.addWidget(badge)
        brow.addStretch(1)
        self.content.addLayout(brow)
        self.content.addSpacing(T.s(10))

        title = QLabel(tr("sos.title"))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"color: {c['danger']}; background: transparent;"
            f" font-size: {T.s(30)}px; font-weight: 800;")
        self.content.addWidget(title)
        self.content.addSpacing(T.s(16))

        # --- Raqamlar: 2 ustunli katta kartalar (sensorga qulay) ---
        grid = QGridLayout()
        grid.setSpacing(gap)
        for i, (num, desc) in enumerate(nums):
            card = QFrame()
            card.setStyleSheet(
                f"background: {c['surface2']};"
                f" border: 1px solid {edge};"
                f" border-radius: {T.s(18)}px;")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(T.s(14), T.s(16), T.s(14), T.s(16))
            cl.setSpacing(T.s(6))
            n = QLabel(num)
            n.setAlignment(Qt.AlignmentFlag.AlignCenter)
            n.setStyleSheet(
                f"color: {c['danger']}; background: transparent;"
                f" border: none; font-size: {T.s(38)}px; font-weight: 800;")
            d = QLabel(desc)
            d.setWordWrap(True)
            d.setAlignment(Qt.AlignmentFlag.AlignCenter)
            d.setStyleSheet(
                f"color: {c['text']}; background: transparent;"
                f" border: none; font-size: {T.s(17)}px; font-weight: 600;")
            cl.addStretch(1)
            cl.addWidget(n)
            cl.addWidget(d)
            cl.addStretch(1)
            card.setFixedHeight(card_h)
            r, col = divmod(i, 2)
            if i == len(nums) - 1 and len(nums) % 2:
                grid.addWidget(card, r, 0, 1, 2)   # toq qolgan oxirgisi — keng
            else:
                grid.addWidget(card, r, col)
        self.content.addLayout(grid)

        # --- Joylashuv (admin kiritgan bo'lsa) — dispetcherga aytish uchun ---
        if loc:
            pill = QFrame()
            pill.setStyleSheet(
                f"background: {soft}; border-radius: {T.s(24)}px;")
            pl = QHBoxLayout(pill)
            pl.setContentsMargins(T.s(18), T.s(11), T.s(18), T.s(11))
            pl.setSpacing(T.s(10))
            pin = QLabel()
            pin.setPixmap(svg_pixmap("map-pin", c["danger"], T.s(22)))
            pin.setStyleSheet("background: transparent;")
            txt = QLabel(tr("sos.location", loc=loc))
            txt.setWordWrap(True)
            txt.setStyleSheet(
                f"color: {c['text']}; background: transparent;"
                f" font-size: {T.s(17)}px; font-weight: 700;")
            pl.addStretch(1)
            pl.addWidget(pin)
            pl.addWidget(txt)
            pl.addStretch(1)
            self.content.addSpacing(T.s(14))
            self.content.addWidget(pill)

        hint = QLabel(tr("sos.hint"))
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet(
            f"color: {c['text_secondary']}; background: transparent;"
            f" font-size: {T.s(15)}px;")
        self.content.addSpacing(T.s(10))
        self.content.addWidget(hint)
        self.content.addStretch(1)
