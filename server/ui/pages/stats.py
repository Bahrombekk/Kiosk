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
        top.addWidget(self._btn("Yangilash", "refresh-cw",
                                self.refresh_usage_stats, kind="ghost"))
        top.addStretch(1)
        lay.addLayout(top)

        # Umumiy hisob kartalari
        cards = QHBoxLayout()
        cards.setSpacing(14)
        self._usage_lbls = {}
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
        return w

    def _stats_table(self, headers, title):
        """Sarlavhali karta ichida kichik jadval. {'card','table'} qaytaradi."""
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
        return {"card": card, "table": table}

    # ------------------------------------------------------------------
    def refresh_usage_stats(self):
        """Barcha statistika bloklari qayta o'qiladi (sahifa ochilganda va
        davr/Yangilash bosilganda)."""
        days = self.stats_period.currentData() or 7
        try:
            totals = db.stats_totals(days)
            daily = db.stats_daily_sessions(days)
            top_content = db.stats_top("content_open", "title", days)
            top_screens = db.stats_top("screen_view", "screen", days)
            langs = db.stats_top("lang_change", "lang", days)
            ads = db.stats_top("ad_play", "title", days, limit=20)
        except Exception:
            # DB hali tayyor bo'lmasa (birinchi ochilish) — bo'sh qoldiramiz
            return
        for key, lbl in self._usage_lbls.items():
            lbl.setText(str(totals.get(key, 0)))
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

    @staticmethod
    def _fill(table, rows):
        table.setRowCount(len(rows))
        for r, vals in enumerate(rows):
            for c, val in enumerate(vals):
                item = QTableWidgetItem(str(val))
                if c > 0:
                    item.setForeground(Qt.GlobalColor.darkGray)
                table.setItem(r, c, item)
