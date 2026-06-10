"""
admin.py — Server (admin) DESKTOP oynasi (PyQt6).

Bu — server qismining yuzi. Ishga tushganda:
  - ichida FastAPI backendni (uvicorn) alohida oqimda ishga tushiradi,
  - admin'ga kontentni boshqarish (qo'shish/o'chirish), sozlamalar va
    server holatini ko'rsatadi.

Ya'ni `server.exe` = shu fayl. Foydalanuvchiga faqat desktop oyna ko'rinadi,
backend ichkarida ishlaydi (TZ 4.2 — admin interfeysi PyQt6 oyna).

Dizayn: chap tomonda doimiy sidebar (bo'limlar, ikonkalar bilan), o'ng tomonda
sahifalar (QStackedWidget). Hamma belgilar — haqiqiy SVG ikonkalar (Lucide).

Ishga tushirish:
  pip install -r requirements.txt
  python admin.py
"""
import os
import sys
import time
import socket
import shutil
import logging
from datetime import datetime

import uvicorn
from PyQt6.QtWidgets import (
    QApplication, QWidget, QMainWindow, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QFormLayout, QLineEdit, QComboBox, QTextEdit, QCheckBox, QDialog,
    QFileDialog, QMessageBox, QDialogButtonBox, QSpinBox, QDoubleSpinBox,
    QFrame, QStackedWidget, QButtonGroup
)
from PyQt6.QtCore import Qt, QThread, QTimer, QSize
from PyQt6.QtGui import QPixmap

import config
import db
import ws
from icons import svg_icon, svg_pixmap

CONTENT_TYPES = ["movie", "cartoon", "music", "book", "audiobook"]
TYPE_LABELS = {
    "movie": "Kino", "cartoon": "Multfilm", "music": "Musiqa",
    "book": "Kitob", "audiobook": "Audiokitob",
}

# --- Ranglar (bitta joyda) ---
C_BG = "#F1F5F9"          # sahifa foni
C_SIDEBAR = "#0F172A"     # sidebar foni (to'q)
C_ACCENT = "#2563EB"      # asosiy ko'k
C_TEXT = "#0F172A"
C_MUTED = "#64748B"
C_OK = "#22C55E"
C_BAD = "#EF4444"

STYLE = f"""
QMainWindow, QDialog {{ background: {C_BG}; }}
QWidget {{ color: {C_TEXT}; font-family: 'Segoe UI', Arial; font-size: 14px; }}
QLabel {{ background: transparent; }}

/* --- Sidebar --- */
QFrame#sidebar {{ background: {C_SIDEBAR}; }}
QLabel#brand {{ color: #FFFFFF; font-size: 17px; font-weight: 800; }}
QLabel#brandSub {{ color: #475569; font-size: 11px; font-weight: 600; }}
QPushButton#navBtn {{
    background: transparent; color: #94A3B8; border: none; text-align: left;
    padding: 11px 14px; border-radius: 10px; font-weight: 600; font-size: 14px;
}}
QPushButton#navBtn:hover {{ background: #1E293B; color: #E2E8F0; }}
QPushButton#navBtn:checked {{ background: {C_ACCENT}; color: #FFFFFF; }}
QLabel#sideStatus {{ color: #94A3B8; font-size: 12px; font-weight: 600; }}

/* --- Sahifa sarlavhalari --- */
QLabel#pageTitle {{ font-size: 21px; font-weight: 800; }}
QLabel#pageSub {{ color: {C_MUTED}; font-size: 13px; }}
QLabel#cardTitle {{ font-weight: 700; font-size: 15px; }}
QLabel#muted {{ color: {C_MUTED}; }}
QLabel#hint {{ color: #94A3B8; font-size: 12px; }}
QLabel#bigNum {{ font-size: 34px; font-weight: 800; color: {C_ACCENT}; }}

/* --- Tugmalar --- */
QPushButton {{
    background: {C_ACCENT}; color: #FFFFFF; border: none;
    padding: 9px 16px; border-radius: 9px; font-weight: 600;
}}
QPushButton:hover {{ background: #1D4ED8; }}
QPushButton:pressed {{ background: #1E40AF; }}
QPushButton#ghost {{ background: #FFFFFF; color: #334155; border: 1px solid #CBD5E1; }}
QPushButton#ghost:hover {{ background: #F1F5F9; }}
QPushButton#danger {{ background: {C_BAD}; }}
QPushButton#danger:hover {{ background: #DC2626; }}

/* --- Kiritish maydonlari --- */
QLineEdit, QComboBox, QTextEdit, QSpinBox, QDoubleSpinBox {{
    background: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 9px;
    padding: 8px 10px; selection-background-color: {C_ACCENT};
    selection-color: #FFFFFF;
}}
QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QSpinBox:focus,
QDoubleSpinBox:focus {{ border: 1px solid {C_ACCENT}; }}

QFrame#card {{ background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 16px; }}

/* --- Jadval --- */
QTableWidget {{
    background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 14px;
    gridline-color: #EEF2F6;
}}
QHeaderView::section {{
    background: #F8FAFC; color: {C_MUTED}; padding: 11px 10px; border: none;
    border-bottom: 1px solid #E2E8F0; font-weight: 600;
}}
QTableWidget::item {{ padding: 8px 6px; border-bottom: 1px solid #F1F5F9; }}
QTableWidget::item:selected {{ background: #EFF6FF; color: {C_TEXT}; }}
QTableWidget:focus {{ outline: none; }}

QStatusBar {{ background: #FFFFFF; color: {C_MUTED}; border-top: 1px solid #E2E8F0; }}

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


def _media_duration(path):
    """Media fayl davomiyligini (soniya) o'qiydi. ffprobe -> cv2 -> None."""
    try:
        import subprocess
        import json as _json
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        out = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "json", path],
            capture_output=True, text=True, timeout=20, creationflags=flags)
        dur = _json.loads(out.stdout or "{}").get("format", {}).get("duration")
        if dur:
            return int(round(float(dur)))
    except Exception:
        pass
    try:
        import cv2
        cap = cv2.VideoCapture(path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        cap.release()
        if fps and frames:
            return int(round(frames / fps))
    except Exception:
        pass
    return None


def _title_from_filename(path):
    """Fayl nomidan toza sarlavha hosil qiladi (kengaytmasiz, _ va - -> bo'sh joy)."""
    base = os.path.splitext(os.path.basename(path))[0]
    return base.replace("_", " ").replace("-", " ").strip()


def _fmt_uptime(secs):
    """Soniyalarni odam o'qiydigan ko'rinishga ('2s 14m' kabi) aylantiradi."""
    secs = int(secs)
    if secs < 60:
        return f"{secs} soniya"
    m, s = divmod(secs, 60)
    if m < 60:
        return f"{m} daq {s} son"
    h, m = divmod(m, 60)
    return f"{h} soat {m} daq"


def port_in_use(port, host="127.0.0.1"):
    """Port allaqachon band emasmi? (oldingi server nusxasi ishlayotgan bo'lishi mumkin)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def local_ips():
    """Tarmoqdagi mahalliy IP manzillarni qaytaradi (user qurilmalar shunga ulanadi)."""
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except socket.gaierror:
        pass
    ips.discard("127.0.0.1")
    return sorted(ips) or ["127.0.0.1"]


class ServerThread(QThread):
    """FastAPI backendni (uvicorn) alohida oqimda ishga tushiradi."""

    def __init__(self):
        super().__init__()
        cfg = uvicorn.Config("main:app", host=config.HOST, port=config.PORT,
                             log_level="warning")
        self.server = uvicorn.Server(cfg)
        # Asosiy oqimda emasligi uchun signal handlerlarni o'chiramiz
        self.server.install_signal_handlers = lambda: None

    def run(self):
        self.server.run()

    def stop(self):
        self.server.should_exit = True


# ----------------------------------------------------------------------------
#  Kontent qo'shish/tahrirlash dialogi
# ----------------------------------------------------------------------------
class ContentDialog(QDialog):
    def __init__(self, parent=None, item=None):
        super().__init__(parent)
        self.item = item or {}
        self.media_src = None   # tanlangan media fayl yo'li
        self.cover_src = None   # tanlangan muqova rasmi
        self.text_src = None    # tanlangan kitob matni (json/txt)
        self.setWindowTitle("Kontentni tahrirlash" if item else "Yangi kontent qo'shish")
        self.setMinimumWidth(640)
        self.setAcceptDrops(True)   # fayllarni tortib tashlash mumkin
        self._build()
        self._on_type_changed()
        self._update_cover_preview(self.item.get("cover_path"))

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(12)

        # Tepa: chapda forma, o'ngda muqova preview
        top = QHBoxLayout()
        top.setSpacing(18)
        form = QFormLayout()
        form.setSpacing(10)
        self.form = form

        self.type = QComboBox()
        for t in CONTENT_TYPES:
            self.type.addItem(TYPE_LABELS[t], t)
        if self.item.get("type"):
            self.type.setCurrentIndex(CONTENT_TYPES.index(self.item["type"]))
        self.type.currentIndexChanged.connect(self._on_type_changed)

        self.title = QLineEdit(self.item.get("title", ""))
        self.author = QLineEdit(self.item.get("author") or "")
        self.genre = QLineEdit(self.item.get("genre") or "")
        self.tab = QLineEdit(self.item.get("category_tab") or "")
        self.tab.setPlaceholderText("Masalan: Kinolar, Badiiy, Bolalarga...")
        self.desc = QTextEdit(self.item.get("description") or "")
        self.desc.setFixedHeight(80)

        self.duration = QSpinBox()
        self.duration.setRange(0, 10_000_000)
        self.duration.setValue(self.item.get("duration") or 0)
        self.duration.setSuffix(" soniya")

        self.pages = QSpinBox()
        self.pages.setRange(0, 100000)
        self.pages.setValue(self.item.get("pages") or 0)
        self.pages.setSuffix(" sahifa")

        self.recommended = QCheckBox("Tavsiya blokida ko'rsatilsin")
        self.recommended.setChecked(bool(self.item.get("is_recommended")))

        form.addRow("Turi:", self.type)
        form.addRow("Nomi:", self.title)
        form.addRow("Muallif:", self.author)
        form.addRow("Janr:", self.genre)
        form.addRow("Tab (kategoriya):", self.tab)
        form.addRow("Tavsif:", self.desc)
        form.addRow("Davomiylik:", self.duration)
        form.addRow("Sahifalar:", self.pages)

        # Fayl tanlash qatorlari (har biri alohida widget — turga qarab yashiriladi)
        self.file_label, self.media_widget = self._pick_row(
            self.item.get("file_path"), "video",
            "Media (*.mp4 *.mkv *.avi *.mp3 *.m4a *.wav);; Barcha fayllar (*.*)",
            "media")
        self.cover_label, self.cover_widget = self._pick_row(
            self.item.get("cover_path"), "image",
            "Rasm (*.jpg *.jpeg *.png *.webp *.svg);; Barcha fayllar (*.*)",
            "cover")
        self.text_label, self.text_widget = self._pick_row(
            self.item.get("text_path"), "file-text",
            "Kitob matni (*.json *.txt);; Barcha fayllar (*.*)",
            "text")
        form.addRow("Media fayl:", self.media_widget)
        form.addRow("Muqova rasmi:", self.cover_widget)
        form.addRow("Kitob matni:", self.text_widget)
        form.addRow("", self.recommended)
        top.addLayout(form, 1)

        # Muqova preview (o'ngda)
        prev_col = QVBoxLayout()
        prev_col.setSpacing(6)
        self.cover_preview = QLabel("Muqova\nyo'q")
        self.cover_preview.setObjectName("coverPrev")
        self.cover_preview.setFixedSize(160, 214)
        self.cover_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        prev_col.addWidget(self.cover_preview)
        prev_col.addStretch(1)
        top.addLayout(prev_col)
        lay.addLayout(top)

        drop = QLabel("Maslahat: media, rasm yoki matn faylini shu oynaga tortib "
                      "tashlasangiz — turi avtomatik aniqlanadi (davomiylik ham).")
        drop.setObjectName("dropHint")
        drop.setWordWrap(True)
        lay.addWidget(drop)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _on_type_changed(self):
        """Turga qarab faqat mos maydonlarni ko'rsatadi (ortiqcha ish bo'lmasin)."""
        t = self.type.currentData()
        has_dur = t in ("movie", "cartoon", "music", "audiobook")
        has_media = t in ("movie", "cartoon", "music", "audiobook")
        has_pages = t == "book"
        has_text = t in ("book", "audiobook")
        self.form.setRowVisible(self.duration, has_dur)
        self.form.setRowVisible(self.pages, has_pages)
        self.form.setRowVisible(self.media_widget, has_media)
        self.form.setRowVisible(self.text_widget, has_text)

    def _pick_row(self, current, icon_name, file_filter, kind):
        """'Fayl nomi + Tanlash...' qatorini yasaydi; (label, widget) qaytaradi."""
        cont = QWidget()
        row = QHBoxLayout(cont)
        row.setContentsMargins(0, 0, 0, 0)
        label = QLabel(current or "Tanlanmagan")
        label.setObjectName("muted" if current else "hint")
        pick = QPushButton(" Tanlash...")
        pick.setObjectName("ghost")
        pick.setIcon(svg_icon(icon_name, "#334155", 32))
        pick.setIconSize(QSize(16, 16))
        pick.clicked.connect(lambda: self._pick_file(kind, file_filter))
        row.addWidget(label, 1)
        row.addWidget(pick)
        cont._label = label
        return label, cont

    def _pick_file(self, kind, file_filter):
        path, _ = QFileDialog.getOpenFileName(self, "Fayl tanlash", "", file_filter)
        if path:
            self._set_file(kind, path)

    def _set_file(self, kind, path):
        """Tanlangan/tashlangan faylni biriktiradi va aqlli to'ldirishni bajaradi."""
        setattr(self, kind + "_src", path)
        label = {"media": self.file_label, "cover": self.cover_label,
                 "text": self.text_label}[kind]
        label.setText(os.path.basename(path))
        label.setStyleSheet("color: #0F172A;")
        if kind == "media":
            if not self.title.text().strip():
                self.title.setText(_title_from_filename(path))
            dur = _media_duration(path)
            if dur:
                self.duration.setValue(dur)
        elif kind == "cover":
            self._update_cover_preview(path)

    def _update_cover_preview(self, src):
        """Muqova rasmini preview maydonida ko'rsatadi (fayl yo'li yoki nomi)."""
        if not src:
            self.cover_preview.setPixmap(QPixmap())
            self.cover_preview.setText("Muqova\nyo'q")
            return
        path = src if os.path.isabs(src) else os.path.join(config.COVERS_DIR, src)
        pm = QPixmap(path)
        if pm.isNull():
            self.cover_preview.setPixmap(QPixmap())
            self.cover_preview.setText("Muqova\nko'rinmadi")
            return
        self.cover_preview.setText("")
        self.cover_preview.setPixmap(pm.scaled(
            self.cover_preview.size(), Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))

    # --- Drag & drop ---
    def _route_kind(self, path):
        ext = os.path.splitext(path)[1].lower()
        if ext in VIDEO_EXT or ext in AUDIO_EXT:
            return "media"
        if ext in IMAGE_EXT:
            return "cover"
        if ext in TEXT_EXT:
            return "text"
        return None

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        for url in e.mimeData().urls():
            path = url.toLocalFile()
            if not path:
                continue
            kind = self._route_kind(path)
            if kind:
                self._set_file(kind, path)
        e.acceptProposedAction()

    def _accept(self):
        if not self.title.text().strip():
            QMessageBox.warning(self, "Xato", "Nomi bo'sh bo'lmasligi kerak.")
            return
        self.accept()

    def values(self):
        """Dialogdagi qiymatlarni DB uchun dict qilib qaytaradi."""
        data = {
            "type": self.type.currentData(),
            "title": self.title.text().strip(),
            "author": self.author.text().strip() or None,
            "genre": self.genre.text().strip() or None,
            "category_tab": self.tab.text().strip() or None,
            "description": self.desc.toPlainText().strip() or None,
            "duration": self.duration.value() or None,
            "pages": self.pages.value() or None,
            "is_recommended": 1 if self.recommended.isChecked() else 0,
        }
        # Tanlangan fayllarni content/ ostidagi papkalarga ko'chiramiz
        for src, dst_dir, key in (
                (self.media_src, config.MEDIA_DIR, "file_path"),
                (self.cover_src, config.COVERS_DIR, "cover_path"),
                (self.text_src, config.BOOKS_DIR, "text_path")):
            if src:
                os.makedirs(dst_dir, exist_ok=True)
                dst_name = os.path.basename(src)
                shutil.copy2(src, os.path.join(dst_dir, dst_name))
                data[key] = dst_name
        return data


# ----------------------------------------------------------------------------
#  Umumiy yozuv dialogi (reklama / sayt / bekat uchun)
# ----------------------------------------------------------------------------
class RecordDialog(QDialog):
    """Bitta jadval yozuvini tahrirlash dialogi.

    fields — [(key, label, kind), ...]; kind: text|multiline|int|float|bool.
    Shu bitta dialog reklama, sayt va bekat formalarini ham hosil qiladi
    (har biri uchun alohida sinf yozish shart emas)."""

    def __init__(self, parent, title, fields, item=None):
        super().__init__(parent)
        self.fields = fields
        self.item = item or {}
        self.widgets = {}
        self.setWindowTitle(title)
        self.setMinimumWidth(440)

        lay = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)
        for key, label, kind in fields:
            val = self.item.get(key)
            if kind == "multiline":
                w = QTextEdit("" if val is None else str(val))
                w.setFixedHeight(70)
            elif kind == "int":
                w = QSpinBox()
                w.setRange(0, 1_000_000)
                w.setValue(int(val or 0))
            elif kind == "float":
                w = QDoubleSpinBox()
                w.setRange(-1e9, 1e9)
                w.setDecimals(6)
                w.setValue(float(val) if val is not None else 0.0)
            elif kind == "bool":
                w = QCheckBox("Ha")
                w.setChecked(bool(val) if val is not None else True)
            else:  # text
                w = QLineEdit("" if val is None else str(val))
            self.widgets[key] = (w, kind)
            form.addRow(label + ":", w)
        lay.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def values(self):
        out = {}
        for key, (w, kind) in self.widgets.items():
            if kind == "multiline":
                out[key] = w.toPlainText().strip() or None
            elif kind in ("int", "float"):
                out[key] = w.value()
            elif kind == "bool":
                out[key] = 1 if w.isChecked() else 0
            else:
                out[key] = w.text().strip() or None
        return out


# ----------------------------------------------------------------------------
#  Asosiy admin oynasi
# ----------------------------------------------------------------------------
class AdminWindow(QMainWindow):
    NAV = [
        ("dashboard", "Boshqaruv", "layout-dashboard"),
        ("content", "Kontent", "clapperboard"),
        ("ads", "Reklama", "megaphone"),
        ("sites", "Saytlar", "globe"),
        ("route", "Bekatlar", "train-front"),
        ("settings", "Sozlamalar", "settings"),
    ]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kiosk — Server admin")
        self.setWindowIcon(svg_icon("server", C_ACCENT, 64))
        self.resize(1180, 760)

        self.server = ServerThread()
        self.server.start()

        # Generik CRUD sahifalar holati (reklama/sayt/bekat) shu yerda saqlanadi
        self._crud = {}

        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._sidebar())

        self.pages = QStackedWidget()
        self._page_index = {}
        builders = {
            "dashboard": self._dashboard_page, "content": self._content_page,
            "ads": self._ads_page, "sites": self._sites_page,
            "route": self._route_page, "settings": self._settings_page,
        }
        for key, _label, _icon in self.NAV:
            page = builders[key]()
            self._page_index[key] = self.pages.count()
            self.pages.addWidget(page)
        root.addWidget(self.pages, 1)
        self.setCentralWidget(central)
        self._go("dashboard")
        self.statusBar().showMessage("Server ishga tushirilmoqda...", 3000)

        self.refresh_content()
        self.load_settings()
        self._update_stats()

        # Jonli holat (har soniyada) va statistika (har 5 soniyada)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_status)
        self.timer.start(1000)
        self._update_status()
        self.stats_timer = QTimer(self)
        self.stats_timer.timeout.connect(self._update_stats)
        self.stats_timer.start(5000)

    # ------------------------------------------------------------------
    #  Sidebar
    # ------------------------------------------------------------------
    def _sidebar(self):
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(232)
        lay = QVBoxLayout(side)
        lay.setContentsMargins(14, 18, 14, 16)
        lay.setSpacing(4)

        # Brend (logo + nom)
        brand_row = QHBoxLayout()
        brand_row.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(svg_pixmap("server", "#60A5FA", 28))
        brand_txt = QVBoxLayout()
        brand_txt.setSpacing(0)
        name = QLabel("Kiosk Server")
        name.setObjectName("brand")
        sub = QLabel("Boshqaruv paneli")
        sub.setObjectName("brandSub")
        brand_txt.addWidget(name)
        brand_txt.addWidget(sub)
        brand_row.addWidget(logo)
        brand_row.addLayout(brand_txt)
        brand_row.addStretch(1)
        lay.addLayout(brand_row)
        lay.addSpacing(18)

        # Navigatsiya tugmalari
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self._nav_btns = {}
        for key, label, icon_name in self.NAV:
            b = QPushButton("  " + label)
            b.setObjectName("navBtn")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setIconSize(QSize(19, 19))
            b.clicked.connect(lambda _c, k=key: self._go(k))
            self._nav_btns[key] = (b, icon_name)
            self.nav_group.addButton(b)
            lay.addWidget(b)
        lay.addStretch(1)

        # Pastda: server holati (rangli nuqta + matn) va manzil
        self.side_dot = QLabel()
        self.side_status = QLabel("Server...")
        self.side_status.setObjectName("sideStatus")
        srow = QHBoxLayout()
        srow.setSpacing(8)
        srow.addWidget(self.side_dot)
        srow.addWidget(self.side_status, 1)
        lay.addLayout(srow)
        self.side_addr = QLabel(f"{local_ips()[0]}:{config.PORT}")
        self.side_addr.setObjectName("sideStatus")
        lay.addWidget(self.side_addr)
        return side

    def _go(self, key):
        self.pages.setCurrentIndex(self._page_index.get(key, 0))
        for k, (b, icon_name) in self._nav_btns.items():
            active = (k == key)
            b.setChecked(active)
            b.setIcon(svg_icon(icon_name, "#FFFFFF" if active else "#94A3B8", 38))
        if key == "dashboard" and hasattr(self, "_stat_lbls"):
            self._update_stats()

    # ------------------------------------------------------------------
    #  Umumiy qurilish bloklari
    # ------------------------------------------------------------------
    def _card(self, padding=18):
        card = QFrame()
        card.setObjectName("card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(padding, padding, padding, padding)
        lay.setSpacing(10)
        return card, lay

    def _page(self, title, subtitle):
        """Standart sahifa skeleti: sarlavha + subtitle, keyin tarkib."""
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(26, 22, 26, 20)
        lay.setSpacing(14)
        t = QLabel(title)
        t.setObjectName("pageTitle")
        s = QLabel(subtitle)
        s.setObjectName("pageSub")
        lay.addWidget(t)
        lay.addWidget(s)
        return w, lay

    def _btn(self, text, icon_name, slot, kind=None, icon_color=None):
        b = QPushButton(" " + text)
        if kind:
            b.setObjectName(kind)
        color = icon_color or ("#334155" if kind == "ghost" else "#FFFFFF")
        b.setIcon(svg_icon(icon_name, color, 32))
        b.setIconSize(QSize(16, 16))
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.clicked.connect(slot)
        return b

    @staticmethod
    def _setup_table(table):
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)

    # ------------------------------------------------------------------
    #  Boshqaruv (dashboard) sahifasi
    # ------------------------------------------------------------------
    def _dashboard_page(self):
        w, lay = self._page("Boshqaruv",
                            "Server holati, ulangan kiosklar va e'lonlar")

        # === Statistika kartalari qatori ===
        stats = QHBoxLayout()
        stats.setSpacing(14)
        self._stat_lbls = {}
        for key, label, icon_name in (
                ("kiosks", "Ulangan kiosklar", "monitor"),
                ("content", "Kontentlar", "clapperboard"),
                ("ads", "Reklamalar", "megaphone"),
                ("sites", "Saytlar", "globe")):
            card, clay = self._card(16)
            row = QHBoxLayout()
            row.setSpacing(12)
            ic = QLabel()
            ic.setPixmap(svg_pixmap(icon_name, C_ACCENT, 26))
            num = QLabel("0")
            num.setObjectName("bigNum")
            cap = QLabel(label)
            cap.setObjectName("muted")
            col = QVBoxLayout()
            col.setSpacing(0)
            col.addWidget(num)
            col.addWidget(cap)
            row.addWidget(ic, 0, Qt.AlignmentFlag.AlignTop)
            row.addLayout(col)
            row.addStretch(1)
            clay.addLayout(row)
            stats.addWidget(card, 1)
            self._stat_lbls[key] = num
        lay.addLayout(stats)

        # === Holat + manzil kartasi ===
        stat_card, stat_lay = self._card()
        hrow = QHBoxLayout()
        self.status_dot = QLabel()
        self.status_lbl = QLabel()
        self.status_lbl.setStyleSheet("font-size: 17px; font-weight: 700;")
        hrow.addWidget(self.status_dot)
        hrow.addWidget(self.status_lbl)
        hrow.addStretch(1)
        stat_lay.addLayout(hrow)

        ip0 = local_ips()[0]
        self._server_url = f"http://{ip0}:{config.PORT}"
        arow = QHBoxLayout()
        arow.setSpacing(10)
        addr_ic = QLabel()
        addr_ic.setPixmap(svg_pixmap("wifi", C_MUTED, 16))
        addr = QLabel(self._server_url)
        addr.setObjectName("muted")
        addr.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        copy_btn = self._btn("Nusxalash", "copy", self._copy_addr, kind="ghost")
        arow.addWidget(addr_ic)
        arow.addWidget(addr)
        arow.addWidget(copy_btn)
        arow.addStretch(1)
        stat_lay.addLayout(arow)
        hint = QLabel(f"User qurilmada: KIOSK_SERVER={self._server_url}")
        hint.setObjectName("hint")
        stat_lay.addWidget(hint)
        lay.addWidget(stat_card)

        # === E'lon yuborish kartasi ===
        ann_card, ann_lay = self._card()
        ann_title_row = QHBoxLayout()
        ann_title_row.setSpacing(8)
        ann_ic = QLabel()
        ann_ic.setPixmap(svg_pixmap("megaphone", C_ACCENT, 18))
        ann_title = QLabel("Barcha kiosklarga e'lon")
        ann_title.setObjectName("cardTitle")
        ann_title_row.addWidget(ann_ic)
        ann_title_row.addWidget(ann_title)
        ann_title_row.addStretch(1)
        ann_lay.addLayout(ann_title_row)
        ann_row = QHBoxLayout()
        self.ann_input = QLineEdit()
        self.ann_input.setPlaceholderText(
            "E'lon matnini kiriting... (masalan: Keyingi bekat — Samarqand)")
        self.ann_input.returnPressed.connect(self.send_announcement)
        send = self._btn("Yuborish", "send", self.send_announcement)
        ann_row.addWidget(self.ann_input, 1)
        ann_row.addWidget(send)
        ann_lay.addLayout(ann_row)
        lay.addWidget(ann_card)

        # === Kiosklar jadvali ===
        ktitle = QLabel("Ulangan kiosklar — batafsil")
        ktitle.setObjectName("cardTitle")
        lay.addWidget(ktitle)

        self.kiosk_table = QTableWidget(0, 5)
        self.kiosk_table.setHorizontalHeaderLabels(
            ["Qurilma", "IP manzil", "Tizim", "Ulangan vaqt", "Davomiyligi"])
        kh = self.kiosk_table.horizontalHeader()
        kh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        kh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._setup_table(self.kiosk_table)
        self.kiosk_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        lay.addWidget(self.kiosk_table, 1)

        self.empty_lbl = QLabel("Hozircha hech qaysi kiosk ulanmagan.")
        self.empty_lbl.setStyleSheet("color: #94A3B8; padding: 6px 4px;")
        lay.addWidget(self.empty_lbl)
        return w

    def _copy_addr(self):
        QApplication.clipboard().setText(self._server_url)
        self.statusBar().showMessage("Manzil nusxalandi: " + self._server_url, 3000)

    @staticmethod
    def _dot(label, color, size=10):
        label.setFixedSize(size, size)
        label.setStyleSheet(
            f"background: {color}; border-radius: {size // 2}px;")

    def _update_status(self):
        running = self.server.isRunning() and not self.server.server.should_exit
        if running:
            self.status_lbl.setText("Server ishlayapti")
            self._dot(self.status_dot, C_OK)
            self.side_status.setText("Server ishlayapti")
            self._dot(self.side_dot, C_OK, 8)
        else:
            self.status_lbl.setText("Server to'xtagan")
            self._dot(self.status_dot, C_BAD)
            self.side_status.setText("Server to'xtagan")
            self._dot(self.side_dot, C_BAD, 8)

        clients = ws.manager.clients()
        self._stat_lbls["kiosks"].setText(str(len(clients)))
        self.empty_lbl.setVisible(not clients)

        self.kiosk_table.setRowCount(len(clients))
        mon_icon = svg_icon("monitor", C_MUTED, 32)
        for r, c in enumerate(clients):
            when = ""
            if c.get("connected_at"):
                when = datetime.fromtimestamp(c["connected_at"]).strftime("%H:%M:%S")
            cells = [c["device_id"], c["ip"], c["platform"], when,
                     _fmt_uptime(c["uptime"])]
            for col, val in enumerate(cells):
                item = QTableWidgetItem(val)
                if col == 0:
                    item.setIcon(mon_icon)
                if col in (1, 3, 4):
                    item.setForeground(Qt.GlobalColor.darkGray)
                self.kiosk_table.setItem(r, col, item)

    def _update_stats(self):
        """Dashboard'dagi kontent/reklama/sayt sonlarini yangilaydi."""
        try:
            self._stat_lbls["content"].setText(str(len(db.get_content())))
            self._stat_lbls["ads"].setText(str(len(db.get_ads(active_only=False))))
            self._stat_lbls["sites"].setText(str(len(db.get_sites())))
        except Exception:
            pass  # DB hali tayyor bo'lmasa — keyingi siklda

    def send_announcement(self):
        text = self.ann_input.text().strip()
        if not text:
            return
        ws.manager.broadcast_threadsafe({"type": "announcement", "text": text})
        self.ann_input.clear()
        n = len(ws.manager.clients())
        self.statusBar().showMessage(
            f"E'lon yuborildi ({n} ta kioskka): {text}", 5000)

    # ------------------------------------------------------------------
    #  Kontent sahifasi (qidiruv + tur filtri bilan)
    # ------------------------------------------------------------------
    def _content_page(self):
        w, lay = self._page("Kontent",
                            "Kino, multfilm, musiqa, kitob va audiokitoblar")

        bar = QHBoxLayout()
        bar.setSpacing(8)
        bar.addWidget(self._btn("Qo'shish", "plus", self.add_content))
        bar.addWidget(self._btn("Tahrirlash", "pencil", self.edit_content, "ghost"))
        bar.addWidget(self._btn("O'chirish", "trash-2", self.delete_content, "danger"))
        bar.addWidget(self._btn("Yangilash", "refresh-cw",
                                self.refresh_content, "ghost"))
        bar.addStretch(1)

        # Tur filtri + qidiruv (yozish bilanoq jadval filtlanadi)
        self.type_filter = QComboBox()
        self.type_filter.addItem("Barcha turlar", None)
        for t in CONTENT_TYPES:
            self.type_filter.addItem(TYPE_LABELS[t], t)
        self.type_filter.currentIndexChanged.connect(self.refresh_content)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Qidirish: nomi, muallif, janr...")
        self.search.setClearButtonEnabled(True)
        self.search.addAction(svg_icon("search", C_MUTED, 32),
                              QLineEdit.ActionPosition.LeadingPosition)
        self.search.setFixedWidth(260)
        self.search.textChanged.connect(self.refresh_content)
        bar.addWidget(self.type_filter)
        bar.addWidget(self.search)
        lay.addLayout(bar)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["ID", "Turi", "Nomi", "Muallif", "Janr", "Media", "Tavsiya"])
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch)
        self._setup_table(self.table)
        self.table.doubleClicked.connect(lambda: self.edit_content())
        lay.addWidget(self.table, 1)

        self.content_count = QLabel("")
        self.content_count.setObjectName("hint")
        lay.addWidget(self.content_count)
        return w

    def refresh_content(self):
        query = (self.search.text() if hasattr(self, "search") else "").lower().strip()
        tfilter = self.type_filter.currentData() if hasattr(self, "type_filter") else None
        items = db.get_content()
        if tfilter:
            items = [it for it in items if it["type"] == tfilter]
        if query:
            items = [it for it in items
                     if query in " ".join(str(it.get(k) or "").lower()
                                          for k in ("title", "author", "genre"))]
        self._content_rows = items

        star = svg_icon("star", "#F59E0B", 32)
        self.table.setRowCount(len(items))
        for r, it in enumerate(items):
            cells = [str(it["id"]), TYPE_LABELS.get(it["type"], it["type"]),
                     it["title"], it.get("author") or "", it.get("genre") or "",
                     "Bor" if it.get("file_path") else "—",
                     "Tavsiya" if it.get("is_recommended") else ""]
            for col, val in enumerate(cells):
                item = QTableWidgetItem(val)
                if col == 6 and it.get("is_recommended"):
                    item.setIcon(star)
                if col in (0, 5):
                    item.setForeground(Qt.GlobalColor.darkGray)
                self.table.setItem(r, col, item)
        self.content_count.setText(f"Jami: {len(items)} ta")

    def _selected_id(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(getattr(self, "_content_rows", [])):
            return None
        return self._content_rows[row]["id"]

    def add_content(self):
        dlg = ContentDialog(self)
        if dlg.exec():
            db.add_content(dlg.values())
            self.refresh_content()
            self.statusBar().showMessage("Kontent qo'shildi.", 3000)

    def edit_content(self):
        cid = self._selected_id()
        if cid is None:
            QMessageBox.information(self, "Eslatma", "Avval qatorni tanlang.")
            return
        item = db.get_content_by_id(cid)
        dlg = ContentDialog(self, item)
        if dlg.exec():
            db.update_content(cid, dlg.values())
            self.refresh_content()
            self.statusBar().showMessage("Kontent yangilandi.", 3000)

    def delete_content(self):
        cid = self._selected_id()
        if cid is None:
            QMessageBox.information(self, "Eslatma", "Avval qatorni tanlang.")
            return
        if QMessageBox.question(self, "Tasdiqlang",
                                f"#{cid} kontent o'chirilsinmi?") \
                == QMessageBox.StandardButton.Yes:
            db.delete_content(cid)
            self.refresh_content()
            self.statusBar().showMessage("Kontent o'chirildi.", 3000)

    # ------------------------------------------------------------------
    #  Generik CRUD sahifa (Reklama / Saytlar / Bekatlar uchun umumiy)
    # ------------------------------------------------------------------
    def _crud_page(self, name, page_title, page_sub, columns, fields, get_all,
                   add_fn, update_fn, delete_fn, dialog_title):
        """columns: [(header, key), ...]; fields: RecordDialog uchun maydonlar."""
        w, lay = self._page(page_title, page_sub)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        bar.addWidget(self._btn("Qo'shish", "plus",
                                lambda: self._crud_add(name)))
        bar.addWidget(self._btn("Tahrirlash", "pencil",
                                lambda: self._crud_edit(name), "ghost"))
        bar.addWidget(self._btn("O'chirish", "trash-2",
                                lambda: self._crud_delete(name), "danger"))
        bar.addWidget(self._btn("Yangilash", "refresh-cw",
                                lambda: self._crud_refresh(name), "ghost"))
        bar.addStretch(1)
        lay.addLayout(bar)

        table = QTableWidget(0, len(columns))
        table.setHorizontalHeaderLabels([h for h, _ in columns])
        table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch)
        self._setup_table(table)
        table.doubleClicked.connect(lambda: self._crud_edit(name))
        lay.addWidget(table, 1)

        count = QLabel("")
        count.setObjectName("hint")
        lay.addWidget(count)

        self._crud[name] = dict(
            table=table, columns=columns, fields=fields, get_all=get_all,
            add=add_fn, update=update_fn, delete=delete_fn,
            title=dialog_title, count=count)
        self._crud_refresh(name)
        return w

    def _crud_refresh(self, name):
        cfg = self._crud[name]
        items = cfg["get_all"]()
        cfg["rows"] = items
        table = cfg["table"]
        table.setRowCount(len(items))
        for r, it in enumerate(items):
            for col, (_h, key) in enumerate(cfg["columns"]):
                val = it.get(key)
                if key == "is_active":
                    text = "Faol" if val else "—"
                elif val is None:
                    text = ""
                else:
                    text = str(val)
                table.setItem(r, col, QTableWidgetItem(text))
        cfg["count"].setText(f"Jami: {len(items)} ta")

    def _crud_selected(self, name):
        cfg = self._crud[name]
        row = cfg["table"].currentRow()
        if row < 0 or row >= len(cfg.get("rows", [])):
            return None
        return cfg["rows"][row]

    def _crud_add(self, name):
        cfg = self._crud[name]
        dlg = RecordDialog(self, f"Yangi: {cfg['title']}", cfg["fields"])
        if dlg.exec():
            cfg["add"](dlg.values())
            self._crud_refresh(name)
            self.statusBar().showMessage("Yozuv qo'shildi.", 3000)

    def _crud_edit(self, name):
        cfg = self._crud[name]
        item = self._crud_selected(name)
        if item is None:
            QMessageBox.information(self, "Eslatma", "Avval qatorni tanlang.")
            return
        dlg = RecordDialog(self, f"Tahrirlash: {cfg['title']}", cfg["fields"], item)
        if dlg.exec():
            cfg["update"](item["id"], dlg.values())
            self._crud_refresh(name)
            self.statusBar().showMessage("Yozuv yangilandi.", 3000)

    def _crud_delete(self, name):
        cfg = self._crud[name]
        item = self._crud_selected(name)
        if item is None:
            QMessageBox.information(self, "Eslatma", "Avval qatorni tanlang.")
            return
        if QMessageBox.question(self, "Tasdiqlang",
                                f"#{item['id']} o'chirilsinmi?") \
                == QMessageBox.StandardButton.Yes:
            cfg["delete"](item["id"])
            self._crud_refresh(name)
            self.statusBar().showMessage("Yozuv o'chirildi.", 3000)

    # --- Reklama sahifasi ---
    def _ads_page(self):
        return self._crud_page(
            "ads", "Reklama", "Asosiy ekranda aylanadigan reklama bannerlari",
            columns=[("ID", "id"), ("Sarlavha", "title"), ("Subtitr", "subtitle"),
                     ("Havola", "link_url"), ("Faol", "is_active"), ("Tartib", "sort_order")],
            fields=[("title", "Sarlavha", "text"),
                    ("subtitle", "Subtitr", "text"),
                    ("link_url", "Havola (URL)", "text"),
                    ("image_path", "Rasm fayli nomi (ixtiyoriy)", "text"),
                    ("is_active", "Faol", "bool"),
                    ("sort_order", "Tartib raqami", "int")],
            get_all=lambda: db.get_ads(active_only=False),
            add_fn=db.add_ad, update_fn=db.update_ad, delete_fn=db.delete_ad,
            dialog_title="reklama")

    # --- Saytlar sahifasi ---
    def _sites_page(self):
        return self._crud_page(
            "sites", "Saytlar", "Kioskda ochish mumkin bo'lgan tavsiya saytlar",
            columns=[("ID", "id"), ("Nomi", "name"), ("URL", "url"),
                     ("Tavsif", "description"), ("Tartib", "sort_order")],
            fields=[("name", "Nomi", "text"),
                    ("url", "URL", "text"),
                    ("description", "Tavsif", "multiline"),
                    ("features", "Imkoniyatlar (; bilan ajrating)", "multiline"),
                    ("icon", "Ikonka nomi", "text"),
                    ("sort_order", "Tartib raqami", "int")],
            get_all=db.get_sites,
            add_fn=db.add_site, update_fn=db.update_site, delete_fn=db.delete_site,
            dialog_title="sayt")

    # --- Bekatlar sahifasi ---
    def _route_page(self):
        return self._crud_page(
            "route", "Bekatlar", "Yo'nalish bekatlari — xarita va timeline uchun",
            columns=[("ID", "id"), ("Bekat", "name"), ("Kelish", "arrival_time"),
                     ("Kenglik", "latitude"), ("Uzunlik", "longitude"), ("Tartib", "sort_order")],
            fields=[("name", "Bekat nomi", "text"),
                    ("arrival_time", "Kelish vaqti (HH:MM)", "text"),
                    ("latitude", "Kenglik (lat)", "float"),
                    ("longitude", "Uzunlik (lng)", "float"),
                    ("sort_order", "Tartib raqami", "int")],
            get_all=db.get_route,
            add_fn=db.add_route_stop, update_fn=db.update_route_stop,
            delete_fn=db.delete_route_stop,
            dialog_title="bekat")

    # --- Sozlamalar sahifasi ---
    def _settings_page(self):
        w, lay = self._page("Sozlamalar", "Poyezd va vagon ma'lumotlari")

        card, clay = self._card(22)
        form = QFormLayout()
        form.setSpacing(12)
        self.s_wagon = QLineEdit()
        self.s_wagon_note = QLineEdit()
        self.s_train = QLineEdit()
        self.s_route = QLineEdit()
        self.s_route.setPlaceholderText("Toshkent → Samarqand")
        self.s_depart = QLineEdit()
        self.s_depart.setPlaceholderText("08:00")
        form.addRow("Vagon raqami:", self.s_wagon)
        form.addRow("Vagon izohi:", self.s_wagon_note)
        form.addRow("Poyezd nomi:", self.s_train)
        form.addRow("Yo'nalish:", self.s_route)
        form.addRow("Jo'nash vaqti:", self.s_depart)
        clay.addLayout(form)

        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self._btn("Saqlash", "save", self.save_settings))
        clay.addLayout(row)

        lay.addWidget(card)
        lay.addStretch(1)
        return w

    def load_settings(self):
        s = db.get_settings()
        self.s_wagon.setText(s.get("wagon_number", ""))
        self.s_wagon_note.setText(s.get("wagon_note", ""))
        self.s_train.setText(s.get("train_name", ""))
        self.s_route.setText(s.get("route", ""))
        self.s_depart.setText(s.get("depart_time", ""))

    def save_settings(self):
        db.set_setting("wagon_number", self.s_wagon.text())
        db.set_setting("wagon_note", self.s_wagon_note.text())
        db.set_setting("train_name", self.s_train.text())
        db.set_setting("route", self.s_route.text())
        db.set_setting("depart_time", self.s_depart.text())
        self.statusBar().showMessage("Sozlamalar saqlandi.", 3000)

    # --- Yopilganda backendni to'xtatamiz ---
    def closeEvent(self, e):
        self.server.stop()
        self.server.wait(3000)
        super().closeEvent(e)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
        datefmt="%H:%M:%S")
    db.init_db()
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)

    # Port band bo'lsa (oldingi nusxa hali ishlayapti) — tushunarli ogohlantirish
    if port_in_use(config.PORT):
        QMessageBox.critical(
            None, "Server allaqachon ishlayapti",
            f"{config.PORT}-port band.\n\nEhtimol Kiosk serverining boshqa nusxasi "
            f"hali ochiq. Avval uni yoping (yoki Vazifalar menejeridan python.exe "
            f"jarayonini to'xtating), so'ng qaytadan oching.")
        sys.exit(1)

    win = AdminWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
