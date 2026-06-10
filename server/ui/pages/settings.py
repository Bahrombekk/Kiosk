"""ui/pages/settings.py — Sozlamalar sahifasi mixin'i."""
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QFormLayout, QLineEdit, QMessageBox, QSpinBox
)

import db


class SettingsPageMixin:
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
        self.s_ad_int = QSpinBox()
        self.s_ad_int.setRange(1, 180)
        self.s_ad_int.setValue(5)
        self.s_ad_int.setSuffix(" daqiqa")
        form.addRow("Vagon raqami:", self.s_wagon)
        form.addRow("Vagon izohi:", self.s_wagon_note)
        form.addRow("Poyezd nomi:", self.s_train)
        form.addRow("Yo'nalish:", self.s_route)
        form.addRow("Jo'nash vaqti:", self.s_depart)
        form.addRow("Reklama oralig'i:", self.s_ad_int)
        clay.addLayout(form)
        ad_hint = QLabel("Reklama oralig'i — standart qiymat: o'z oralig'i "
                         "belgilanmagan reklamalar shu chastotada chiqadi "
                         "(har reklamaga alohida oraliqni Reklama bo'limida "
                         "qo'yish mumkin).")
        ad_hint.setObjectName("hint")
        clay.addWidget(ad_hint)

        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self._btn("Saqlash", "save", self.save_settings))
        clay.addLayout(row)

        lay.addWidget(card)

        # --- Xavfsizlik kartasi: kiosk chiqish PIN + admin parolini almashtirish ---
        sec_card, sec_lay = self._card(22)
        sec_title = QLabel("Xavfsizlik")
        sec_title.setObjectName("cardTitle")
        sec_lay.addWidget(sec_title)
        sec_form = QFormLayout()
        sec_form.setSpacing(12)
        self.s_pin = QLineEdit()
        self.s_pin.setEchoMode(QLineEdit.EchoMode.Password)
        self.s_pin.setPlaceholderText("Yangi PIN (4-8 raqam, bo'sh = o'zgarmaydi)")
        sec_form.addRow("Kiosk chiqish PIN-kodi:", self.s_pin)
        self.s_admin_old = QLineEdit()
        self.s_admin_old.setEchoMode(QLineEdit.EchoMode.Password)
        self.s_admin_new = QLineEdit()
        self.s_admin_new.setEchoMode(QLineEdit.EchoMode.Password)
        self.s_admin_new.setPlaceholderText("Kamida 8 belgi (bo'sh = o'zgarmaydi)")
        sec_form.addRow("Joriy admin parol:", self.s_admin_old)
        sec_form.addRow("Yangi admin parol:", self.s_admin_new)
        sec_lay.addLayout(sec_form)
        sec_hint = QLabel("PIN kioskka serverdan yetkaziladi (kiosk uni xesh "
                          "ko'rinishida keshlaydi, oflaynda ham ishlaydi).")
        sec_hint.setObjectName("hint")
        sec_lay.addWidget(sec_hint)
        sec_row = QHBoxLayout()
        sec_row.addStretch(1)
        sec_row.addWidget(self._btn("Xavfsizlikni saqlash", "save",
                                    self.save_security))
        sec_lay.addLayout(sec_row)
        lay.addWidget(sec_card)
        lay.addStretch(1)
        return w

    def load_settings(self):
        s = db.get_settings()
        self.s_wagon.setText(s.get("wagon_number", ""))
        self.s_wagon_note.setText(s.get("wagon_note", ""))
        self.s_train.setText(s.get("train_name", ""))
        self.s_route.setText(s.get("route", ""))
        self.s_depart.setText(s.get("depart_time", ""))
        try:
            self.s_ad_int.setValue(int(float(s.get("ad_interval_min") or 5)))
        except (TypeError, ValueError):
            self.s_ad_int.setValue(5)

    def save_settings(self):
        import re
        wagon = self.s_wagon.text().strip()
        if wagon and not wagon.isdigit():
            QMessageBox.warning(self, "Xato",
                                "Vagon raqami faqat raqamlardan iborat bo'lsin.")
            return
        depart = self.s_depart.text().strip()
        if depart and not re.fullmatch(r"\d{1,2}:\d{2}", depart):
            QMessageBox.warning(self, "Xato",
                                "Jo'nash vaqti HH:MM ko'rinishida bo'lsin "
                                "(masalan 08:00).")
            return
        db.set_setting("wagon_number", wagon)
        db.set_setting("wagon_note", self.s_wagon_note.text())
        db.set_setting("train_name", self.s_train.text())
        db.set_setting("route", self.s_route.text())
        db.set_setting("depart_time", depart)
        db.set_setting("ad_interval_min", str(self.s_ad_int.value()))
        db.log_action("settings_saved",
                      f"train={self.s_train.text()!r} wagon={wagon!r}")
        self.statusBar().showMessage("Sozlamalar saqlandi.", 3000)

    def save_security(self):
        """Kiosk PIN va/yoki admin parolini yangilaydi (faqat xesh saqlanadi)."""
        pin = self.s_pin.text().strip()
        new_pw = self.s_admin_new.text()
        if not pin and not new_pw:
            QMessageBox.information(self, "Eslatma",
                                    "O'zgartirish uchun PIN yoki yangi parol kiriting.")
            return
        if pin:
            if not (pin.isdigit() and 4 <= len(pin) <= 8):
                QMessageBox.warning(self, "Xato",
                                    "PIN 4-8 ta raqamdan iborat bo'lishi kerak.")
                return
            db.set_setting("exit_pin_hash", db.hash_secret(pin))
            db.log_action("exit_pin_changed")
        if new_pw:
            stored = db.get_settings().get("admin_password_hash")
            if stored and not db.verify_secret(self.s_admin_old.text(), stored):
                QMessageBox.warning(self, "Xato", "Joriy admin parol noto'g'ri.")
                return
            if len(new_pw) < 8:
                QMessageBox.warning(self, "Xato",
                                    "Yangi parol kamida 8 belgi bo'lsin.")
                return
            db.set_setting("admin_password_hash", db.hash_secret(new_pw))
            db.log_action("admin_password_changed")
        self.s_pin.clear()
        self.s_admin_old.clear()
        self.s_admin_new.clear()
        self.statusBar().showMessage("Xavfsizlik sozlamalari saqlandi.", 3000)
