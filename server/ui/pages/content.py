"""ui/pages/content.py — Kontent sahifasi mixin'i (kartochkalar to'ri)."""
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QLineEdit, QComboBox, QMessageBox,
    QFrame, QScrollArea, QGridLayout
)
from PyQt6.QtCore import Qt, QTimer

import db
from icons import svg_icon
from ui.styles import CONTENT_TYPES, TYPE_LABELS, C_MUTED
from ui.cards import CARD_W, AdminContentCard
from ui.dialogs import ContentDialog


class ContentPageMixin:
    # ------------------------------------------------------------------
    #  Kontent sahifasi (qidiruv + tur filtri bilan)
    # ------------------------------------------------------------------
    def _content_page(self):
        w, lay = self._page("Kontent",
                            "Kino, multfilm, musiqa, kitob va audiokitoblar")

        bar = QHBoxLayout()
        bar.setSpacing(8)
        bar.addWidget(self._btn("Qo'shish", "plus", self.add_content))
        bar.addWidget(self._btn("Yangilash", "refresh-cw",
                                self.refresh_content, "ghost"))
        bar.addStretch(1)

        # Tur filtri + qidiruv (yozish bilanoq ro'yxat filtlanadi)
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
        self.search.setFixedWidth(280)
        self.search.textChanged.connect(self.refresh_content)
        bar.addWidget(self.type_filter)
        bar.addWidget(self.search)
        lay.addLayout(bar)

        # Kartochkalar to'ri (scroll ichida) — user ilovadagi videolar kabi
        self.cards_scroll = QScrollArea()
        self.cards_scroll.setWidgetResizable(True)
        self.cards_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.cards_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.cards_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }")
        host = QWidget()
        host.setStyleSheet("background: transparent;")
        self.cards_grid = QGridLayout(host)
        self.cards_grid.setContentsMargins(0, 4, 0, 12)
        self.cards_grid.setHorizontalSpacing(14)
        self.cards_grid.setVerticalSpacing(14)
        self.cards_grid.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.cards_scroll.setWidget(host)
        self.cards_scroll.viewport().setStyleSheet("background: transparent;")
        lay.addWidget(self.cards_scroll, 1)

        self.content_empty = QLabel(
            "Hech narsa topilmadi — «Qo'shish» orqali kontent kiriting "
            "yoki filtr/qidiruvni o'zgartiring.")
        self.content_empty.setStyleSheet("color: #94A3B8; padding: 6px 2px;")
        self.content_empty.hide()
        lay.addWidget(self.content_empty)

        self.content_count = QLabel("")
        self.content_count.setObjectName("hint")
        lay.addWidget(self.content_count)
        return w

    def _content_cols(self):
        """Oyna kengligiga qarab kartochka ustunlari soni."""
        avail = self.cards_scroll.viewport().width()
        if avail <= 0:
            avail = self.width() - 232 - 60   # sidebar + page padding taxmini
        sp = self.cards_grid.horizontalSpacing()
        return max(1, (avail + sp) // (CARD_W + sp))

    def _regrid_cards(self):
        """Mavjud kartalarni joriy ustun soniga teradi (qayta yaratmasdan).

        Har katak AlignTop|AlignLeft bilan qo'yiladi — grid bo'sh balandlikni
        kartalarga taqsimlab ularni cho'zib yubormasin. Oxirgi ustun/qatordan
        keyin stretch qo'yiladi — kartalar chap-tepada zich tursin."""
        g = self.cards_grid
        cols = self._content_cols()
        self._cards_cols = cols
        for i, card in enumerate(self._cards):
            g.addWidget(card, i // cols, i % cols,
                        Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        # Avvalgi (boshqa ustun sonidagi) stretchlarni nollab, yangisini qo'yamiz
        rows = (len(self._cards) + cols - 1) // cols
        for c in range(g.columnCount() + 1):
            g.setColumnStretch(c, 0)
        for r in range(g.rowCount() + 1):
            g.setRowStretch(r, 0)
        g.setColumnStretch(cols, 1)
        g.setRowStretch(rows, 1)

    def _recheck_cols(self):
        """Layout o'rnashgandan keyin ustun sonini qayta tekshiradi.
        (resize/birinchi ochilish paytida viewport kengligi hali yakuniy emas.)"""
        if getattr(self, "_cards", None) and \
                self._content_cols() != getattr(self, "_cards_cols", 0):
            self._regrid_cards()

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
        # Eski kartochkalarni tozalab, yangilarini teramiz
        while self.cards_grid.count():
            old = self.cards_grid.takeAt(0).widget()
            if old:
                old.deleteLater()
        self._cards = []
        for it in items:
            self._cards.append(
                AdminContentCard(it, self.edit_content, self.delete_content))
        self._regrid_cards()
        QTimer.singleShot(0, self._recheck_cols)
        self.content_empty.setVisible(not items)
        self.content_count.setText(f"Jami: {len(items)} ta")

    def add_content(self):
        dlg = ContentDialog(self)
        if dlg.exec():
            vals = dlg.values()
            new_id = db.add_content(vals)
            db.log_action("content_added", f"#{new_id} {vals.get('title')!r}")
            self.refresh_content()
            self.statusBar().showMessage("Kontent qo'shildi.", 3000)

    def edit_content(self, item):
        cid = item["id"]
        item = db.get_content_by_id(cid)
        if item is None:
            self.refresh_content()
            return
        dlg = ContentDialog(self, item)
        if dlg.exec():
            db.update_content(cid, dlg.values())
            db.log_action("content_updated", f"#{cid}")
            self.refresh_content()
            self.statusBar().showMessage("Kontent yangilandi.", 3000)

    def delete_content(self, item):
        if QMessageBox.question(
                self, "Tasdiqlang",
                f"«{item.get('title', '')}» o'chirilsinmi?") \
                == QMessageBox.StandardButton.Yes:
            db.delete_content(item["id"])
            db.log_action("content_deleted", f"#{item['id']}")
            self.refresh_content()
            self.statusBar().showMessage("Kontent o'chirildi.", 3000)
