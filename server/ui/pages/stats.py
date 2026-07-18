"""ui/pages/stats.py — Statistika sahifasi mixin'i.

Kiosklardan kelgan foydalanish statistikasi (stats_events jadvali):
kunlik sessiyalar, eng ko'p ochilgan kontent, bo'limlar, til almashtirishlar
va reklama namoyishlari (proof-of-play). Davr: oxirgi 7 yoki 30 kun.
"""
from PyQt6.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QLabel, QComboBox, QTableWidget,
    QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt

import db
from icons import svg_pixmap
from ui.helpers import no_wheel


class StatsPageMixin:
    def _stats_page(self):
        w, lay = self._page("Statistika",
                            "Kiosklardan kelgan foydalanish ma'lumotlari")

        # Davr tanlash + yangilash
        top = QHBoxLayout()
        top.setSpacing(10)
        self.stats_period = QComboBox()
        self.stats_period.addItem("Oxirgi 7 kun", 7)
        self.stats_period.addItem("Oxirgi 30 kun", 30)
        self.stats_period.currentIndexChanged.connect(self.refresh_usage_stats)
        no_wheel(self.stats_period)   # scroll'da adashib o'zgarmasin
        top.addWidget(QLabel("Davr:"))
        top.addWidget(self.stats_period)
        # Manba filtri: kiosk (PyQt klient) va veb (Nuxt) statistikasini
        # ajratib ko'rsatadi. None = hammasi birga.
        self.stats_source = QComboBox()
        self.stats_source.addItem("Barcha manbalar", None)
        self.stats_source.addItem("Faqat kiosklar", "kiosk")
        self.stats_source.addItem("Faqat veb", "web")
        self.stats_source.currentIndexChanged.connect(self.refresh_usage_stats)
        no_wheel(self.stats_source)
        top.addWidget(QLabel("Manba:"))
        top.addWidget(self.stats_source)
        top.addWidget(self._btn("Yangilash", "refresh-cw",
                                self.refresh_usage_stats, kind="ghost"))
        top.addStretch(1)
        top.addWidget(self._btn("Statistikani tozalash", "trash-2",
                                self._reset_stats, kind="danger"))
        lay.addLayout(top)

        # Umumiy hisob kartalari
        cards = QHBoxLayout()
        cards.setSpacing(14)
        self._usage_lbls = {}
        self._usage_caps = {}   # yorliq (caption) — manba=web da o'zgaradi
        for key, label, icon_name, fg, bg in (
                ("sessions", "Sessiyalar", "monitor", "#1D4ED8", "#DBEAFE"),
                ("content_opens", "Kontent ochishlar", "clapperboard",
                 "#7C3AED", "#EDE9FE"),
                ("ad_plays", "Reklama namoyishlari", "megaphone",
                 "#B45309", "#FEF3C7"),
                ("devices", "Faol kiosklar", "server", "#0F766E", "#CCFBF1")):
            card, clay = self._card(16)
            row = QHBoxLayout()
            row.setSpacing(12)
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
            cards.addWidget(card, 1)
            self._usage_lbls[key] = num
            self._usage_caps[key] = cap
        lay.addLayout(cards)

        # Jadvallar: chapda kunlik sessiyalar, o'ngda TOP kontent
        mid = QHBoxLayout()
        mid.setSpacing(14)
        self.tbl_daily = self._stats_table(
            ["Kun", "Sessiyalar", "O'rtacha (s)"], "Kunlik sessiyalar")
        self.tbl_content = self._stats_table(
            ["Kontent", "Ochishlar"], "Eng ko'p ochilgan kontent")
        mid.addWidget(self.tbl_daily["card"], 1)
        mid.addWidget(self.tbl_content["card"], 1)
        lay.addLayout(mid, 1)

        bottom = QHBoxLayout()
        bottom.setSpacing(14)
        self.tbl_screens = self._stats_table(
            ["Bo'lim", "Kirishlar"], "Bo'limlar bo'yicha")
        self.tbl_langs = self._stats_table(
            ["Til", "Almashtirishlar"], "Til almashtirishlar")
        self.tbl_ads = self._stats_table(
            ["Reklama", "Namoyishlar"], "Reklama (proof-of-play)")
        bottom.addWidget(self.tbl_screens["card"], 1)
        bottom.addWidget(self.tbl_langs["card"], 1)
        bottom.addWidget(self.tbl_ads["card"], 1)
        lay.addLayout(bottom, 1)

        # Uchinchi qator: soatlik faollik, kiosk bo'yicha, QR/SOS xulosasi
        row3 = QHBoxLayout()
        row3.setSpacing(14)
        self.tbl_hours = self._stats_table(
            ["Soat", "Kirishlar"], "Soatlik faollik (gavjum vaqtlar)")
        self.tbl_kiosk = self._stats_table(
            ["Kiosk", "Sessiyalar"], "Kiosk bo'yicha")
        self.tbl_qrsos = self._stats_table(
            ["Amal", "Soni"], "QR va SOS")
        row3.addWidget(self.tbl_hours["card"], 1)
        row3.addWidget(self.tbl_kiosk["card"], 1)
        row3.addWidget(self.tbl_qrsos["card"], 1)
        lay.addLayout(row3, 1)
        return w

    def _stats_table(self, headers, title):
        """Sarlavhali karta ichida kichik jadval.
        {'card','table','title'} qaytaradi (title — sarlavha QLabel'i)."""
        card, clay = self._card(14)
        t = QLabel(title)
        t.setObjectName("cardTitle")
        clay.addWidget(t)
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self._setup_table(table)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        clay.addWidget(table, 1)
        return {"card": card, "table": table, "title": t}

    # ------------------------------------------------------------------
    def refresh_usage_stats(self):
        """Barcha statistika bloklari qayta o'qiladi (sahifa ochilganda va
        davr/Yangilash bosilganda)."""
        days = self.stats_period.currentData() or 7
        src = self.stats_source.currentData()   # None | 'kiosk' | 'web'
        try:
            totals = db.stats_totals(days, source=src)
            daily = db.stats_daily_sessions(days, source=src)
            top_content = db.stats_top("content_open", "title", days, source=src)
            top_screens = db.stats_top("screen_view", "screen", days, source=src)
            langs = db.stats_top("lang_change", "lang", days, source=src)
            ads = db.stats_top("ad_play", "title", days, limit=20, source=src)
            hours = db.stats_hourly(days, source=src)
            by_kiosk = db.stats_by_kiosk(days, source=src)
            daily_users = db.stats_daily_users(days, source="web")
            qr_n = db.stats_event_count("site_qr", days, source=src)
            sos_n = db.stats_event_count("sos_open", days, source=src)
            kiosks = {k["device_id"]: k for k in db.get_kiosks()}
        except Exception:
            # DB hali tayyor bo'lmasa (birinchi ochilish) — bo'sh qoldiramiz
            return
        for key, lbl in self._usage_lbls.items():
            lbl.setText(str(totals.get(key, 0)))
        # Manba=veb bo'lsa "devices" kartasi noyob foydalanuvchilarni bildiradi
        # (distinct device_id = noyob brauzer/telefon = unique visitors).
        web_mode = src == "web"
        self._usage_caps["devices"].setText(
            "Noyob foydalanuvchilar" if web_mode else "Faol kiosklar")
        self._fill(self.tbl_daily["table"],
                   [(r["day"], r["sessions"], r["avg_s"] or 0) for r in daily])
        self._fill(self.tbl_content["table"],
                   [(r["name"], r["n"]) for r in top_content])
        SCREEN_LABELS = {"home": "Asosiy", "map": "Xarita", "videos": "Videolar",
                         "books": "Kitoblar", "sites": "Saytlar"}
        self._fill(self.tbl_screens["table"],
                   [(SCREEN_LABELS.get(r["name"], r["name"]), r["n"])
                    for r in top_screens])
        self._fill(self.tbl_langs["table"],
                   [(str(r["name"]).upper(), r["n"]) for r in langs])
        self._fill(self.tbl_ads["table"], [(r["name"], r["n"]) for r in ads])
        # Soatlik faollik — "HH:00" ko'rinishida
        self._fill(self.tbl_hours["table"],
                   [(f"{r['hr']}:00", r["n"]) for r in hours])
        # Manba=veb: "Kiosk bo'yicha" jadval o'rniga "Kunlik noyob
        # foydalanuvchilar (DAU)" ko'rsatiladi — veb qurilma nomlari yo'q,
        # o'rniga kun bo'yicha noyob foydalanuvchilar foydaliroq.
        if web_mode:
            self.tbl_kiosk["title"].setText("Kunlik noyob foydalanuvchilar (DAU)")
            self.tbl_kiosk["table"].setHorizontalHeaderLabels(
                ["Kun", "Foydalanuvchilar"])
            self._fill(self.tbl_kiosk["table"],
                       [(r["day"], r["users"]) for r in daily_users])
        else:
            self.tbl_kiosk["title"].setText("Kiosk bo'yicha")
            self.tbl_kiosk["table"].setHorizontalHeaderLabels(
                ["Kiosk", "Sessiyalar"])
            # kiosk_no/xona bilan tushunarli yorliq (bo'lmasa ID)
            def _klabel(dev):
                k = kiosks.get(dev)
                if k and (k.get("kiosk_no") or k.get("room")):
                    parts = [p for p in (k.get("kiosk_no"), k.get("room")) if p]
                    return " / ".join(parts)
                return dev
            self._fill(self.tbl_kiosk["table"],
                       [(_klabel(r["dev"]), r["n"]) for r in by_kiosk])
        # QR va SOS — yagona ko'rsatkichlar
        self._fill(self.tbl_qrsos["table"],
                   [("Sayt QR ochildi", qr_n), ("SOS ochildi", sos_n)])

    def _reset_stats(self):
        """Barcha foydalanish statistikasini 0 ga tushiradi (tasdiqlash bilan)."""
        from PyQt6.QtWidgets import QMessageBox
        if QMessageBox.question(
                self, "Statistikani tozalash",
                "Barcha foydalanish statistikasi butunlay o'chiriladi va "
                "hisoblar 0 ga tushadi.\n\nBu amalni QAYTARIB BO'LMAYDI. "
                "Davom etilsinmi?") != QMessageBox.StandardButton.Yes:
            return
        try:
            db.clear_stats()
            db.log_action("stats_cleared", "all")
        except Exception:
            self.statusBar().showMessage("Statistikani tozalashda xato.", 4000)
            return
        self.refresh_usage_stats()
        self.statusBar().showMessage("Statistika tozalandi (0 ga tushdi).", 4000)

    @staticmethod
    def _fill(table, rows):
        table.setRowCount(len(rows))
        for r, vals in enumerate(rows):
            for c, val in enumerate(vals):
                item = QTableWidgetItem(str(val))
                if c > 0:
                    item.setForeground(Qt.GlobalColor.darkGray)
                table.setItem(r, c, item)
