"""ui/pages/settings.py — Sozlamalar sahifasi mixin'i.

Dizayn: mavzu bo'yicha alohida kartalar (Poyezd / Reklama / Zastavka / SOS /
Xavfsizlik), har birida ikonkali sarlavha. Yorliqlar maydon USTIDA (2 ustunli
grid). Butun tarkib QScrollArea ichida — kichik oynada ham hech narsa
ustma-ust chiqmaydi, shunchaki aylantiriladi.
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPlainTextEdit, QScrollArea, QSpinBox, QVBoxLayout, QWidget
)

import db
from icons import svg_pixmap
from ui.helpers import no_wheel
from ui.toggle import ToggleSwitch

# SOS oynasining standart raqamlari (kiosk i18n bilan 3 tilda ko'rsatadi).
# Admin maydoni bo'sh bo'lsa shu ro'yxat ko'rsatiladi; admin matnni aynan
# shu holicha qoldirsa ham bazaga yozilmaydi — 3 til saqlanib qoladi.
DEFAULT_SOS = ("112 - Yagona qutqaruv xizmati\n"
               "101 - Yong'in xizmati\n"
               "102 - Politsiya\n"
               "103 - Tez tibbiy yordam")


class SettingsPageMixin:
    # --- Qurilish bloklari (faqat shu sahifa uchun) ---
    def _sec_card(self, icon, bg, fg, title, sub):
        """Ikonkali sarlavhasi bor sozlama kartasi: rangli plitka + nom + izoh."""
        card, clay = self._card(20)
        head = QHBoxLayout()
        head.setSpacing(12)
        ic = QLabel()
        ic.setFixedSize(40, 40)
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic.setPixmap(svg_pixmap(icon, fg, 20))
        ic.setStyleSheet(f"background: {bg}; border-radius: 12px;")
        tcol = QVBoxLayout()
        tcol.setSpacing(1)
        tl = QLabel(title)
        tl.setObjectName("secTitle")
        sl = QLabel(sub)
        sl.setObjectName("secSub")
        sl.setWordWrap(True)
        tcol.addWidget(tl)
        tcol.addWidget(sl)
        head.addWidget(ic)
        head.addLayout(tcol, 1)
        clay.addLayout(head)
        clay.addSpacing(4)
        return card, clay

    @staticmethod
    def _field(label, widget):
        """Yorliq maydon USTIDA turadigan zamonaviy forma katagi."""
        box = QVBoxLayout()
        box.setSpacing(6)
        lbl = QLabel(label)
        lbl.setObjectName("fieldLbl")
        box.addWidget(lbl)
        box.addWidget(widget)
        return box

    # --- Sozlamalar sahifasi ---
    def _settings_page(self):
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(26, 22, 26, 20)
        outer.setSpacing(14)

        # Sarlavha qatori: nom + umumiy "Saqlash" (o'ng yuqorida, doim ko'rinadi)
        hrow = QHBoxLayout()
        tcol = QVBoxLayout()
        tcol.setSpacing(2)
        t = QLabel("Sozlamalar")
        t.setObjectName("pageTitle")
        s = QLabel("Poyezd, reklama, zastavka va SOS sozlamalari")
        s.setObjectName("pageSub")
        tcol.addWidget(t)
        tcol.addWidget(s)
        hrow.addLayout(tcol)
        hrow.addStretch(1)
        hrow.addWidget(self._btn("Saqlash", "save", self.save_settings),
                       alignment=Qt.AlignmentFlag.AlignTop)
        outer.addLayout(hrow)

        # Butun tarkib scroll ichida — kichik oynada ustma-ust chiqmaydi
        scroll = QScrollArea()
        scroll.setObjectName("plainScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        ilay = QVBoxLayout(inner)
        ilay.setContentsMargins(0, 0, 6, 0)   # o'ngda scrollbar'ga joy
        ilay.setSpacing(14)

        # === 1) Poyezd ma'lumotlari ===
        card, clay = self._sec_card(
            "train-front", "#EFF6FF", "#2563EB", "Poyezd ma'lumotlari",
            "Asosiy ekran va xarita sahifasida ko'rinadi")
        self.s_train = QLineEdit()
        self.s_train.setPlaceholderText("076Ф TOSHKENT — XIVA")
        self.s_route = QLineEdit()
        self.s_route.setPlaceholderText("Toshkent → Samarqand")
        self.s_wagon = QLineEdit()
        self.s_wagon.setPlaceholderText("6")
        self.s_wagon_note = QLineEdit()
        self.s_wagon_note.setPlaceholderText("Restoran vagonning chap tarafida")
        self.s_depart = QLineEdit()
        self.s_depart.setPlaceholderText("08:00")
        self.s_location = QLineEdit()
        self.s_location.setPlaceholderText(
            "Masalan: 6-vagon, AFROSIYOB 764 (SOS oynasida ko'rinadi)")
        g = QGridLayout()
        g.setHorizontalSpacing(14)
        g.setVerticalSpacing(12)
        g.addLayout(self._field("Poyezd nomi", self.s_train), 0, 0)
        g.addLayout(self._field("Yo'nalish", self.s_route), 0, 1)
        g.addLayout(self._field("Vagon raqami", self.s_wagon), 1, 0)
        g.addLayout(self._field("Vagon izohi", self.s_wagon_note), 1, 1)
        g.addLayout(self._field("Jo'nash vaqti", self.s_depart), 2, 0)
        g.addLayout(self._field("Kiosk joylashuvi", self.s_location), 2, 1)
        clay.addLayout(g)
        ilay.addWidget(card)

        # === 2) Reklama ===
        card, clay = self._sec_card(
            "megaphone", "#FFF7ED", "#D97706", "Reklama",
            "Popup chastotasi va slotda qaysi reklama tanlanishi")
        self.s_ad_int = QSpinBox()
        self.s_ad_int.setRange(1, 180)
        self.s_ad_int.setValue(5)
        self.s_ad_int.setSuffix(" daqiqa")
        g = QGridLayout()
        g.setHorizontalSpacing(14)
        g.setVerticalSpacing(12)
        g.addLayout(self._field("Reklama oralig'i", self.s_ad_int), 0, 0)
        g.setColumnStretch(1, 1)   # oraliq chap chetda ixcham tursin
        clay.addLayout(g)
        # Sahifa scrollida g'ildirak qiymatni ADASHIB o'zgartirmasin
        no_wheel(self.s_ad_int)

        # Rejalashtirish algoritmlari — bir nechtasini birga tanlash mumkin
        # (qiymatlar user/services/ads.py bilan mos). Popup tanlash usullari
        # (Vaznli/Navbat/Tasodifiy) bir-birini istisno qiladi — bir nechtasi
        # belgilansa, kiosk prioritet bo'yicha birinchisini ishlatadi; «Media»
        # esa alohida joylashuv (kino atrofida), ularning ustiga qo'shiladi.
        self.s_ad_algos = {}
        algo_holder = QWidget()
        algo_box = QVBoxLayout(algo_holder)
        algo_box.setContentsMargins(0, 0, 0, 0)
        algo_box.setSpacing(8)
        for key, text in (
                ("weighted", "Vaznli — har reklamaning o'z oralig'i hisobga olinadi"),
                ("queue", "Navbat bilan — har oraliqda ro'yxatdagi keyingisi"),
                ("random", "Tasodifiy — har safar aralash tartibda"),
                ("media", "Media — kino boshida, o'rtasida va oxirida")):
            cb = QCheckBox(text)
            self.s_ad_algos[key] = cb
            algo_box.addWidget(cb)
        clay.addLayout(self._field(
            "Reklama algoritmlari (bir nechtasini tanlash mumkin)", algo_holder))
        ad_hint = QLabel(
            "Oraliq — popup chastotasi: har shu daqiqada BITTA reklama "
            "chiqadi. «Vaznli»da har reklamaning o'z oralig'i (Reklama "
            "bo'limida) vazn bo'lib xizmat qiladi; «Navbat bilan» va "
            "«Tasodifiy»da reklamalar teng aylanadi. Bu uchovidan bittasi "
            "ishlatiladi (bir nechtasi belgilansa — yuqoridagisi). «Media» "
            "alohida: reklama kino boshida, o'rtasida va oxirida ham "
            "ko'rsatiladi. «Media»ni popup usuli bilan birga belgilash mumkin.")
        ad_hint.setObjectName("hint")
        ad_hint.setWordWrap(True)   # MUHIM: aks holda oyna kichraymay qoladi
        clay.addWidget(ad_hint)
        ilay.addWidget(card)

        # === 3) Kiosk lokal keshi ===
        card, clay = self._sec_card(
            "server", "#EFF6FF", "#2563EB", "Kiosk lokal keshi",
            "Kontent fayllari kiosk diskiga fonda yuklab qo'yiladi — "
            "oflaynda ham ijro etiladi, serverga yuk kamayadi")
        # Yoqish/o'chirish — switch + holat yozuvi (yozuv switch holatiga qarab
        # yangilanadi). s_mcache.isChecked() -> "1"/"0" save'da.
        self.s_mcache = ToggleSwitch()
        self.s_mcache_lbl = QLabel()
        self.s_mcache.toggled.connect(self._update_mcache_lbl)
        sw_row = QHBoxLayout()
        sw_row.setSpacing(12)
        sw_row.addWidget(self.s_mcache)
        sw_row.addWidget(self.s_mcache_lbl)
        sw_row.addStretch(1)
        sw_holder = QWidget()
        sw_holder.setLayout(sw_row)
        sw_row.setContentsMargins(0, 0, 0, 0)
        clay.addLayout(self._field("Lokal media kesh", sw_holder))

        # Kesh hajmi cheklovi — kiosk diskidan eng ko'pi shuncha GB band qiladi
        # (0 = cheklov yo'q, faqat bo'sh joy bo'yicha). Kiosk media_cache.py
        # shu chegaradan oshmaydi.
        self.s_cache_limit = QSpinBox()
        self.s_cache_limit.setRange(0, 2000)
        self.s_cache_limit.setSuffix(" GB")
        self.s_cache_limit.setSpecialValueText("Cheklov yo'q")
        no_wheel(self.s_cache_limit)
        g = QGridLayout()
        g.setHorizontalSpacing(14)
        g.addLayout(self._field("Kesh hajmi cheklovi", self.s_cache_limit), 0, 0)
        g.setColumnStretch(1, 1)
        clay.addLayout(g)

        mc_hint = QLabel(
            "O'chirilganda kioskdagi yuklab olingan fayllar o'chmaydi — "
            "faqat yangi yuklash to'xtaydi. Kesh hajmi cheklovi — kiosk "
            "diskidan eng ko'pi shuncha GB band qilinadi (0 = faqat bo'sh joy "
            "bo'yicha). Har kioskda qancha yuklangani Boshqaruv sahifasidagi "
            "jadvalda ko'rinadi (qatorga ikki marta bosing).")
        mc_hint.setObjectName("hint")
        mc_hint.setWordWrap(True)
        clay.addWidget(mc_hint)

        # Masofadan tozalash — barcha onlayn kiosklarga "keshni tozala" buyrug'i
        clr_row = QHBoxLayout()
        clr_row.addStretch(1)
        clr_row.addWidget(self._btn("Barcha kiosklar keshini tozalash",
                                    "trash-2", self.clear_all_cache,
                                    kind="ghost"))
        clay.addLayout(clr_row)
        ilay.addWidget(card)

        # === 4) SOS (favqulodda) ===
        card, clay = self._sec_card(
            "phone", "#FEF2F2", "#DC2626", "SOS — favqulodda raqamlar",
            "Kiosk navbar'idagi qizil SOS tugmasi va uning oynasi")
        self.s_sos_on = QComboBox()
        self.s_sos_on.addItem("Ko'rsatilsin — navbar'da SOS tugmasi chiqadi", "1")
        self.s_sos_on.addItem("Ko'rsatilmasin — kioskda SOS umuman bo'lmaydi", "0")
        self.s_sos = QPlainTextEdit()
        self.s_sos.setPlaceholderText(
            "Har qatorda bittadan, \"RAQAM - Tavsif\" ko'rinishida:\n"
            "112 - Yagona qutqaruv xizmati\n"
            "1005 - Temir yo'l ma'lumot xizmati")
        self.s_sos.setFixedHeight(110)
        no_wheel(self.s_sos_on)   # scroll paytida adashib o'zgarmasin
        clay.addLayout(self._field("SOS tugmasi kioskda", self.s_sos_on))
        clay.addLayout(self._field("Raqamlar ro'yxati", self.s_sos))
        sos_hint = QLabel(
            "Standart ro'yxat o'zgartirilmasa kioskda 3 tilda (UZ/RU/EN) "
            "ko'rsatiladi; o'zgartirilsa — kiritilgan matn barcha tillarda "
            "bir xil chiqadi.")
        sos_hint.setObjectName("hint")
        sos_hint.setWordWrap(True)
        clay.addWidget(sos_hint)
        ilay.addWidget(card)

        # === 5) Xavfsizlik ===
        card, clay = self._sec_card(
            "lock", "#F0FDF4", "#16A34A", "Xavfsizlik",
            "Kiosk chiqish PIN-kodi va admin parolini almashtirish")
        self.s_pin = QLineEdit()
        self.s_pin.setEchoMode(QLineEdit.EchoMode.Password)
        self.s_pin.setPlaceholderText("4-8 raqam (bo'sh = o'zgarmaydi)")
        self.s_admin_old = QLineEdit()
        self.s_admin_old.setEchoMode(QLineEdit.EchoMode.Password)
        self.s_admin_new = QLineEdit()
        self.s_admin_new.setEchoMode(QLineEdit.EchoMode.Password)
        self.s_admin_new.setPlaceholderText("Kamida 8 belgi (bo'sh = o'zgarmaydi)")
        g = QGridLayout()
        g.setHorizontalSpacing(14)
        g.setVerticalSpacing(12)
        g.addLayout(self._field("Kiosk chiqish PIN-kodi", self.s_pin), 0, 0)
        g.addLayout(self._field("Joriy admin parol", self.s_admin_old), 1, 0)
        g.addLayout(self._field("Yangi admin parol", self.s_admin_new), 1, 1)
        clay.addLayout(g)
        sec_hint = QLabel("PIN kioskka serverdan yetkaziladi (kiosk uni xesh "
                          "ko'rinishida keshlaydi, oflaynda ham ishlaydi).")
        sec_hint.setObjectName("hint")
        sec_hint.setWordWrap(True)
        clay.addWidget(sec_hint)
        sec_row = QHBoxLayout()
        sec_row.addStretch(1)
        sec_row.addWidget(self._btn("Xavfsizlikni saqlash", "save",
                                    self.save_security))
        clay.addLayout(sec_row)
        ilay.addWidget(card)

        ilay.addStretch(1)
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)
        return w

    def load_settings(self):
        s = db.get_settings()
        self.s_wagon.setText(s.get("wagon_number", ""))
        self.s_wagon_note.setText(s.get("wagon_note", ""))
        self.s_train.setText(s.get("train_name", ""))
        self.s_route.setText(s.get("route", ""))
        self.s_depart.setText(s.get("depart_time", ""))
        self.s_location.setText(s.get("kiosk_location", ""))
        # Bo'sh bo'lsa standart ro'yxat ko'rsatiladi — admin hozir nima
        # chiqayotganini ko'rib, shu yerda tahrirlaydi.
        self.s_sos.setPlainText(s.get("sos_numbers", "").strip() or DEFAULT_SOS)
        idx = self.s_sos_on.findData(s.get("sos_enabled") or "0")
        self.s_sos_on.setCurrentIndex(max(0, idx))
        self.s_mcache.setChecked(str(s.get("media_cache") or "1") != "0")
        self._update_mcache_lbl(self.s_mcache.isChecked())
        try:
            self.s_cache_limit.setValue(int(float(s.get("cache_limit_gb") or 0)))
        except (TypeError, ValueError):
            self.s_cache_limit.setValue(0)
        try:
            self.s_ad_int.setValue(int(float(s.get("ad_interval_min") or 5)))
        except (TypeError, ValueError):
            self.s_ad_int.setValue(5)
        # Algoritmlar vergul bilan saqlanadi; eski yagona qiymat ham mos keladi.
        sel = {x.strip() for x in (s.get("ad_algorithm") or "").split(",")
               if x.strip()} or {"weighted"}
        for key, cb in self.s_ad_algos.items():
            cb.setChecked(key in sel)

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
        algos = [k for k, cb in self.s_ad_algos.items() if cb.isChecked()]
        db.set_setting("ad_algorithm", ",".join(algos) or "weighted")
        db.set_setting("kiosk_location", self.s_location.text().strip())
        # Standart ro'yxat o'zgartirilmagan bo'lsa bo'sh saqlanadi — kiosk
        # uni i18n orqali 3 tilda ko'rsatishda davom etadi.
        sos_txt = self.s_sos.toPlainText().strip()
        db.set_setting("sos_numbers", "" if sos_txt == DEFAULT_SOS else sos_txt)
        db.set_setting("sos_enabled", self.s_sos_on.currentData())
        db.set_setting("media_cache", "1" if self.s_mcache.isChecked() else "0")
        db.set_setting("cache_limit_gb", str(self.s_cache_limit.value()))
        db.log_action("settings_saved",
                      f"train={self.s_train.text()!r} wagon={wagon!r}")
        self._broadcast_sync("settings")
        self.statusBar().showMessage("Sozlamalar saqlandi.", 3000)

    @staticmethod
    def _update_mcache_lbl_text(on):
        return ("Yoqilgan — xotirasi yetgan kiosk fonda yuklab oladi" if on
                else "O'chirilgan — faqat serverdan striming")

    def _update_mcache_lbl(self, on):
        self.s_mcache_lbl.setText(self._update_mcache_lbl_text(on))

    def clear_all_cache(self):
        """Barcha onlayn kiosklarga lokal keshini tozalash buyrug'ini yuboradi.
        Kesh yoqiq qolsa kiosk keyingi sinxda fayllarni qaytadan yuklaydi."""
        import ws
        n = len(ws.manager.clients())
        if QMessageBox.question(
                self, "Keshni tozalash",
                f"Barcha kiosklar ({n} ta onlayn) lokal media keshi "
                "o'chirilsinmi?\n\nKesh yoqiq bo'lsa fayllar keyingi sinxda "
                "qaytadan yuklanadi.") != QMessageBox.StandardButton.Yes:
            return
        ws.manager.broadcast_threadsafe({"type": "cache_clear"})
        db.log_action("cache_clear_broadcast", f"online={n}")
        self.statusBar().showMessage(
            f"Keshni tozalash buyrug'i yuborildi ({n} ta kioskka).", 4000)

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
        self._broadcast_sync("settings")
        self.statusBar().showMessage("Xavfsizlik sozlamalari saqlandi.", 3000)
