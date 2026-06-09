"""
admin.py — Server (admin) DESKTOP oynasi (PyQt6).

Bu — server qismining yuzi. Ishga tushganda:
  - ichida FastAPI backendni (uvicorn) alohida oqimda ishga tushiradi,
  - admin'ga kontentni boshqarish (qo'shish/o'chirish), sozlamalar va
    server holatini ko'rsatadi.

Ya'ni `server.exe` = shu fayl. Foydalanuvchiga faqat desktop oyna ko'rinadi,
backend ichkarida ishlaydi (TZ 4.2 — admin interfeysi PyQt6 oyna).

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
    QApplication, QWidget, QMainWindow, QTabWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QFormLayout, QLineEdit, QComboBox, QTextEdit, QCheckBox, QDialog,
    QFileDialog, QMessageBox, QDialogButtonBox, QSpinBox, QDoubleSpinBox, QFrame
)
from PyQt6.QtCore import Qt, QThread, QTimer

import config
import db
import ws

CONTENT_TYPES = ["movie", "cartoon", "music", "book", "audiobook"]

# Zamonaviy, ochiq mavzudagi global stil (TZ 4.2 — admin interfeysi)
STYLE = """
QMainWindow, QDialog { background: #EEF2F7; }
QWidget { color: #0F172A; font-family: 'Segoe UI', Arial; font-size: 14px; }
QLabel { background: transparent; }

QTabWidget::pane { border: none; background: #EEF2F7; top: -1px; }
QTabBar::tab {
    background: transparent; color: #64748B;
    padding: 10px 22px; margin-right: 4px; border: none;
    font-weight: 600; border-radius: 9px;
}
QTabBar::tab:selected { background: #FFFFFF; color: #2563EB; }
QTabBar::tab:hover:!selected { color: #0F172A; }

QPushButton {
    background: #2563EB; color: #FFFFFF; border: none;
    padding: 9px 16px; border-radius: 9px; font-weight: 600;
}
QPushButton:hover { background: #1D4ED8; }
QPushButton:pressed { background: #1E40AF; }
QPushButton#ghost { background: #FFFFFF; color: #334155; border: 1px solid #CBD5E1; }
QPushButton#ghost:hover { background: #F1F5F9; }
QPushButton#danger { background: #EF4444; }
QPushButton#danger:hover { background: #DC2626; }

QLineEdit, QComboBox, QTextEdit, QSpinBox {
    background: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 9px;
    padding: 8px 10px; selection-background-color: #2563EB;
    selection-color: #FFFFFF;
}
QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QSpinBox:focus {
    border: 1px solid #2563EB;
}

QFrame#card {
    background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 16px;
}

QTableWidget {
    background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 14px;
    gridline-color: #EEF2F6;
}
QHeaderView::section {
    background: #F8FAFC; color: #64748B; padding: 11px 10px; border: none;
    border-bottom: 1px solid #E2E8F0; font-weight: 600;
}
QTableWidget::item { padding: 8px 6px; border-bottom: 1px solid #F1F5F9; }
QTableWidget::item:selected { background: #EFF6FF; color: #0F172A; }
QTableWidget:focus { outline: none; }
"""


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
        self.setWindowTitle("Kontentni tahrirlash" if item else "Yangi kontent qo'shish")
        self.setMinimumWidth(460)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        form = QFormLayout()

        self.type = QComboBox()
        self.type.addItems(CONTENT_TYPES)
        if self.item.get("type"):
            self.type.setCurrentText(self.item["type"])

        self.title = QLineEdit(self.item.get("title", ""))
        self.author = QLineEdit(self.item.get("author") or "")
        self.genre = QLineEdit(self.item.get("genre") or "")
        self.tab = QLineEdit(self.item.get("category_tab") or "")
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

        # Media fayl tanlash
        file_row = QHBoxLayout()
        self.file_label = QLabel(self.item.get("file_path") or "Fayl tanlanmagan")
        pick = QPushButton("Fayl tanlash...")
        pick.clicked.connect(self._pick_file)
        file_row.addWidget(self.file_label, 1)
        file_row.addWidget(pick)

        form.addRow("Turi:", self.type)
        form.addRow("Nomi:", self.title)
        form.addRow("Muallif:", self.author)
        form.addRow("Janr:", self.genre)
        form.addRow("Tab (kategoriya):", self.tab)
        form.addRow("Tavsif:", self.desc)
        form.addRow("Davomiylik:", self.duration)
        form.addRow("Sahifalar:", self.pages)
        form.addRow("Media fayl:", file_row)
        form.addRow("", self.recommended)
        lay.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _pick_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Media fayl tanlash", "",
            "Media (*.mp4 *.mkv *.avi *.mp3 *.m4a *.wav);; Barcha fayllar (*.*)")
        if path:
            self.media_src = path
            self.file_label.setText(os.path.basename(path))

    def _accept(self):
        if not self.title.text().strip():
            QMessageBox.warning(self, "Xato", "Nomi bo'sh bo'lmasligi kerak.")
            return
        self.accept()

    def values(self):
        """Dialogdagi qiymatlarni DB uchun dict qilib qaytaradi."""
        data = {
            "type": self.type.currentText(),
            "title": self.title.text().strip(),
            "author": self.author.text().strip() or None,
            "genre": self.genre.text().strip() or None,
            "category_tab": self.tab.text().strip() or None,
            "description": self.desc.toPlainText().strip() or None,
            "duration": self.duration.value() or None,
            "pages": self.pages.value() or None,
            "is_recommended": 1 if self.recommended.isChecked() else 0,
        }
        # Media faylni content/media ga ko'chiramiz
        if self.media_src:
            os.makedirs(config.MEDIA_DIR, exist_ok=True)
            dst_name = os.path.basename(self.media_src)
            shutil.copy2(self.media_src, os.path.join(config.MEDIA_DIR, dst_name))
            data["file_path"] = dst_name
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
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kiosk — Server admin")
        self.resize(1040, 720)

        self.server = ServerThread()
        self.server.start()

        # Generik CRUD tablar holati (reklama/sayt/bekat) shu yerda saqlanadi
        self._crud = {}

        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.addTab(self._server_tab(), "📡  Server")
        tabs.addTab(self._content_tab(), "🎬  Kontent")
        tabs.addTab(self._ads_tab(), "📢  Reklama")
        tabs.addTab(self._sites_tab(), "🌐  Saytlar")
        tabs.addTab(self._route_tab(), "🚉  Bekatlar")
        tabs.addTab(self._settings_tab(), "⚙  Sozlamalar")

        wrap = QWidget()
        wlay = QVBoxLayout(wrap)
        wlay.setContentsMargins(18, 14, 18, 18)
        wlay.addWidget(tabs)
        self.setCentralWidget(wrap)

        self.refresh_content()
        self.load_settings()

    # --- Umumiy: oq "karta" konteyner ---
    def _card(self, padding=18):
        card = QFrame()
        card.setObjectName("card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(padding, padding, padding, padding)
        lay.setSpacing(10)
        return card, lay

    # --- Server tab ---
    def _server_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(2, 12, 2, 2)
        lay.setSpacing(14)
        lay.setAlignment(Qt.AlignmentFlag.AlignTop)

        # === Yuqori qator: holat kartasi + kiosklar soni kartasi ===
        top = QHBoxLayout()
        top.setSpacing(14)

        # Holat kartasi
        stat_card, stat_lay = self._card()
        self.status_lbl = QLabel()
        self.status_lbl.setStyleSheet("font-size: 18px; font-weight: 700;")
        ip0 = local_ips()[0]
        addr = QLabel(f"🌐  http://{ip0}:{config.PORT}")
        addr.setStyleSheet("color: #475569; font-size: 13px;")
        hint = QLabel(f"User config: KIOSK_SERVER=http://{ip0}:{config.PORT}")
        hint.setStyleSheet("color: #94A3B8; font-size: 12px;")
        stat_lay.addWidget(self.status_lbl)
        stat_lay.addWidget(addr)
        stat_lay.addWidget(hint)
        stat_lay.addStretch(1)
        top.addWidget(stat_card, 1)

        # Ulangan kiosklar soni kartasi
        count_card, count_lay = self._card()
        count_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.users_num = QLabel("0")
        self.users_num.setStyleSheet("font-size: 52px; font-weight: 800; color: #2563EB;")
        self.users_num.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cap = QLabel("Ulangan kiosklar")
        cap.setStyleSheet("color: #64748B; font-weight: 600;")
        cap.setAlignment(Qt.AlignmentFlag.AlignCenter)
        count_lay.addWidget(self.users_num)
        count_lay.addWidget(cap)
        count_card.setFixedWidth(220)
        top.addWidget(count_card)
        lay.addLayout(top)

        # === E'lon yuborish kartasi ===
        ann_card, ann_lay = self._card()
        ann_title = QLabel("📢  Barcha kiosklarga e'lon")
        ann_title.setStyleSheet("font-weight: 700; font-size: 15px;")
        ann_lay.addWidget(ann_title)
        ann_row = QHBoxLayout()
        self.ann_input = QLineEdit()
        self.ann_input.setPlaceholderText("E'lon matnini kiriting...")
        self.ann_input.returnPressed.connect(self.send_announcement)
        send = QPushButton("Yuborish")
        send.clicked.connect(self.send_announcement)
        ann_row.addWidget(self.ann_input, 1)
        ann_row.addWidget(send)
        ann_lay.addLayout(ann_row)
        lay.addWidget(ann_card)

        # === Kiosklar jadvali ===
        ktitle = QLabel("Ulangan kiosklar — batafsil")
        ktitle.setStyleSheet("font-weight: 700; font-size: 15px; margin-left: 4px;")
        lay.addWidget(ktitle)

        self.kiosk_table = QTableWidget(0, 5)
        self.kiosk_table.setHorizontalHeaderLabels(
            ["Qurilma", "IP manzil", "Tizim", "Ulangan vaqt", "Davomiyligi"])
        kh = self.kiosk_table.horizontalHeader()
        kh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        kh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.kiosk_table.verticalHeader().setVisible(False)
        self.kiosk_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.kiosk_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.kiosk_table.setShowGrid(False)
        lay.addWidget(self.kiosk_table, 1)

        self.empty_lbl = QLabel("Hozircha hech qaysi kiosk ulanmagan.")
        self.empty_lbl.setStyleSheet("color: #94A3B8; padding: 12px 4px;")
        lay.addWidget(self.empty_lbl)

        # Holatni davriy yangilab turamiz
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_status)
        self.timer.start(1000)
        self._update_status()
        return w

    def _update_status(self):
        running = self.server.isRunning() and not self.server.server.should_exit
        if running:
            self.status_lbl.setText(f"🟢  Server ishlayapti")
        else:
            self.status_lbl.setText("🔴  Server to'xtagan")

        clients = ws.manager.clients()
        self.users_num.setText(str(len(clients)))
        self.empty_lbl.setVisible(not clients)

        self.kiosk_table.setRowCount(len(clients))
        for r, c in enumerate(clients):
            when = ""
            if c.get("connected_at"):
                when = datetime.fromtimestamp(c["connected_at"]).strftime("%H:%M:%S")
            cells = [
                f"🖥  {c['device_id']}",
                c["ip"],
                c["platform"],
                when,
                _fmt_uptime(c["uptime"]),
            ]
            for col, val in enumerate(cells):
                item = QTableWidgetItem(val)
                if col in (1, 3, 4):
                    item.setForeground(Qt.GlobalColor.darkGray)
                self.kiosk_table.setItem(r, col, item)

    def send_announcement(self):
        text = self.ann_input.text().strip()
        if not text:
            return
        ws.manager.broadcast_threadsafe({"type": "announcement", "text": text})
        self.ann_input.clear()
        QMessageBox.information(self, "Yuborildi", "E'lon barcha userlarga yuborildi.")

    # --- Kontent tab ---
    def _content_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)

        btn_row = QHBoxLayout()
        add = QPushButton("➕ Qo'shish")
        edit = QPushButton("✏️ Tahrirlash")
        delete = QPushButton("🗑 O'chirish")
        refresh = QPushButton("🔄 Yangilash")
        edit.setObjectName("ghost")
        refresh.setObjectName("ghost")
        delete.setObjectName("danger")
        add.clicked.connect(self.add_content)
        edit.clicked.connect(self.edit_content)
        delete.clicked.connect(self.delete_content)
        refresh.clicked.connect(self.refresh_content)
        for b in (add, edit, delete, refresh):
            btn_row.addWidget(b)
        btn_row.addStretch(1)
        lay.addLayout(btn_row)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["ID", "Turi", "Nomi", "Muallif", "Janr", "Tavsiya"])
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        lay.addWidget(self.table)
        return w

    def refresh_content(self):
        items = db.get_content()
        self.table.setRowCount(len(items))
        for r, it in enumerate(items):
            cells = [str(it["id"]), it["type"], it["title"],
                     it.get("author") or "", it.get("genre") or "",
                     "★" if it.get("is_recommended") else ""]
            for col, val in enumerate(cells):
                self.table.setItem(r, col, QTableWidgetItem(val))

    def _selected_id(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        return int(self.table.item(row, 0).text())

    def add_content(self):
        dlg = ContentDialog(self)
        if dlg.exec():
            db.add_content(dlg.values())
            self.refresh_content()

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

    # ------------------------------------------------------------------
    #  Generik CRUD tab (Reklama / Saytlar / Bekatlar uchun umumiy)
    # ------------------------------------------------------------------
    def _crud_tab(self, name, columns, fields, get_all,
                  add_fn, update_fn, delete_fn, dialog_title):
        """columns: [(header, key), ...]; fields: RecordDialog uchun maydonlar."""
        w = QWidget()
        lay = QVBoxLayout(w)

        btn_row = QHBoxLayout()
        add = QPushButton("➕ Qo'shish")
        edit = QPushButton("✏️ Tahrirlash")
        delete = QPushButton("🗑 O'chirish")
        refresh = QPushButton("🔄 Yangilash")
        edit.setObjectName("ghost")
        refresh.setObjectName("ghost")
        delete.setObjectName("danger")
        add.clicked.connect(lambda: self._crud_add(name))
        edit.clicked.connect(lambda: self._crud_edit(name))
        delete.clicked.connect(lambda: self._crud_delete(name))
        refresh.clicked.connect(lambda: self._crud_refresh(name))
        for b in (add, edit, delete, refresh):
            btn_row.addWidget(b)
        btn_row.addStretch(1)
        lay.addLayout(btn_row)

        table = QTableWidget(0, len(columns))
        table.setHorizontalHeaderLabels([h for h, _ in columns])
        table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.doubleClicked.connect(lambda: self._crud_edit(name))
        lay.addWidget(table)

        self._crud[name] = dict(
            table=table, columns=columns, fields=fields, get_all=get_all,
            add=add_fn, update=update_fn, delete=delete_fn, title=dialog_title)
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
                    text = "✓" if val else "—"
                elif val is None:
                    text = ""
                else:
                    text = str(val)
                table.setItem(r, col, QTableWidgetItem(text))

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

    # --- Reklama tab ---
    def _ads_tab(self):
        return self._crud_tab(
            "ads",
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

    # --- Saytlar tab ---
    def _sites_tab(self):
        return self._crud_tab(
            "sites",
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

    # --- Bekatlar tab ---
    def _route_tab(self):
        return self._crud_tab(
            "route",
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

    # --- Sozlamalar tab ---
    def _settings_tab(self):
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(2, 12, 2, 2)
        outer.setAlignment(Qt.AlignmentFlag.AlignTop)

        card, clay = self._card(22)
        title = QLabel("Poyezd sozlamalari")
        title.setStyleSheet("font-weight: 700; font-size: 16px;")
        clay.addWidget(title)

        form = QFormLayout()
        form.setSpacing(12)
        self.s_wagon = QLineEdit()
        self.s_wagon_note = QLineEdit()
        self.s_train = QLineEdit()
        self.s_route = QLineEdit()
        self.s_depart = QLineEdit()
        form.addRow("Vagon raqami:", self.s_wagon)
        form.addRow("Vagon izohi:", self.s_wagon_note)
        form.addRow("Poyezd nomi:", self.s_train)
        form.addRow("Yo'nalish:", self.s_route)
        form.addRow("Jo'nash vaqti:", self.s_depart)
        clay.addLayout(form)

        save = QPushButton("💾 Saqlash")
        save.clicked.connect(self.save_settings)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(save)
        clay.addLayout(row)

        outer.addWidget(card)
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
        QMessageBox.information(self, "Saqlandi", "Sozlamalar saqlandi.")

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
