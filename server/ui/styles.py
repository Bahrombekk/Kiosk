"""ui/styles.py — Umumiy QSS uslublar, ranglar va tur/kengaytma lug'atlari."""
from icons import ICON_DIR

CONTENT_TYPES = ["movie", "cartoon", "music", "book", "audiobook"]
TYPE_LABELS = {
    "movie": "Kino", "cartoon": "Multfilm", "music": "Musiqa",
    "book": "Kitob", "audiobook": "Audiokitob",
}
# Har bir tur uchun badge ranglari: (matn, fon)
TYPE_COLORS = {
    "movie": ("#1D4ED8", "#DBEAFE"),
    "cartoon": ("#7C3AED", "#EDE9FE"),
    "music": ("#047857", "#D1FAE5"),
    "book": ("#B45309", "#FEF3C7"),
    "audiobook": ("#0F766E", "#CCFBF1"),
}

# --- Ranglar (bitta joyda) ---
C_BG = "#F1F5F9"          # sahifa foni
C_SIDEBAR = "#0F172A"     # sidebar foni (to'q)
C_ACCENT = "#2563EB"      # asosiy ko'k
C_TEXT = "#0F172A"
C_MUTED = "#64748B"
C_OK = "#22C55E"
C_BAD = "#EF4444"

_ICONS = ICON_DIR.replace("\\", "/")  # QSS url() uchun

STYLE = f"""
QMainWindow, QDialog {{ background: {C_BG}; }}
QWidget {{ color: {C_TEXT}; font-family: 'Segoe UI', Arial; font-size: 14px; }}
QLabel {{ background: transparent; }}

/* --- Sidebar --- */
QFrame#sidebar {{ background: {C_SIDEBAR}; }}
QLabel#brand {{ color: #FFFFFF; font-size: 17px; font-weight: 800; }}
QLabel#brandSub {{ color: #64748B; font-size: 11px; font-weight: 600; }}
QPushButton#navBtn {{
    background: transparent; color: #94A3B8; border: none; text-align: left;
    padding: 11px 14px; border-radius: 10px; font-weight: 600; font-size: 14px;
}}
QPushButton#navBtn:hover {{ background: #1E293B; color: #E2E8F0; }}
QPushButton#navBtn:checked {{ background: {C_ACCENT}; color: #FFFFFF; }}
QFrame#sideCard {{ background: #1E293B; border-radius: 12px; }}
QLabel#sideStatus {{ color: #E2E8F0; font-size: 12px; font-weight: 600; }}
QLabel#sideAddr {{ color: #94A3B8; font-size: 11px; }}

/* --- Sahifa sarlavhalari --- */
QLabel#pageTitle {{ font-size: 22px; font-weight: 800; }}
QLabel#pageSub {{ color: {C_MUTED}; font-size: 13px; }}
QLabel#cardTitle {{ font-weight: 700; font-size: 15px; }}
QLabel#muted {{ color: {C_MUTED}; }}
QLabel#hint {{ color: #94A3B8; font-size: 12px; }}
QLabel#fieldLbl {{ color: #334155; font-size: 13px; font-weight: 600; }}
QLabel#secTitle {{ font-size: 15px; font-weight: 800; }}
QLabel#secSub {{ color: #94A3B8; font-size: 12px; }}

/* Shaffof scroll-konteyner (sahifa tarkibi uchun — fon sahifaniki qoladi) */
QScrollArea#plainScroll {{ background: transparent; border: none; }}
QScrollArea#plainScroll > QWidget > QWidget {{ background: transparent; }}
QLabel#bigNum {{ font-size: 30px; font-weight: 800; color: {C_TEXT}; }}

/* --- Tugmalar --- */
QPushButton {{
    background: {C_ACCENT}; color: #FFFFFF; border: none;
    padding: 9px 18px; border-radius: 10px; font-weight: 600;
}}
QPushButton:hover {{ background: #1D4ED8; }}
QPushButton:pressed {{ background: #1E40AF; }}
QPushButton:disabled {{ background: #CBD5E1; color: #F8FAFC; }}
QPushButton#ghost {{ background: #FFFFFF; color: #334155; border: 1px solid #E2E8F0; }}
QPushButton#ghost:hover {{ background: #F8FAFC; border-color: #CBD5E1; }}
QPushButton#ghost:pressed {{ background: #F1F5F9; }}
QPushButton#danger {{ background: #FFFFFF; color: {C_BAD}; border: 1px solid #FECACA; }}
QPushButton#danger:hover {{ background: #FEF2F2; border-color: #FCA5A5; }}
QPushButton#danger:pressed {{ background: #FEE2E2; }}

/* --- Kiritish maydonlari --- */
/* MUHIM: QPlainTextEdit QTextEdit'dan meros olmaydi — selektorda alohida
   yozilmasa tizimning qora rejim ranglarida qoladi. */
QLineEdit, QComboBox, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {{
    background: #FFFFFF; color: {C_TEXT};
    border: 1px solid #E2E8F0; border-radius: 10px;
    padding: 9px 12px; selection-background-color: {C_ACCENT};
    selection-color: #FFFFFF;
}}
QLineEdit:hover, QComboBox:hover, QTextEdit:hover,
QPlainTextEdit:hover {{ border-color: #CBD5E1; }}
QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QPlainTextEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus {{ border: 1px solid {C_ACCENT}; }}

/* ComboBox — zamonaviy chevron strelka va ochiladigan ro'yxat */
QComboBox {{ padding-right: 30px; }}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox::down-arrow {{
    image: url({_ICONS}/chevron-down.svg); width: 14px; height: 14px;
}}
QComboBox QAbstractItemView {{
    background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px;
    padding: 4px; outline: none;
    selection-background-color: #EFF6FF; selection-color: {C_TEXT};
}}

/* SpinBox — eski tizim strelkalari o'rniga chevron tugmalar */
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin: border; subcontrol-position: top right;
    width: 28px; border: none; border-left: 1px solid #E2E8F0;
    border-top-right-radius: 10px; background: #F8FAFC;
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border; subcontrol-position: bottom right;
    width: 28px; border: none; border-left: 1px solid #E2E8F0;
    border-bottom-right-radius: 10px; background: #F8FAFC;
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{
    background: #EFF6FF;
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: url({_ICONS}/chevron-up.svg); width: 12px; height: 12px;
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: url({_ICONS}/chevron-down.svg); width: 12px; height: 12px;
}}

/* Checkbox — yumaloq burchakli indikator, belgilanganda accent + check */
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{
    width: 18px; height: 18px; border-radius: 6px;
    border: 2px solid #CBD5E1; background: #FFFFFF;
}}
QCheckBox::indicator:hover {{ border-color: #94A3B8; }}
QCheckBox::indicator:checked {{
    background: {C_ACCENT}; border-color: {C_ACCENT};
    image: url({_ICONS}/check.svg);
}}

/* Tur tablari (Kontent sahifasi) — pill segmentlar, faoli accent */
QPushButton#typeTab {{
    background: #FFFFFF; color: #64748B; border: 1px solid #E2E8F0;
    border-radius: 17px; padding: 7px 16px; font-weight: 600;
}}
QPushButton#typeTab:hover {{ border-color: #CBD5E1; color: #334155; }}
QPushButton#typeTab:checked {{
    background: {C_ACCENT}; color: #FFFFFF; border-color: {C_ACCENT};
}}

QFrame#card {{ background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 16px; }}

/* --- Kontent kartochkasi (user ilovadagi videolar ko'rinishi uslubida) --- */
QFrame#contentCard {{
    background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 16px;
}}
QFrame#contentCard:hover {{ border-color: #93C5FD; background: #FDFEFF; }}
QLabel#ccTitle {{ font-weight: 700; font-size: 14px; }}
QLabel#ccSub {{ color: {C_MUTED}; font-size: 12px; }}
QLabel#ccWarn {{ color: #B91C1C; font-size: 11px; font-weight: 600; }}
QPushButton#iconBtn {{
    background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px;
    padding: 5px;
}}
QPushButton#iconBtn:hover {{ background: #EFF6FF; border-color: #93C5FD; }}
QPushButton#iconBtnDanger {{
    background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px;
    padding: 5px;
}}
QPushButton#iconBtnDanger:hover {{ background: #FEF2F2; border-color: #FCA5A5; }}

/* --- Jadval --- */
QTableWidget {{
    background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 14px;
    alternate-background-color: #FAFBFD;
}}
QHeaderView {{ background: transparent; }}
QHeaderView::section {{
    background: #F8FAFC; color: {C_MUTED}; padding: 12px 10px; border: none;
    border-bottom: 1px solid #E2E8F0; font-weight: 700; font-size: 12px;
}}
QHeaderView::section:first {{ border-top-left-radius: 14px; }}
QHeaderView::section:last {{ border-top-right-radius: 14px; }}
QTableWidget::item {{
    padding-left: 10px; padding-right: 10px;
    border: none; border-bottom: 1px solid #F1F5F9;
}}
QTableWidget::item:selected {{ background: #EFF6FF; color: {C_TEXT}; }}
QTableWidget:focus {{ outline: none; }}

/* Disk indikatori (Boshqaruv -> Kiosklar jadvali) */
QProgressBar {{
    background: #F1F5F9; border: 1px solid #E2E8F0; border-radius: 9px;
    text-align: center; font-size: 11px; font-weight: 600; color: #334155;
    min-height: 18px; max-height: 18px;
}}
QProgressBar::chunk {{ border-radius: 8px; background: #86EFAC; }}

QStatusBar {{ background: #FFFFFF; color: {C_MUTED}; border-top: 1px solid #E2E8F0; }}

/* --- Scrollbar (ingichka, strelkasiz) --- */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{
    background: #CBD5E1; border-radius: 5px; min-height: 40px;
}}
QScrollBar::handle:vertical:hover {{ background: #94A3B8; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{
    background: #CBD5E1; border-radius: 5px; min-width: 40px;
}}
QScrollBar::handle:horizontal:hover {{ background: #94A3B8; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: none; }}

/* --- Dialog/MessageBox tugmalari bir xil ko'rinsin --- */
QMessageBox {{ background: #FFFFFF; }}
QMessageBox QLabel {{ font-size: 14px; }}
QMessageBox QPushButton, QDialogButtonBox QPushButton {{
    min-width: 86px; padding: 8px 18px;
}}

/* --- Muqova preview (kontent dialogi) --- */
QLabel#coverPrev {{
    background: #F8FAFC; border: 1px dashed #CBD5E1; border-radius: 12px;
    color: #94A3B8; font-size: 12px;
}}
QLabel#dropHint {{ color: #94A3B8; font-size: 12px; }}
"""

# Drag&drop va avto-aniqlash uchun fayl kengaytmalari
VIDEO_EXT = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v"}
AUDIO_EXT = {".mp3", ".m4a", ".wav", ".flac", ".ogg", ".aac"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".svg", ".bmp"}
TEXT_EXT = {".json", ".txt", ".epub"}
