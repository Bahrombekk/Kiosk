"""ui/pages/cache.py — "Lokal kesh" sahifasi mixin'i.

Qaysi (keshlanadigan) kontent qaysi kioskka yuklangan / yuklanmaganini
ko'rsatadi va kioskka qo'lda yuklash buyrug'ini beradi:
  - chapda kiosklar ro'yxati (onlayn, N/M yuklangan, kesh yoq/yo'q);
  - o'ngda tanlangan kioskда har kontent holati: ✓ yuklangan / ⬇NN% / ○ yo'q;
  - "Hoziroq yukla" (shu kioskка), "Barchasiga yukla", har kiosk kesh toggle.
Jonli yangilanadi (heartbeat'dan kelgan cached_ids / caching).
"""
import json

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor

import db
import ws
from ui.toggle import ToggleSwitch


class CachePageMixin:
    # ------------------------------------------------------------------
    #  "Lokal kesh" sahifasi
    # ------------------------------------------------------------------
    def _cache_page(self):
        w, lay = self._page(
            "Lokal kesh",
            "Qaysi kontent qaysi kioskka yuklangan — va qo'lda yuklash")

        top = QHBoxLayout()
        top.addWidget(self._btn("Yangilash", "refresh-cw",
                                self._refresh_cache_matrix, kind="ghost"))
        top.addWidget(self._btn("Barchasiga yukla", "save",
                                self._cache_sync_all))
        top.addStretch(1)
        self.cache_hint = QLabel("")
        self.cache_hint.setStyleSheet("color:#64748B;")
        top.addWidget(self.cache_hint)
        lay.addLayout(top)

        body = QHBoxLayout()
        body.setSpacing(16)

        # --- Chap: kiosklar ro'yxati (oq karta) ---
        lcard, lc = self._card(14)
        lcard.setFixedWidth(320)
        kl = QLabel("Kiosklar")
        kl.setObjectName("cardTitle")
        lc.addWidget(kl)
        self.cache_klist = QListWidget()
        self.cache_klist.setObjectName("kioskList")
        self.cache_klist.setStyleSheet(
            "QListWidget#kioskList { background: #FFFFFF; border: none;"
            "  outline: none; }"
            "QListWidget#kioskList::item { padding: 11px 12px;"
            "  border-radius: 10px; margin: 2px 0; color: #0F172A; }"
            "QListWidget#kioskList::item:hover { background: #F1F5F9; }"
            "QListWidget#kioskList::item:selected { background: #EFF6FF;"
            "  color: #0F172A; }")
        self.cache_klist.currentRowChanged.connect(self._on_cache_kiosk_sel)
        lc.addWidget(self.cache_klist, 1)
        body.addWidget(lcard)

        # --- O'ng: tanlangan kiosk tafsiloti (oq karta) ---
        rcard, rc = self._card(14)
        head = QHBoxLayout()
        self.cache_hdr = QLabel("Chapdan kioskni tanlang")
        self.cache_hdr.setObjectName("cardTitle")
        head.addWidget(self.cache_hdr)
        head.addStretch(1)
        head.addWidget(QLabel("Lokal kesh:"))
        self.cache_dev_toggle = ToggleSwitch()
        self.cache_dev_toggle.setEnabled(False)
        self.cache_dev_toggle.toggled.connect(self._on_cache_toggle)
        head.addWidget(self.cache_dev_toggle)
        rc.addLayout(head)

        # Tanlangan kiosk haqida to'liq ma'lumot (IP, xona, disk, ...)
        self.cache_info = QLabel("")
        self.cache_info.setObjectName("muted")
        self.cache_info.setWordWrap(True)
        self.cache_info.setStyleSheet("color:#64748B; font-size:13px;")
        rc.addWidget(self.cache_info)

        act = QHBoxLayout()
        self.cache_sync_btn = self._btn("Hoziroq yukla", "save",
                                        self._cache_sync_selected)
        self.cache_sync_btn.setEnabled(False)
        act.addWidget(self.cache_sync_btn)
        act.addStretch(1)
        rc.addLayout(act)

        self.cache_table = QTableWidget(0, 3)
        self.cache_table.setHorizontalHeaderLabels(["Holat", "Nomi", "Turi"])
        self.cache_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch)
        self._setup_table(self.cache_table)
        rc.addWidget(self.cache_table, 1)
        body.addWidget(rcard, 1)
        lay.addLayout(body, 1)

        # Holat
        self._cache_kiosks = []     # ro'yxatdagi tartibda kiosk qatorlari
        self._cache_sel_dev = None  # tanlangan device_id
        self._cache_timer = QTimer(self)
        self._cache_timer.timeout.connect(self._refresh_cache_matrix)
        return w

    # ------------------------------------------------------------------
    #  Yangilash
    # ------------------------------------------------------------------
    def _refresh_cache_matrix(self):
        try:
            kiosks = db.get_kiosks()
        except Exception:
            kiosks = []
        av = self._cacheable_av()
        total = len(av)
        online_ids = {c.get("device_id") for c in ws.manager.clients()}

        self._cache_kiosks = kiosks
        # Har kiosk uchun yorliq (matn, onlayn) tayyorlaymiz
        labels = []
        for k in kiosks:
            dev = k.get("device_id")
            try:
                ids = set(json.loads(k.get("cached_ids") or "[]"))
            except (ValueError, TypeError):
                ids = set()
            done = len(ids & {c["id"] for c in av})
            online = dev in online_ids
            name = k.get("kiosk_no") or dev or "Kiosk"
            if k.get("room"):
                name += f" · {k['room']}"
            dot = "🟢" if online else "⚪"
            state = "kesh o'chiq" if not k.get("cache_enabled", 1) else f"{done}/{total}"
            labels.append((f"{dot}  {name}\n      {state}", online))

        lst = self.cache_klist
        if lst.count() != len(kiosks):
            # Tuzilma o'zgardi — qayta quramiz (tanlovni saqlab)
            prev = self._cache_sel_dev
            lst.blockSignals(True)
            lst.clear()
            for text, online in labels:
                it = QListWidgetItem(text)
                if not online:
                    it.setForeground(QColor("#94A3B8"))
                lst.addItem(it)
            lst.blockSignals(False)
            for i, k in enumerate(kiosks):
                if k.get("device_id") == prev:
                    lst.setCurrentRow(i)
                    break
        else:
            # Faqat matn/rangni joyida yangilaymiz (miltillamasin)
            for i, (text, online) in enumerate(labels):
                it = lst.item(i)
                it.setText(text)
                it.setForeground(QColor("#94A3B8") if not online
                                 else QColor("#1C2230"))
        self.cache_hint.setText(
            f"{len(kiosks)} kiosk · {total} keshlanadigan kontent")
        self._refresh_cache_detail()

    def _on_cache_kiosk_sel(self, row):
        if 0 <= row < len(self._cache_kiosks):
            self._cache_sel_dev = self._cache_kiosks[row].get("device_id")
        else:
            self._cache_sel_dev = None
        self._refresh_cache_detail()

    def _refresh_cache_detail(self):
        from ui.styles import TYPE_LABELS
        dev = self._cache_sel_dev
        k = next((x for x in self._cache_kiosks
                  if x.get("device_id") == dev), None)
        av = self._cacheable_av()
        online_ids = {c.get("device_id") for c in ws.manager.clients()}
        online = bool(k and dev in online_ids)

        if k is None:
            self.cache_hdr.setText("Chapdan kioskni tanlang")
            self.cache_info.setText("")
            self.cache_sync_btn.setEnabled(False)
            self.cache_dev_toggle.setEnabled(False)
            self.cache_table.setRowCount(0)
            return

        # Tanlangan kiosk haqida to'liq ma'lumot
        gb = 1024 ** 3
        info = [f"Qurilma: {dev}"]
        if k.get("kiosk_no"):
            info.append(f"Raqami: {k['kiosk_no']}")
        if k.get("room"):
            info.append(f"Xona: {k['room']}")
        if k.get("ip"):
            info.append(f"IP: {k['ip']}")
        if k.get("platform"):
            info.append(f"Platforma: {k['platform']}")
        if k.get("disk_total"):
            info.append(f"Disk: {(k.get('disk_free') or 0) / gb:.0f} GB bo'sh"
                        f" / {k['disk_total'] / gb:.0f} GB")
        info.append("Holat: " + ("🟢 onlayn" if online else "⚪ oflayn"))
        if k.get("last_seen"):
            info.append(f"Oxirgi aloqa: {k['last_seen']}")
        self.cache_info.setText("    ·    ".join(info))

        try:
            ids = set(json.loads(k.get("cached_ids") or "[]"))
        except (ValueError, TypeError):
            ids = set()
        try:
            cg = json.loads(k.get("caching") or "null") or {}
        except (ValueError, TypeError):
            cg = {}
        done = len(ids & {c["id"] for c in av})
        name = k.get("kiosk_no") or dev
        self.cache_hdr.setText(
            f"{name} — {done}/{len(av)} yuklangan"
            + ("" if online else "   (oflayn)"))

        # Toggle (signalni vaqtincha uzib qo'yamiz — handler ishlamasin)
        self.cache_dev_toggle.blockSignals(True)
        self.cache_dev_toggle.setChecked(bool(k.get("cache_enabled", 1)))
        self.cache_dev_toggle.setEnabled(bool(dev))
        self.cache_dev_toggle.blockSignals(False)
        self.cache_sync_btn.setEnabled(
            bool(online and k.get("cache_enabled", 1)))

        self.cache_table.setRowCount(len(av))
        for r, c in enumerate(av):
            cid = c["id"]
            if cid in ids:
                txt, col = "✓ Yuklandi", QColor("#16A34A")
            elif cg.get("id") == cid:
                pct = cg.get("pct", -1)
                txt = (f"⬇ {pct}%" if isinstance(pct, int) and pct >= 0
                       else "⬇ yuklanmoqda…")
                col = QColor("#2563EB")
            elif not k.get("cache_enabled", 1):
                txt, col = "— kesh o'chiq", QColor("#94A3B8")
            else:
                txt, col = "○ Navbatda", QColor("#94A3B8")
            st = QTableWidgetItem(txt)
            st.setForeground(col)
            self.cache_table.setItem(r, 0, st)
            self.cache_table.setItem(r, 1, QTableWidgetItem(c.get("title") or ""))
            self.cache_table.setItem(r, 2, QTableWidgetItem(
                TYPE_LABELS.get(c.get("type"), c.get("type"))))

    # ------------------------------------------------------------------
    #  Amallar
    # ------------------------------------------------------------------
    def _on_cache_toggle(self, on):
        if self._cache_sel_dev:
            self._set_kiosk_cache_enabled(self._cache_sel_dev, on)
            self._refresh_cache_matrix()

    def _cache_sync_selected(self):
        dev = self._cache_sel_dev
        if not dev:
            return
        ws.manager.send_to_device_threadsafe(dev, {"type": "cache_sync"})
        db.log_action("cache_sync_device", dev)
        self.statusBar().showMessage("Yuklash buyrug'i yuborildi.", 4000)

    def _cache_sync_all(self):
        online_ids = {c.get("device_id") for c in ws.manager.clients()}
        n = 0
        for k in (self._cache_kiosks or db.get_kiosks()):
            dev = k.get("device_id")
            if dev and dev in online_ids and k.get("cache_enabled", 1):
                ws.manager.send_to_device_threadsafe(dev, {"type": "cache_sync"})
                n += 1
        db.log_action("cache_sync_all", str(n))
        self.statusBar().showMessage(
            f"{n} ta onlayn kioskka yuklash buyrug'i yuborildi.", 4000)
