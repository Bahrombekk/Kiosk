"""ui/pages/crud.py — Generik CRUD sahifalar mixin'i (Saytlar/Bekatlar)."""
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox
)
from PyQt6.QtGui import QColor

import db
from ui.styles import C_MUTED
from ui.helpers import _pill
from ui.dialogs import RecordDialog


class CrudPagesMixin:
    # ------------------------------------------------------------------
    #  Generik CRUD sahifa (Reklama / Saytlar / Bekatlar uchun umumiy)
    # ------------------------------------------------------------------
    def _crud_page(self, name, page_title, page_sub, columns, fields, get_all,
                   add_fn, update_fn, delete_fn, dialog_title, dialog_cls=None):
        """columns: [(header, key), ...]; fields: RecordDialog uchun maydonlar.
        dialog_cls berilsa — RecordDialog o'rniga maxsus dialog ishlatiladi
        (masalan reklama uchun AdDialog)."""
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
        table.setColumnWidth(0, 60)
        table.doubleClicked.connect(lambda: self._crud_edit(name))
        lay.addWidget(table, 1)

        count = QLabel("")
        count.setObjectName("hint")
        lay.addWidget(count)

        self._crud[name] = dict(
            table=table, columns=columns, fields=fields, get_all=get_all,
            add=add_fn, update=update_fn, delete=delete_fn,
            title=dialog_title, count=count, dialog_cls=dialog_cls)
        self._crud_refresh(name)
        return w

    def _crud_refresh(self, name):
        cfg = self._crud[name]
        items = cfg["get_all"]()
        cfg["rows"] = items
        table = cfg["table"]
        table.setRowCount(0)   # oldingi badge widgetlar ham tozalanadi
        table.setRowCount(len(items))
        for r, it in enumerate(items):
            for col, (_h, key) in enumerate(cfg["columns"]):
                val = it.get(key)
                if key == "is_active":
                    if val:
                        table.setItem(r, col, QTableWidgetItem(""))
                        table.setCellWidget(
                            r, col, _pill("Faol", "#047857", "#D1FAE5"))
                    else:
                        dash = QTableWidgetItem("—")
                        dash.setForeground(QColor("#94A3B8"))
                        table.setItem(r, col, dash)
                    continue
                item = QTableWidgetItem("" if val is None else str(val))
                if key == "id":
                    item.setForeground(QColor(C_MUTED))
                table.setItem(r, col, item)
        cfg["count"].setText(f"Jami: {len(items)} ta")

    def _crud_selected(self, name):
        cfg = self._crud[name]
        row = cfg["table"].currentRow()
        if row < 0 or row >= len(cfg.get("rows", [])):
            return None
        return cfg["rows"][row]

    def _crud_add(self, name):
        cfg = self._crud[name]
        if cfg.get("dialog_cls"):
            dlg = cfg["dialog_cls"](self)
        else:
            dlg = RecordDialog(self, f"Yangi: {cfg['title']}", cfg["fields"])
        if dlg.exec():
            cfg["add"](dlg.values())
            db.log_action(f"{name}_added")
            self._crud_refresh(name)
            self.statusBar().showMessage("Yozuv qo'shildi.", 3000)

    def _crud_edit(self, name):
        cfg = self._crud[name]
        item = self._crud_selected(name)
        if item is None:
            QMessageBox.information(self, "Eslatma", "Avval qatorni tanlang.")
            return
        if cfg.get("dialog_cls"):
            dlg = cfg["dialog_cls"](self, item)
        else:
            dlg = RecordDialog(self, f"Tahrirlash: {cfg['title']}",
                               cfg["fields"], item)
        if dlg.exec():
            cfg["update"](item["id"], dlg.values())
            db.log_action(f"{name}_updated", f"#{item['id']}")
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
            db.log_action(f"{name}_deleted", f"#{item['id']}")
            self._crud_refresh(name)
            self.statusBar().showMessage("Yozuv o'chirildi.", 3000)

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
                     ("Jo'nash", "departure_time"), ("Km", "distance_km"),
                     ("Kenglik", "latitude"), ("Uzunlik", "longitude"), ("Tartib", "sort_order")],
            fields=[("name", "Bekat nomi", "text"),
                    ("arrival_time", "Kelish vaqti (HH:MM)", "text"),
                    ("departure_time", "Jo'nash vaqti (HH:MM)", "text"),
                    ("distance_km", "Masofa (km, boshlang'ich bekatdan)", "int"),
                    ("latitude", "Kenglik (lat)", "float"),
                    ("longitude", "Uzunlik (lng)", "float"),
                    ("sort_order", "Tartib raqami", "int")],
            get_all=db.get_route,
            add_fn=db.add_route_stop, update_fn=db.update_route_stop,
            delete_fn=db.delete_route_stop,
            dialog_title="bekat")
