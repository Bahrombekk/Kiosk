"""ui/pages/content.py — Kontent sahifasi mixin'i (tur tablari + to'r)."""
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea
)
from PyQt6.QtCore import Qt

import db
from icons import svg_icon
from ui.styles import CONTENT_TYPES, TYPE_LABELS, C_MUTED
from ui.cards import CARD_W, AdminContentCard, CardFlow
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

        # Qidiruv (yozish bilanoq ro'yxat filtlanadi)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Qidirish: nomi, muallif, janr...")
        self.search.setClearButtonEnabled(True)
        self.search.addAction(svg_icon("search", C_MUTED, 32),
                              QLineEdit.ActionPosition.LeadingPosition)
        self.search.setFixedWidth(280)
        self.search.textChanged.connect(self.refresh_content)
        bar.addWidget(self.search)
        lay.addLayout(bar)

        # Tur tablari: Barchasi / Kino / Multfilm / Musiqa / Kitob / Audiokitob
        # (kioskdagi Videolar tablari kabi — bo'limlardan qulayroq)
        tabs = QHBoxLayout()
        tabs.setSpacing(8)
        self._ctype = None
        self._ctype_btns = {}
        for key, label in ([(None, "Barchasi")]
                           + [(t, TYPE_LABELS[t]) for t in CONTENT_TYPES]):
            b = QPushButton(label)
            b.setObjectName("typeTab")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _c, k=key: self._set_ctype(k))
            self._ctype_btns[key] = b
            tabs.addWidget(b)
        tabs.addStretch(1)
        self._ctype_btns[None].setChecked(True)
        lay.addLayout(tabs)

        # Kartochkalar to'ri (umumiy scroll ichida)
        self.cards_scroll = QScrollArea()
        self.cards_scroll.setObjectName("plainScroll")
        self.cards_scroll.setWidgetResizable(True)
        self.cards_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.cards_flow = CardFlow(CARD_W)
        self.cards_scroll.setWidget(self.cards_flow)
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

    def _set_ctype(self, key):
        """Tur tabini almashtiradi (None = Barchasi)."""
        self._ctype = key
        for k, b in self._ctype_btns.items():
            b.setChecked(k == key)
        self.refresh_content()

    def _recheck_cols(self):
        """Oyna kengligi o'zgarganda to'rni qayta teradi
        (window.resizeEvent va sahifaga o'tishda chaqiriladi)."""
        if hasattr(self, "cards_flow"):
            self.cards_flow._recheck()

    def refresh_content(self):
        query = (self.search.text() if hasattr(self, "search") else "").lower().strip()
        items = db.get_content()
        if query:
            items = [it for it in items
                     if query in " ".join(str(it.get(k) or "").lower()
                                          for k in ("title", "author", "genre"))]
        # Tab yorliqlarida joriy (qidiruvga mos) sonlar ko'rinadi
        counts = {}
        for it in items:
            counts[it.get("type")] = counts.get(it.get("type"), 0) + 1
        self._ctype_btns[None].setText(f"Barchasi ({len(items)})")
        for t in CONTENT_TYPES:
            self._ctype_btns[t].setText(
                f"{TYPE_LABELS[t]} ({counts.get(t, 0)})")
        if self._ctype:
            items = [it for it in items if it["type"] == self._ctype]
        self.cards_flow.set_cards(
            AdminContentCard(it, self.edit_content, self.delete_content)
            for it in items)
        self.content_empty.setVisible(not items)
        self.content_count.setText(f"Jami: {len(items)} ta")

    LANG_NAMES = {"uz": "o'zbekcha", "ru": "ruscha", "en": "inglizcha"}

    def add_content(self):
        dlg = ContentDialog(self)
        if dlg.exec():
            vals = dlg.values()
            new_id = db.add_content(vals)
            db.log_action("content_added", f"#{new_id} {vals.get('title')!r}")
            self.refresh_content()
            self._broadcast_sync("content")
            self.statusBar().showMessage("Kontent qo'shildi.", 3000)
            self._offer_translations(new_id, vals)

    def _offer_translations(self, base_id, vals):
        """Tilli kontent saqlangach, qolgan tillardagi versiyalarini ham
        yuklashni taklif qiladi. Versiyalar bitta lang_group'ga bog'lanadi —
        kioskda joriy tilga mosi ko'rinadi."""
        if vals.get("lang") not in ("uz", "ru", "en"):
            return   # "Barcha tillarda" — versiyalar shart emas
        db.update_content(base_id, {"lang_group": base_id})
        for code in ("uz", "ru", "en"):
            if code == vals["lang"]:
                continue
            if QMessageBox.question(
                    self, "Til versiyasi",
                    f"«{vals.get('title')}» kontentining "
                    f"{self.LANG_NAMES[code]} versiyasini ham yuklaysizmi?") \
                    != QMessageBox.StandardButton.Yes:
                continue
            # Dialog umumiy maydonlar oldindan to'ldirilgan holda ochiladi —
            # admin faqat fayl (va kerak bo'lsa tarjima nomi) kiritadi.
            tmpl = {k: vals.get(k) for k in
                    ("type", "title", "author", "genre", "category_tab",
                     "description", "cover_path")}
            tmpl["lang"] = code
            tmpl["lang_group"] = base_id
            vdlg = ContentDialog(self, tmpl)
            if not vdlg.exec():
                continue
            vvals = vdlg.values()
            vvals["lang_group"] = base_id
            # Yangi muqova tanlanmagan bo'lsa asl muqova ulashiladi
            vvals.setdefault("cover_path", vals.get("cover_path"))
            nid = db.add_content(vvals)
            db.log_action("content_added",
                          f"#{nid} {vvals.get('title')!r} ({code})")
        self.refresh_content()
        self._broadcast_sync("content")

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
            self._broadcast_sync("content")
            self.statusBar().showMessage("Kontent yangilandi.", 3000)

    def delete_content(self, item):
        if QMessageBox.question(
                self, "Tasdiqlang",
                f"«{item.get('title', '')}» o'chirilsinmi?") \
                == QMessageBox.StandardButton.Yes:
            db.delete_content(item["id"])
            db.log_action("content_deleted", f"#{item['id']}")
            self.refresh_content()
            self._broadcast_sync("content")
            self.statusBar().showMessage("Kontent o'chirildi.", 3000)
