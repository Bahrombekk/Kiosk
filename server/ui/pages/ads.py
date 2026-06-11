"""ui/pages/ads.py — Reklama sahifasi mixin'i (kartochkalar to'ri).

Kontent sahifasi kabi zamonaviy ko'rinish: har reklama — thumbnail (videodan
kadr olinadi), media turi/holat badge'lari, namoyish·oraliq·vaqt ma'lumotlari
va amal tugmalari bilan kartochka.
"""
import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QHBoxLayout, QLabel, QMessageBox, QPushButton,
                             QScrollArea)

import config
import db
from ui.cards import AD_CARD_W, AdCard, CardFlow
from ui.dialogs import AdDialog

# Joylashuv tablari (Kontent sahifasidagi tur tablari kabi)
PLACE_GROUPS = (
    ("popup", "Popup"),
    ("banner", "Banner"),
    ("both", "Popup + Banner"),
)


class AdsPageMixin:
    @staticmethod
    def _ads_rows():
        """Reklamalar + kartochka uchun hisoblangan maydonlar (media turi,
        davomiylik, takrorlanish va vaqt oralig'i matnlari)."""
        rows = db.get_ads(active_only=False)
        for ad in rows:
            mp = ad.get("media_path") or ""
            # Fayl diskda haqiqatan bormi? Yo'q bo'lsa kartada qizil "Fayl
            # yo'q" ko'rinadi — kiosk bunday reklamani baribir o'tkazib yuboradi.
            if mp and os.path.isfile(os.path.join(config.ADS_DIR, mp)):
                ad["media_kind"] = ("Video" if AdDialog._is_video(mp) else "Rasm")
            else:
                ad["media_kind"] = None
            if ad["media_kind"] == "Video" and not ad.get("duration"):
                ad["dur_disp"] = "Video oxirigacha"
            else:
                ad["dur_disp"] = f"{ad.get('duration') or 10} s"
            ad["int_disp"] = (f"har {ad['interval_min']} daq"
                              if ad.get("interval_min") else "Standart oraliq")
            st, en = ad.get("start_time"), ad.get("end_time")
            ad["time_disp"] = f"{st} – {en}" if st and en else "Kun bo'yi"
        return rows

    def _ads_page(self):
        w, lay = self._page(
            "Reklama",
            "Kioskda qalqib chiquvchi rasm/video reklamalar — har biri o'z "
            "davomiyligi, takrorlanish oralig'i va kunlik vaqti bilan")

        bar = QHBoxLayout()
        bar.setSpacing(8)
        bar.addWidget(self._btn("Qo'shish", "plus", self.add_ad))
        bar.addWidget(self._btn("Yangilash", "refresh-cw",
                                self.refresh_ads, "ghost"))
        bar.addStretch(1)
        lay.addLayout(bar)

        # Joylashuv tablari: Barchasi / Popup / Banner / Popup+Banner
        tabs = QHBoxLayout()
        tabs.setSpacing(8)
        self._aplace = None
        self._aplace_btns = {}
        for key, label in ([(None, "Barchasi")] + list(PLACE_GROUPS)):
            b = QPushButton(label)
            b.setObjectName("typeTab")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _c, k=key: self._set_aplace(k))
            self._aplace_btns[key] = b
            tabs.addWidget(b)
        tabs.addStretch(1)
        self._aplace_btns[None].setChecked(True)
        lay.addLayout(tabs)

        # Kartochkalar to'ri (umumiy scroll ichida)
        scroll = QScrollArea()
        scroll.setObjectName("plainScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.ads_flow = CardFlow(AD_CARD_W)
        scroll.setWidget(self.ads_flow)
        lay.addWidget(scroll, 1)

        self.ads_empty = QLabel(
            "Hozircha reklama yo'q — «Qo'shish» orqali rasm yoki video "
            "reklama kiriting.")
        self.ads_empty.setStyleSheet("color: #94A3B8; padding: 6px 2px;")
        self.ads_empty.hide()
        lay.addWidget(self.ads_empty)

        self.ads_count = QLabel("")
        self.ads_count.setObjectName("hint")
        lay.addWidget(self.ads_count)

        self.refresh_ads()
        return w

    def _set_aplace(self, key):
        """Joylashuv tabini almashtiradi (None = Barchasi)."""
        self._aplace = key
        for k, b in self._aplace_btns.items():
            b.setChecked(k == key)
        self.refresh_ads()

    @staticmethod
    def _ad_place(ad):
        """Reklamaning joylashuvi (eski yozuvlarda NULL = popup)."""
        key = ad.get("placement") or "popup"
        return key if key in ("popup", "banner", "both") else "popup"

    def refresh_ads(self):
        items = self._ads_rows()
        # Tab yorliqlarida sonlar ko'rinadi
        counts = {}
        for ad in items:
            k = self._ad_place(ad)
            counts[k] = counts.get(k, 0) + 1
        self._aplace_btns[None].setText(f"Barchasi ({len(items)})")
        for key, label in PLACE_GROUPS:
            self._aplace_btns[key].setText(f"{label} ({counts.get(key, 0)})")
        if self._aplace:
            items = [ad for ad in items if self._ad_place(ad) == self._aplace]
        self.ads_flow.set_cards(
            AdCard(ad, self.edit_ad, self.delete_ad) for ad in items)
        self.ads_empty.setVisible(not items)
        self.ads_count.setText(f"Jami: {len(items)} ta")

    def add_ad(self):
        dlg = AdDialog(self)
        if dlg.exec():
            vals = dlg.values()
            new_id = db.add_ad(vals)
            db.log_action("ads_added", f"#{new_id} {vals.get('title')!r}")
            self.refresh_ads()
            self._broadcast_sync("ads")
            self.statusBar().showMessage("Reklama qo'shildi.", 3000)

    def edit_ad(self, ad):
        aid = ad["id"]
        fresh = db.get_ad_by_id(aid)
        if fresh is None:
            self.refresh_ads()
            return
        dlg = AdDialog(self, fresh)
        if dlg.exec():
            db.update_ad(aid, dlg.values())
            db.log_action("ads_updated", f"#{aid}")
            self.refresh_ads()
            self._broadcast_sync("ads")
            self.statusBar().showMessage("Reklama yangilandi.", 3000)

    def delete_ad(self, ad):
        if QMessageBox.question(
                self, "Tasdiqlang",
                f"«{ad.get('title', '')}» reklamasi o'chirilsinmi?") \
                == QMessageBox.StandardButton.Yes:
            db.delete_ad(ad["id"])
            db.log_action("ads_deleted", f"#{ad['id']}")
            self.refresh_ads()
            self._broadcast_sync("ads")
            self.statusBar().showMessage("Reklama o'chirildi.", 3000)
