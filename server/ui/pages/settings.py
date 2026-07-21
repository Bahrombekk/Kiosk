"""ui/pages/settings.py — Sozlamalar sahifasi mixin'i.

Dizayn: mavzu bo'yicha alohida kartalar (Poyezd / Reklama / Zastavka / SOS /
Xavfsizlik), har birida ikonkali sarlavha. Yorliqlar maydon USTIDA (2 ustunli
grid). Butun tarkib QScrollArea ichida — kichik oynada ham hech narsa
ustma-ust chiqmaydi, shunchaki aylantiriladi.
"""
import os

from PyQt6.QtCore import Qt, QDate
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
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

        # Harorat: internet ob-havo (Open-Meteo) yoki qo'lda kiritilgan qiymat.
        # Yoqilganda server marshrut bekatlari uchun 7 kunlik prognozni yuklab
        # keshlaydi (internet bo'lganda yangilanadi); joriy bekat + vaqt bo'yicha
        # harorat asosiy ekranda ko'rinadi. O'chirilsa — quyidagi qo'lda qiymat.
        self.s_weather = ToggleSwitch()
        self.s_weather_lbl = QLabel()
        self.s_temp = QSpinBox()
        self.s_temp.setRange(-50, 60)
        self.s_temp.setSuffix(" °C")
        no_wheel(self.s_temp)

        def _upd_weather(_c=None):
            on = self.s_weather.isChecked()
            self.s_weather_lbl.setText(
                "Internet ob-havo (avtomatik)" if on
                else "Qo'lda kiritilgan harorat")
            self.s_temp.setEnabled(not on)
        self.s_weather.toggled.connect(_upd_weather)
        self._upd_weather = _upd_weather
        w_row = QHBoxLayout()
        w_row.setContentsMargins(0, 0, 0, 0)
        w_row.setSpacing(12)
        w_row.addWidget(self.s_weather)
        w_row.addWidget(self.s_weather_lbl)
        w_row.addStretch(1)
        w_holder = QWidget()
        w_holder.setLayout(w_row)
        wg = QGridLayout()
        wg.setHorizontalSpacing(14)
        wg.addLayout(self._field("Harorat manbai", w_holder), 0, 0)
        wg.addLayout(self._field("Qo'lda harorat", self.s_temp), 0, 1)
        wg.setColumnStretch(0, 1)
        clay.addLayout(wg)
        w_hint = QLabel(
            "Internet ob-havo yoqilganda harorat avtomatik — bekat hududi va "
            "vaqtiga qarab o'zgaradi. Server 7 kunlik prognozni yuklab qo'yadi, "
            "shuning uchun internet uzilsa ham bir hafta davomida ishlaydi.")
        w_hint.setObjectName("hint")
        w_hint.setWordWrap(True)
        clay.addWidget(w_hint)

        # Tezlik: avto (jadvaldan segment o'rtacha) yoki qo'lda kiritilgan son.
        self.s_speed_auto = ToggleSwitch()
        self.s_speed_auto_lbl = QLabel()
        self.s_speed = QSpinBox()
        self.s_speed.setRange(0, 400)
        self.s_speed.setSuffix(" km/h")
        no_wheel(self.s_speed)

        def _upd_speed(_c=None):
            on = self.s_speed_auto.isChecked()
            self.s_speed_auto_lbl.setText(
                "Jadvaldan (avtomatik)" if on else "Qo'lda kiritilgan tezlik")
            self.s_speed.setEnabled(not on)
        self.s_speed_auto.toggled.connect(_upd_speed)
        self._upd_speed = _upd_speed
        sp_row = QHBoxLayout()
        sp_row.setContentsMargins(0, 0, 0, 0)
        sp_row.setSpacing(12)
        sp_row.addWidget(self.s_speed_auto)
        sp_row.addWidget(self.s_speed_auto_lbl)
        sp_row.addStretch(1)
        sp_holder = QWidget()
        sp_holder.setLayout(sp_row)
        sg = QGridLayout()
        sg.setHorizontalSpacing(14)
        sg.addLayout(self._field("Tezlik manbai", sp_holder), 0, 0)
        sg.addLayout(self._field("Qo'lda tezlik", self.s_speed), 0, 1)
        sg.setColumnStretch(0, 1)
        clay.addLayout(sg)
        sp_hint = QLabel(
            "Avtomatik yoqilganda tezlik jadvaldan hisoblanadi — joriy bekat va "
            "keyingi bekat oralig'idagi masofa/vaqt bo'yicha o'rtacha (poyezd "
            "yurgani sayin o'zgaradi). O'chirilsa — yuqoridagi qo'lda qiymat.")
        sp_hint.setObjectName("hint")
        sp_hint.setWordWrap(True)
        clay.addWidget(sp_hint)
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

        # «Media» tanlangan bo'lsa — kino ichida qaysi joylarda chiqsin
        self.s_media_slots = QComboBox()
        for label, val in (
                ("Boshida, o'rtasida va oxirida", "pre,mid,end"),
                ("Boshida va oxirida", "pre,end"),
                ("Faqat boshida", "pre")):
            self.s_media_slots.addItem(label, val)
        no_wheel(self.s_media_slots)   # scroll paytida adashib o'zgarmasin
        clay.addLayout(self._field(
            "Media reklama joylashuvi (kino ichida)", self.s_media_slots))

        def _upd_media_slots():
            self.s_media_slots.setEnabled(self.s_ad_algos["media"].isChecked())
        self.s_ad_algos["media"].toggled.connect(lambda _c: _upd_media_slots())
        _upd_media_slots()

        ad_hint = QLabel(
            "Oraliq — popup chastotasi: har shu daqiqada BITTA reklama "
            "chiqadi. «Vaznli»da har reklamaning o'z oralig'i (Reklama "
            "bo'limida) vazn bo'lib xizmat qiladi; «Navbat bilan» va "
            "«Tasodifiy»da reklamalar teng aylanadi. Bu uchovidan bittasi "
            "ishlatiladi (bir nechtasi belgilansa — yuqoridagisi). «Media» "
            "alohida: reklama kino ichida ko'rsatiladi — joyini quyidagi "
            "«Media reklama joylashuvi» orqali tanlaysiz (faqat boshida / "
            "boshi va oxiri / boshi-o'rtasi-oxiri). Har kino ochilganda "
            "navbatdagi boshqa reklama chiqadi; ikki joy tanlansa har biriga "
            "boshqa reklama. «Media»ni popup usuli bilan birga belgilash mumkin.")
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

        # === 6) Sinov muddati / Litsenziya ===
        card, clay = self._sec_card(
            "lock", "#FEF2F2", "#DC2626", "Sinov muddati (litsenziya)",
            "Dasturni sinovga berish — muddat tugaganda kiosklar avtomatik "
            "bloklanadi (qulf ekrani). Xohlagan paytda qo'lda ham bloklash mumkin.")
        self.s_trial_on = ToggleSwitch()
        self.s_trial_on_lbl = QLabel()
        self.s_trial_on.toggled.connect(
            lambda c: self.s_trial_on_lbl.setText(
                "Sinov nazorati yoqilgan" if c else "O'chirilgan (cheksiz)"))
        ton_row = QHBoxLayout()
        ton_row.setContentsMargins(0, 0, 0, 0)
        ton_row.setSpacing(12)
        ton_row.addWidget(self.s_trial_on)
        ton_row.addWidget(self.s_trial_on_lbl)
        ton_row.addStretch(1)
        ton_holder = QWidget()
        ton_holder.setLayout(ton_row)
        clay.addLayout(self._field("Sinov muddati nazorati", ton_holder))

        self.s_trial_start = QDateEdit()
        self.s_trial_start.setCalendarPopup(True)
        self.s_trial_start.setDisplayFormat("yyyy-MM-dd")
        self.s_trial_days = QSpinBox()
        self.s_trial_days.setRange(1, 3650)
        self.s_trial_days.setSuffix(" kun")
        no_wheel(self.s_trial_days)
        tg = QGridLayout()
        tg.setHorizontalSpacing(14)
        tg.addLayout(self._field("Topshirish (boshlanish) sanasi",
                                 self.s_trial_start), 0, 0)
        tg.addLayout(self._field("Necha kunga", self.s_trial_days), 0, 1)
        clay.addLayout(tg)

        # Joriy holat (tugash sanasi + qolgan kunlar / BLOKLANGAN)
        self.s_trial_status = QLabel()
        self.s_trial_status.setWordWrap(True)
        self.s_trial_status.setObjectName("hint")
        clay.addWidget(self.s_trial_status)

        # Darhol amal qiluvchi tugmalar (Saqlashdan mustaqil)
        t_row = QHBoxLayout()
        t_row.addStretch(1)
        t_row.addWidget(self._btn("Blokni ochish", "check",
                                  self._trial_unblock, kind="ghost"))
        t_row.addWidget(self._btn("Hoziroq bloklash", "lock",
                                  self._trial_block_now, kind="danger"))
        clay.addLayout(t_row)
        ilay.addWidget(card)

        # === 7) Imzolangan litsenziya (license.key) ===
        card, clay = self._sec_card(
            "file-text", "#EFF6FF", "#2563EB", "Litsenziya fayli (imzolangan)",
            "Dastur vendor imzolagan license.key bilan ishlaydi: muddat, "
            "kiosk soni chegarasi va AYNAN SHU kompyuterga bog'langan. "
            "Yangi litsenziya olish uchun quyidagi Qurilma ID'ni vendorga "
            "yuboring — u license.key faylini tayyorlab beradi.")
        self.s_hwid = QLineEdit()
        self.s_hwid.setReadOnly(True)
        hw_row = QHBoxLayout()
        hw_row.setContentsMargins(0, 0, 0, 0)
        hw_row.setSpacing(10)
        hw_row.addWidget(self.s_hwid, 1)
        hw_row.addWidget(self._btn("Nusxalash", "copy",
                                   self._copy_hwid, kind="ghost"))
        hw_holder = QWidget()
        hw_holder.setLayout(hw_row)
        clay.addLayout(self._field("Qurilma ID (vendorga yuboriladi)",
                                   hw_holder))
        self.s_lic_status = QLabel()
        self.s_lic_status.setWordWrap(True)
        self.s_lic_status.setObjectName("hint")
        clay.addWidget(self.s_lic_status)
        l_row = QHBoxLayout()
        l_row.addStretch(1)
        l_row.addWidget(self._btn("Litsenziya faylini yuklash...", "file-text",
                                  self._load_license_file))
        clay.addLayout(l_row)
        ilay.addWidget(card)

        # === 8) Wi-Fi tarqatish (hotspot) ===
        card, clay = self._sec_card(
            "wifi", "#ECFEFF", "#0891B2", "Wi-Fi tarqatish (hotspot)",
            "Yoqilsa server ishga tushganda o'zi Wi-Fi tarqatadi — kiosklar "
            "alohida routersiz shu tarmoqqa ulanadi (internet shart emas). "
            "Wi-Fi adapter hotspotni qo'llashi va dastur admin huquqida "
            "ishlashi kerak.")
        self.s_wifi_on = ToggleSwitch()
        self.s_wifi_on_lbl = QLabel()
        self.s_wifi_on.toggled.connect(
            lambda c: self.s_wifi_on_lbl.setText(
                "Yoqilgan" if c else "O'chirilgan"))
        won_row = QHBoxLayout()
        won_row.setContentsMargins(0, 0, 0, 0)
        won_row.setSpacing(12)
        won_row.addWidget(self.s_wifi_on)
        won_row.addWidget(self.s_wifi_on_lbl)
        won_row.addStretch(1)
        won_holder = QWidget()
        won_holder.setLayout(won_row)
        clay.addLayout(self._field("Server ishga tushganda Wi-Fi tarqatsin",
                                   won_holder))
        self.s_wifi_ssid = QLineEdit()
        self.s_wifi_ssid.setPlaceholderText("Masalan: KioskServer")
        self.s_wifi_pass = QLineEdit()
        self.s_wifi_pass.setPlaceholderText("Kamida 8 belgi")
        wg = QGridLayout()
        wg.setHorizontalSpacing(14)
        wg.addLayout(self._field("Tarmoq nomi (SSID)", self.s_wifi_ssid), 0, 0)
        wg.addLayout(self._field("Wi-Fi paroli", self.s_wifi_pass), 0, 1)
        clay.addLayout(wg)
        self.s_wifi_status = QLabel()
        self.s_wifi_status.setWordWrap(True)
        self.s_wifi_status.setObjectName("hint")
        clay.addWidget(self.s_wifi_status)
        w_row = QHBoxLayout()
        w_row.addStretch(1)
        w_row.addWidget(self._btn("Hozir o'chirish", "wifi",
                                  self._wifi_stop_now, kind="ghost"))
        w_row.addWidget(self._btn("Saqlash va qo'llash", "save",
                                  self._wifi_apply))
        clay.addLayout(w_row)
        ilay.addWidget(card)

        # === 9) Veb ilova (web kiosk) ===
        card, clay = self._sec_card(
            "globe", "#EEF2FF", "#4F46E5", "Veb ilova (poyezd.uz)",
            "Yoqilsa server telefon/brauzer uchun veb versiyani tarqatadi — "
            "yo'lovchilar o'z qurilmasidan ochadi. O'chirilsa veb yopiladi, "
            "faqat kiosk qurilmalari ishlaydi.")
        self.s_web_on = ToggleSwitch()
        self.s_web_on_lbl = QLabel()
        self.s_web_on.toggled.connect(
            lambda c: self.s_web_on_lbl.setText(
                "Yoqilgan" if c else "O'chirilgan"))
        web_row = QHBoxLayout()
        web_row.setContentsMargins(0, 0, 0, 0)
        web_row.setSpacing(12)
        web_row.addWidget(self.s_web_on)
        web_row.addWidget(self.s_web_on_lbl)
        web_row.addStretch(1)
        web_holder = QWidget()
        web_holder.setLayout(web_row)
        clay.addLayout(self._field("Veb ilova ishga tushsin", web_holder))
        self.s_web_status = QLabel()
        self.s_web_status.setWordWrap(True)
        self.s_web_status.setObjectName("hint")
        clay.addWidget(self.s_web_status)
        wb_row = QHBoxLayout()
        wb_row.addStretch(1)
        wb_row.addWidget(self._btn("Hozir o'chirish", "globe",
                                   self._web_stop_now, kind="ghost"))
        wb_row.addWidget(self._btn("Saqlash va qo'llash", "save",
                                   self._web_apply))
        clay.addLayout(wb_row)
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
        self.s_weather.setChecked(str(s.get("weather_auto") or "1") != "0")
        try:
            self.s_temp.setValue(int(float(s.get("temperature") or 22)))
        except (TypeError, ValueError):
            self.s_temp.setValue(22)
        self._upd_weather()
        self.s_speed_auto.setChecked(str(s.get("speed_auto") or "1") != "0")
        try:
            self.s_speed.setValue(int(float(s.get("speed") or 210)))
        except (TypeError, ValueError):
            self.s_speed.setValue(210)
        self._upd_speed()
        # Sinov muddati
        self.s_trial_on.setChecked((s.get("trial_enabled") or "0") == "1")
        self.s_trial_on_lbl.setText(
            "Sinov nazorati yoqilgan" if self.s_trial_on.isChecked()
            else "O'chirilgan (cheksiz)")
        start = (s.get("trial_start") or "").strip()
        qd = QDate.fromString(start, "yyyy-MM-dd")
        self.s_trial_start.setDate(qd if qd.isValid() else QDate.currentDate())
        try:
            self.s_trial_days.setValue(int(float(s.get("trial_days") or 30)))
        except (TypeError, ValueError):
            self.s_trial_days.setValue(30)
        self._update_trial_status()
        self._update_license_status()
        # Wi-Fi hotspot
        self.s_wifi_on.setChecked((s.get("wifi_hotspot") or "0") == "1")
        self.s_wifi_on_lbl.setText(
            "Yoqilgan" if self.s_wifi_on.isChecked() else "O'chirilgan")
        self.s_wifi_ssid.setText(s.get("wifi_ssid") or "KioskServer")
        self.s_wifi_pass.setText(s.get("wifi_password") or "")
        self._update_wifi_status()
        # Veb ilova
        self.s_web_on.setChecked(str(s.get("web_enabled") or "1") != "0")
        self.s_web_on_lbl.setText(
            "Yoqilgan" if self.s_web_on.isChecked() else "O'chirilgan")
        self._update_web_status()
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
        # Media reklama joylashuvi (kino ichida)
        slots = s.get("media_ad_slots") or "pre,mid,end"
        idx = self.s_media_slots.findData(slots)
        self.s_media_slots.setCurrentIndex(idx if idx >= 0 else 0)
        self.s_media_slots.setEnabled("media" in sel)

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
        db.set_setting("weather_auto", "1" if self.s_weather.isChecked() else "0")
        db.set_setting("temperature", str(self.s_temp.value()))
        db.set_setting("speed_auto", "1" if self.s_speed_auto.isChecked() else "0")
        db.set_setting("speed", str(self.s_speed.value()))
        db.set_setting("trial_enabled", "1" if self.s_trial_on.isChecked() else "0")
        db.set_setting("trial_start", self.s_trial_start.date().toString("yyyy-MM-dd"))
        db.set_setting("trial_days", str(self.s_trial_days.value()))
        self._update_trial_status()
        db.set_setting("ad_interval_min", str(self.s_ad_int.value()))
        algos = [k for k, cb in self.s_ad_algos.items() if cb.isChecked()]
        db.set_setting("ad_algorithm", ",".join(algos) or "weighted")
        db.set_setting("media_ad_slots", self.s_media_slots.currentData())
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

    # --- Sinov muddati / litsenziya ---
    def _update_trial_status(self):
        """Joriy holatni (tugash sanasi, qolgan kunlar yoki BLOKLANGAN) yozadi.
        Emoji o'rniga rang-kod: qizil=blok, yashil=faol, kulrang=o'chiq."""
        st = db.trial_state()
        if st["reason"] == "manual":
            txt = "HOZIR QO'LDA BLOKLANGAN — kiosklarda qulf ekrani ko'rinadi."
            color = "#DC2626"
        elif st["reason"] == "expired":
            txt = (f"MUDDAT TUGAGAN ({st['end']}) — kiosklar bloklangan. "
                   "Yangilash uchun sanani o'zgartiring va saqlang.")
            color = "#DC2626"
        elif st["enabled"] and st["end"]:
            d = st["days_left"]
            txt = (f"Faol. Tugash sanasi: {st['end']} — {d} kun qoldi."
                   if d is not None and d >= 0
                   else f"Tugash sanasi: {st['end']}")
            color = "#047857"
        else:
            txt = "Sinov nazorati o'chirilgan — dastur cheksiz ishlaydi."
            color = "#64748B"
        self.s_trial_status.setText(txt)
        self.s_trial_status.setStyleSheet(
            f"color: {color}; font-weight: 700; background: transparent;")

    # --- Imzolangan litsenziya (license.key) ---
    def _copy_hwid(self):
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(self.s_hwid.text())
        self.statusBar().showMessage("Qurilma ID nusxalandi.", 3000)

    def _update_license_status(self):
        """license.key holatini kartada ko'rsatadi (HW ID ham shu yerda)."""
        import licensing
        st = licensing.state()
        self.s_hwid.setText(st["hw_id"])
        if st["valid"]:
            left = (f" ({st['days_left']} kun qoldi)"
                    if st["days_left"] is not None else "")
            txt = ("Litsenziya FAOL"
                   + (f" — mijoz: {st['customer']}" if st["customer"] else "")
                   + f" • muddat: {st['expires'] or 'muddatsiz'}{left}"
                   + f" • kiosk limiti: {st['max_kiosks'] or 'cheksiz'}")
            color = "#047857"
        elif st["blocked"]:
            txt = (f"LITSENZIYA YAROQSIZ: {st['reason']} — barcha kiosklar "
                   "qulf ekranida. To'g'ri license.key yuklang.")
            color = "#DC2626"
        else:
            txt = st["reason"] or ""
            color = "#64748B"
        self.s_lic_status.setText(txt)
        self.s_lic_status.setStyleSheet(
            f"color: {color}; font-weight: 700; background: transparent;")

    def _load_license_file(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "Litsenziya fayli", "",
            "Litsenziya (*.key);;Barcha fayllar (*)")
        if not path:
            return
        import licensing
        try:
            st = licensing.install_file(path)
        except (OSError, ValueError) as e:
            QMessageBox.warning(self, "Litsenziya", str(e))
            return
        db.log_action("license_install",
                      st.get("customer") or os.path.basename(path))
        self._broadcast_sync("settings")   # kiosklar yangi holatni darhol oladi
        self._update_license_status()
        if st["valid"]:
            self.statusBar().showMessage("Litsenziya qabul qilindi.", 4000)
        else:
            QMessageBox.warning(self, "Litsenziya",
                                f"Fayl yuklandi, lekin yaroqsiz: {st['reason']}")

    # --- Wi-Fi tarqatish (hotspot) ---
    def _update_wifi_status(self):
        """Hotspot hozir yoqilganmi (jonli holat) — kartada ko'rsatadi."""
        try:
            import hotspot
            active = hotspot.is_active()
        except Exception:                                # noqa: BLE001
            active = False
        if active:
            txt = "Hozir FAOL — kiosklar shu Wi-Fi'ga ulanishi mumkin."
            color = "#047857"
        elif self.s_wifi_on.isChecked():
            txt = ("Yoqilgan, lekin hozir faol emas (server qayta ishga "
                   "tushganda yoki 'Saqlash va qo'llash' bosilganda yoqiladi).")
            color = "#B45309"
        else:
            txt = "O'chirilgan — server Wi-Fi tarqatmaydi."
            color = "#64748B"
        self.s_wifi_status.setText(txt)
        self.s_wifi_status.setStyleSheet(
            f"color: {color}; font-weight: 700; background: transparent;")

    def _wifi_apply(self):
        """Wi-Fi sozlamalarini saqlaydi va darhol qo'llaydi (yoqadi/o'chiradi)."""
        from PyQt6.QtWidgets import QMessageBox
        ssid = self.s_wifi_ssid.text().strip()
        pw = self.s_wifi_pass.text().strip()
        on = self.s_wifi_on.isChecked()
        if on and (not ssid or len(pw) < 8):
            QMessageBox.warning(
                self, "Wi-Fi",
                "Tarmoq nomi (SSID) va kamida 8 belgili parol kiriting.")
            return
        db.set_setting("wifi_hotspot", "1" if on else "0")
        db.set_setting("wifi_ssid", ssid or "KioskServer")
        db.set_setting("wifi_password", pw)
        db.log_action("wifi_hotspot", "on" if on else "off")
        import hotspot
        if on:
            ok, msg = hotspot.start(ssid, pw)
            if ok:
                self.statusBar().showMessage(
                    f"Wi-Fi tarqatish yoqildi ({msg}).", 5000)
            else:
                QMessageBox.warning(
                    self, "Wi-Fi tarqatib bo'lmadi",
                    "Sozlama saqlandi, lekin hotspot yoqilmadi:\n\n" + msg +
                    "\n\nWi-Fi adapter hotspotni qo'llashini va dastur admin "
                    "huquqida ishlashini tekshiring.")
        else:
            hotspot.stop()
            self.statusBar().showMessage("Wi-Fi tarqatish o'chirildi.", 4000)
        self._update_wifi_status()

    def _wifi_stop_now(self):
        """Hotspot'ni darhol o'chiradi (sozlamani o'zgartirmasdan)."""
        import hotspot
        hotspot.stop()
        self.statusBar().showMessage("Wi-Fi tarqatish to'xtatildi.", 4000)
        self._update_wifi_status()

    # --- Veb ilova (web kiosk) ---
    def _update_web_status(self):
        """Veb hozir ishlayaptimi (jonli) + qanday manzildan ochish — kartada."""
        web = getattr(self, "web", None)
        running = bool(web and web.is_running())
        if running:
            urls = "http://poyezd.uz"
            try:
                import security
                ips = [ip for ip in security._local_ipv4s()
                       if ip and ip != "127.0.0.1"]
                for ip in ips:
                    urls += f"  •  http://{ip}"
            except Exception:                            # noqa: BLE001
                pass
            txt = f"Hozir ISHLAYAPTI — oching: {urls}"
            color = "#047857"
        elif self.s_web_on.isChecked():
            txt = ("Yoqilgan, lekin hozir ishlamayapti (Node.js topilmagan "
                   "bo'lishi mumkin, yoki 'Saqlash va qo'llash' bosing).")
            color = "#B45309"
        else:
            txt = "O'chirilgan — veb tarqatilmaydi (faqat kiosk qurilmalari)."
            color = "#64748B"
        self.s_web_status.setText(txt)
        self.s_web_status.setStyleSheet(
            f"color: {color}; font-weight: 700; background: transparent;")

    def _web_apply(self):
        """Veb sozlamasini saqlaydi va darhol qo'llaydi (yoqadi/o'chiradi)."""
        on = self.s_web_on.isChecked()
        db.set_setting("web_enabled", "1" if on else "0")
        db.log_action("web_enabled", "on" if on else "off")
        web = getattr(self, "web", None)
        if web:
            if on:
                web.start()
            else:
                web.stop()
        # start() fon oqimida — holatni bir lahzadan keyin ham yangilaymiz
        try:
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(1800, self._update_web_status)
        except Exception:                                # noqa: BLE001
            pass
        self._update_web_status()
        self.statusBar().showMessage(
            "Veb ilova yoqildi." if on else "Veb ilova o'chirildi.", 4000)

    def _web_stop_now(self):
        """Veb'ni darhol to'xtatadi (sozlamani o'zgartirmasdan)."""
        web = getattr(self, "web", None)
        if web:
            web.stop()
        self.statusBar().showMessage("Veb ilova to'xtatildi.", 4000)
        self._update_web_status()

    def _trial_block_now(self):
        if QMessageBox.question(
                self, "Hoziroq bloklash",
                "Barcha kiosklar DARHOL bloklansinmi? Ekranlarда qulf "
                "ko'rinadi. Keyin 'Blokni ochish' bilan qaytarasiz.") \
                != QMessageBox.StandardButton.Yes:
            return
        db.set_setting("trial_blocked", "1")
        db.log_action("trial_block_now", "manual")
        self._broadcast_sync("settings")   # kiosklar status'ни darhol oladi
        self._update_trial_status()
        self.statusBar().showMessage("Kiosklar bloklandi.", 4000)

    def _trial_unblock(self):
        db.set_setting("trial_blocked", "0")
        db.log_action("trial_unblock", "manual")
        self._broadcast_sync("settings")
        self._update_trial_status()
        self.statusBar().showMessage("Blok ochildi.", 4000)

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
