"""ui/pages/dashboard.py — Boshqaruv (dashboard) sahifasi mixin'i."""
import json
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar, QWidget,
    QDialog, QDialogButtonBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

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
        hint.setWordWrap(True)
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
        key_hint.setWordWrap(True)
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

        # === Kiosklar jadvali (doimiy registr) ===
        # Bir marta ulangan kiosk ro'yxatda DOIM qoladi — hozir oflayn bo'lsa
        # ham (qachon oxirgi marta ko'ringani bilan). Raqam/xona o'rnatishda
        # kioskning server.txt fayliga yoziladi (kiosk= / xona= qatorlari).
        ktitle = QLabel("Kiosklar — № va xona bilan (oflaynlar ham ko'rinadi)")
        ktitle.setObjectName("cardTitle")
        lay.addWidget(ktitle)

        self.kiosk_table = QTableWidget(0, 8)
        self.kiosk_table.setHorizontalHeaderLabels(
            ["№", "Xona", "Qurilma", "IP manzil", "Holat",
             "Oxirgi aloqa", "Lokal kesh", "Xotira (bo'sh joy)"])
        kh = self.kiosk_table.horizontalHeader()
        kh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        kh.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        self._setup_table(self.kiosk_table)
        self.kiosk_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        # Qatorga ikki marta bosilsa — shu kioskda qaysi kontent yuklangani
        self.kiosk_table.cellDoubleClicked.connect(self._show_kiosk_cache)
        self._kiosk_rows = []
        lay.addWidget(self.kiosk_table, 1)

        self.empty_lbl = QLabel("Hozircha hech qaysi kiosk ro'yxatdan o'tmagan.")
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

        # Kiosk registri: DB'dagi doimiy ro'yxat + jonli holat.
        # Onlayn = WS ulanishi bor YOKI heartbeat so'nggi 15 soniyada kelgan.
        ws_ids = {c.get("device_id") for c in ws.manager.clients()}
        try:
            kiosks = db.get_kiosks()
        except Exception:
            kiosks = []   # DB band bo'lsa keyingi siklda
        now = datetime.now()
        online_n = 0
        self._kiosk_rows = kiosks
        self.empty_lbl.setVisible(not kiosks)
        self.kiosk_table.setRowCount(len(kiosks))
        mon_icon = svg_icon("monitor", C_MUTED, 32)
        total_av = self._av_total()
        for r, k in enumerate(kiosks):
            online = k.get("device_id") in ws_ids
            if not online and k.get("last_seen"):
                try:
                    seen = datetime.strptime(k["last_seen"],
                                             "%Y-%m-%d %H:%M:%S")
                    online = (now - seen).total_seconds() < 15
                except ValueError:
                    pass
            online_n += online
            cells = [
                k.get("kiosk_no") or "—",
                k.get("room") or "—",
                k.get("device_id") or "",
                k.get("ip") or "",
                "● Onlayn" if online else "● Oflayn",
                k.get("last_seen") or "—",
                f"{k.get('cached_n') or 0}/{total_av} media",
            ]
            for col, val in enumerate(cells):
                item = QTableWidgetItem(str(val))
                if col == 2:
                    item.setIcon(mon_icon)
                if col == 4:
                    item.setForeground(QColor("#16A34A") if online
                                       else QColor("#94A3B8"))
                elif col in (3, 5, 6):
                    item.setForeground(Qt.GlobalColor.darkGray)
                self.kiosk_table.setItem(r, col, item)
            self.kiosk_table.setCellWidget(r, 7, self._disk_cell(k))
        self._stat_lbls["kiosks"].setText(str(online_n))

    @staticmethod
    def _cacheable_av():
        """Kioskka yuklanadigan media ro'yxati: video/audio fayli bor VA
        admin "Kiosklarga yuklab qo'yilsin" belgisini qo'ygan kontentlar."""
        try:
            return [c for c in db.get_content()
                    if c.get("type") in ("movie", "cartoon", "music",
                                         "audiobook")
                    and c.get("file_path")
                    and (c.get("cache_enabled") is None
                         or c.get("cache_enabled"))]
        except Exception:
            return []

    def _av_total(self):
        return len(self._cacheable_av())

    @staticmethod
    def _disk_cell(k):
        """Kiosk diski indikatori: band foiz + «N GB bo'sh / M GB» yozuvi.
        Bo'sh joy ozayganda rang yashil -> sariq -> qizilga o'tadi."""
        total, free = k.get("disk_total") or 0, k.get("disk_free") or 0
        if not total:
            lbl = QLabel("—")
            lbl.setStyleSheet("color: #94A3B8; padding-left: 8px;")
            return lbl
        used_pct = round((total - free) * 100 / total)
        free_pct = 100 - used_pct
        chunk = ("#FCA5A5" if free_pct < 10
                 else "#FCD34D" if free_pct < 25 else "#86EFAC")
        gb = 1024 ** 3
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(used_pct)
        bar.setFormat(f"{free / gb:.1f} GB bo'sh / {total / gb:.0f} GB")
        bar.setStyleSheet(f"QProgressBar::chunk {{ background: {chunk};"
                          f" border-radius: 8px; }}")
        wrap = QWidget()
        wl = QHBoxLayout(wrap)
        wl.setContentsMargins(6, 4, 10, 4)
        wl.addWidget(bar)
        return wrap

    def _show_kiosk_cache(self, row, _col):
        """Kiosk qatoriga ikki marta bosilganda: shu qurilmada qaysi media
        yuklangan/yuklanmaganini ko'rsatadigan oyna."""
        if row >= len(self._kiosk_rows):
            return
        k = self._kiosk_rows[row]
        try:
            ids = set(json.loads(k.get("cached_ids") or "[]"))
        except (ValueError, TypeError):
            ids = set()
        av = self._cacheable_av()
        dlg = QDialog(self)
        title = k.get("kiosk_no") or k.get("device_id") or "Kiosk"
        dlg.setWindowTitle(f"Kiosk {title} — lokal kesh"
                           + (f" (xona {k['room']})" if k.get("room") else ""))
        dlg.setMinimumSize(560, 420)
        lay = QVBoxLayout(dlg)
        info = QLabel(f"Yuklangan: {len(ids & {c['id'] for c in av})} / "
                      f"{len(av)} ta media")
        info.setObjectName("cardTitle")
        lay.addWidget(info)
        table = QTableWidget(len(av), 3)
        table.setHorizontalHeaderLabels(["Holat", "Nomi", "Turi"])
        th = table.horizontalHeader()
        th.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._setup_table(table)
        from ui.styles import TYPE_LABELS
        for r, c in enumerate(av):
            ok = c["id"] in ids
            st = QTableWidgetItem("✓ Yuklangan" if ok else "○ Yuklanmagan")
            st.setForeground(QColor("#16A34A") if ok else QColor("#94A3B8"))
            table.setItem(r, 0, st)
            table.setItem(r, 1, QTableWidgetItem(c.get("title") or ""))
            table.setItem(r, 2, QTableWidgetItem(
                TYPE_LABELS.get(c.get("type"), c.get("type"))))
        lay.addWidget(table, 1)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(dlg.reject)
        btns.clicked.connect(dlg.accept)
        lay.addWidget(btns)
        dlg.exec()

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
