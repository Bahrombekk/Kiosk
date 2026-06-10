"""ui/pages/dashboard.py — Boshqaruv (dashboard) sahifasi mixin'i."""
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt

import config
import db
import ws
from icons import svg_icon, svg_pixmap
from ui.styles import C_ACCENT, C_MUTED, C_OK, C_BAD
from ui.helpers import _fmt_uptime, local_ips


class DashboardPageMixin:
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
        for key, label, icon_name, fg, bg in (
                ("kiosks", "Ulangan kiosklar", "monitor", "#1D4ED8", "#DBEAFE"),
                ("content", "Kontentlar", "clapperboard", "#7C3AED", "#EDE9FE"),
                ("ads", "Reklamalar", "megaphone", "#B45309", "#FEF3C7"),
                ("sites", "Saytlar", "globe", "#0F766E", "#CCFBF1")):
            card, clay = self._card(16)
            row = QHBoxLayout()
            row.setSpacing(12)
            # Rangli ikonka plitkasi
            ic = QLabel()
            ic.setFixedSize(42, 42)
            ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ic.setStyleSheet(f"background: {bg}; border-radius: 12px;")
            ic.setPixmap(svg_pixmap(icon_name, fg, 22))
            num = QLabel("0")
            num.setObjectName("bigNum")
            cap = QLabel(label)
            cap.setObjectName("muted")
            col = QVBoxLayout()
            col.setSpacing(0)
            col.addWidget(num)
            col.addWidget(cap)
            row.addWidget(ic, 0, Qt.AlignmentFlag.AlignVCenter)
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

        # API kalit qatori — kiosk o'rnatuvchisiga kiritiladi (maskalangan,
        # "Nusxalash" tugmasi to'liq kalitni clipboard'ga oladi).
        self._api_key = db.get_or_create_api_key()
        krow = QHBoxLayout()
        krow.setSpacing(10)
        key_ic = QLabel()
        key_ic.setPixmap(svg_pixmap("copy", C_MUTED, 16))
        masked = self._api_key[:4] + "•" * 8 + self._api_key[-4:]
        key_lbl = QLabel(f"API kalit: {masked}")
        key_lbl.setObjectName("muted")
        key_copy = self._btn("Nusxalash", "copy", self._copy_api_key, kind="ghost")
        krow.addWidget(key_ic)
        krow.addWidget(key_lbl)
        krow.addWidget(key_copy)
        krow.addStretch(1)
        stat_lay.addLayout(krow)
        key_hint = QLabel("Kiosk o'rnatishda shu kalit so'raladi (server.txt'dagi key= qatori)")
        key_hint.setObjectName("hint")
        stat_lay.addWidget(key_hint)
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

    def _copy_api_key(self):
        QApplication.clipboard().setText(self._api_key)
        self.statusBar().showMessage("API kalit nusxalandi.", 3000)

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
        db.log_action("announcement_sent", text)
        self.statusBar().showMessage(
            f"E'lon yuborildi ({n} ta kioskka): {text}", 5000)
