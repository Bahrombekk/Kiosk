"""ui/pages/dashboard.py — Boshqaruv (dashboard) sahifasi mixin'i."""
import json
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar, QWidget,
    QDialog, QDialogButtonBox, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor

import config
import db
import ws
import security
from icons import svg_icon, svg_pixmap
from ui.styles import C_ACCENT, C_MUTED, C_OK, C_BAD
from ui.helpers import _fmt_uptime, local_ips


class DashboardPageMixin:
    # ------------------------------------------------------------------
    #  Boshqaruv (dashboard) sahifasi
    # ------------------------------------------------------------------
    def _dashboard_page(self):
        w, lay = self._page("Boshqaruv",
                            "Server holati, ulangan kiosklar va e'lonlar")

        # === Statistika kartalari qatori ===
        stats = QHBoxLayout()
        stats.setSpacing(14)
        self._stat_lbls = {}
        for key, label, icon_name, fg, bg in (
                ("kiosks", "Ulangan kiosklar", "monitor", "#1D4ED8", "#DBEAFE"),
                ("content", "Kontentlar", "clapperboard", "#7C3AED", "#EDE9FE"),
                ("ads", "Reklamalar", "megaphone", "#B45309", "#FEF3C7"),
                ("sites", "Saytlar", "globe", "#0F766E", "#CCFBF1")):
            card, clay = self._card(16)
            row = QHBoxLayout()
            row.setSpacing(12)
            # Rangli ikonka plitkasi
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
            stats.addWidget(card, 1)
            self._stat_lbls[key] = num
        lay.addLayout(stats)

        # === Holat + manzil kartasi ===
        stat_card, stat_lay = self._card()
        hrow = QHBoxLayout()
        self.status_dot = QLabel()
        self.status_lbl = QLabel()
        self.status_lbl.setStyleSheet("font-size: 17px; font-weight: 700;")
        hrow.addWidget(self.status_dot)
        hrow.addWidget(self.status_lbl)
        hrow.addStretch(1)
        stat_lay.addLayout(hrow)

        ip0 = local_ips()[0]
        scheme = "https" if config.USE_TLS else "http"
        self._server_url = f"{scheme}://{ip0}:{config.PORT}"
        arow = QHBoxLayout()
        arow.setSpacing(10)
        addr_ic = QLabel()
        addr_ic.setPixmap(svg_pixmap("wifi", C_MUTED, 16))
        addr = QLabel(self._server_url)
        addr.setObjectName("muted")
        addr.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        copy_btn = self._btn("Nusxalash", "copy", self._copy_addr, kind="ghost")
        arow.addWidget(addr_ic)
        arow.addWidget(addr)
        arow.addWidget(copy_btn)
        arow.addStretch(1)
        stat_lay.addLayout(arow)
        hint = QLabel(f"User qurilmada: KIOSK_SERVER={self._server_url}")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        stat_lay.addWidget(hint)

        # API kalit qatori — kiosk o'rnatuvchisiga kiritiladi (maskalangan,
        # "Nusxalash" tugmasi to'liq kalitni clipboard'ga oladi).
        self._api_key = db.get_or_create_api_key()
        krow = QHBoxLayout()
        krow.setSpacing(10)
        key_ic = QLabel()
        key_ic.setPixmap(svg_pixmap("copy", C_MUTED, 16))
        masked = self._api_key[:4] + "•" * 8 + self._api_key[-4:]
        key_lbl = QLabel(f"API kalit: {masked}")
        key_lbl.setObjectName("muted")
        key_copy = self._btn("Nusxalash", "copy", self._copy_api_key, kind="ghost")
        krow.addWidget(key_ic)
        krow.addWidget(key_lbl)
        krow.addWidget(key_copy)
        krow.addStretch(1)
        stat_lay.addLayout(krow)
        key_hint = QLabel("Kiosk o'rnatishda shu kalit so'raladi (server.txt'dagi key= qatori)")
        key_hint.setObjectName("hint")
        key_hint.setWordWrap(True)
        stat_lay.addWidget(key_hint)

        # --- Kiosk ishonch fayli (trust.json) eksporti ---
        # Bitta faylga server URL + API kalit + ochiq imzo kaliti + TLS
        # sertifikat fingerprint/PEM jamlanadi. Kiosk o'rnatuvchisi shu faylni
        # tanlaydi: kiosk serverni IMZO bilan tekshiradi va TLS'ni PIN qiladi
        # (qo'lda IP/kalit yozish o'rniga — xavfsizroq va qulayroq).
        trow = QHBoxLayout()
        trow.setSpacing(10)
        tr_ic = QLabel()
        tr_ic.setPixmap(svg_pixmap("lock", C_MUTED, 16))
        trow.addWidget(tr_ic)
        trow.addWidget(self._btn("Kiosk ishonch faylini eksport (trust.json)",
                                 "save", self._export_trust, kind="ghost"))
        trow.addStretch(1)
        stat_lay.addLayout(trow)
        tr_hint = QLabel(
            "O'rnatishda kioskka shu faylni bering — server IP'sini qo'lda "
            "yozish shart emas (kiosk imzolangan signal orqali topadi) va "
            "ulanish sertifikatga pin qilinadi.")
        tr_hint.setObjectName("hint")
        tr_hint.setWordWrap(True)
        stat_lay.addWidget(tr_hint)
        lay.addWidget(stat_card)

        # === E'lon yuborish kartasi ===
        ann_card, ann_lay = self._card()
        ann_title_row = QHBoxLayout()
        ann_title_row.setSpacing(8)
        ann_ic = QLabel()
        ann_ic.setPixmap(svg_pixmap("megaphone", C_ACCENT, 18))
        ann_title = QLabel("Barcha kiosklarga e'lon")
        ann_title.setObjectName("cardTitle")
        ann_title_row.addWidget(ann_ic)
        ann_title_row.addWidget(ann_title)
        ann_title_row.addStretch(1)
        ann_lay.addLayout(ann_title_row)
        ann_row = QHBoxLayout()
        self.ann_input = QLineEdit()
        self.ann_input.setPlaceholderText(
            "E'lon matnini kiriting... (masalan: Keyingi bekat — Samarqand)")
        self.ann_input.returnPressed.connect(self.send_announcement)
        send = self._btn("Yuborish", "send", self.send_announcement)
        ann_row.addWidget(self.ann_input, 1)
        ann_row.addWidget(send)
        ann_lay.addLayout(ann_row)
        lay.addWidget(ann_card)

        # === Kiosklar jadvali (doimiy registr) ===
        # Bir marta ulangan kiosk ro'yxatda DOIM qoladi — hozir oflayn bo'lsa
        # ham (qachon oxirgi marta ko'ringani bilan). Raqam/xona o'rnatishda
        # kioskning server.txt fayliga yoziladi (kiosk= / xona= qatorlari).
        ktitle = QLabel("Kiosklar — № va xona bilan (oflaynlar ham ko'rinadi)")
        ktitle.setObjectName("cardTitle")
        lay.addWidget(ktitle)

        self.kiosk_table = QTableWidget(0, 8)
        self.kiosk_table.setHorizontalHeaderLabels(
            ["№", "Xona", "Qurilma", "IP manzil", "Holat",
             "Oxirgi aloqa", "Lokal kesh", "Xotira (bo'sh joy)"])
        kh = self.kiosk_table.horizontalHeader()
        kh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        kh.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        self._setup_table(self.kiosk_table)
        self.kiosk_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        # Qatorga ikki marta bosilsa — shu kioskda qaysi kontent yuklangani
        self.kiosk_table.cellDoubleClicked.connect(self._show_kiosk_cache)
        self._kiosk_rows = []
        lay.addWidget(self.kiosk_table, 1)

        self.empty_lbl = QLabel("Hozircha hech qaysi kiosk ro'yxatdan o'tmagan.")
        self.empty_lbl.setStyleSheet("color: #94A3B8; padding: 6px 4px;")
        lay.addWidget(self.empty_lbl)
        return w

    def _copy_addr(self):
        QApplication.clipboard().setText(self._server_url)
        self.statusBar().showMessage("Manzil nusxalandi: " + self._server_url, 3000)

    def _copy_api_key(self):
        QApplication.clipboard().setText(self._api_key)
        self.statusBar().showMessage("API kalit nusxalandi.", 3000)

    def _export_trust(self):
        """Kioskka beriladigan trust.json faylini yozadi (server URL + API
        kalit + ochiq imzo kaliti + TLS sertifikat). Imzo/sertifikat birinchi
        ishga tushishda yaratilgan; bu yerda faqat o'qib jamlanadi."""
        import json
        try:
            security.ensure_identity()
            bundle = security.trust_bundle(
                self._server_url, self._api_key, config.SERVER_NAME)
        except Exception as e:                       # noqa: BLE001
            QMessageBox.critical(
                self, "Xato",
                "Ishonch faylini tayyorlab bo'lmadi.\n"
                "'cryptography' kutubxonasi o'rnatilganmi tekshiring.\n\n"
                f"{e}")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Kiosk ishonch faylini saqlash", "trust.json",
            "JSON fayllar (*.json)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(bundle, f, ensure_ascii=False, indent=2)
        except OSError as e:
            QMessageBox.critical(self, "Xato", f"Saqlab bo'lmadi: {e}")
            return
        db.log_action("trust_bundle_exported", path)
        QMessageBox.information(
            self, "Tayyor",
            "Ishonch fayli saqlandi:\n" + path + "\n\n"
            "Bu faylni kiosk o'rnatuvchisiga bering. Maxfiy kalit (imzo) "
            "serverda qoladi — faylda faqat ochiq ma'lumot va API kalit bor.")
        self.statusBar().showMessage("trust.json eksport qilindi.", 4000)

    @staticmethod
    def _dot(label, color, size=10):
        label.setFixedSize(size, size)
        label.setStyleSheet(
            f"background: {color}; border-radius: {size // 2}px;")

    def _update_status(self):
        running = self.server.isRunning() and not self.server.server.should_exit
        if running:
            self.status_lbl.setText("Server ishlayapti")
            self._dot(self.status_dot, C_OK)
            self.side_status.setText("Server ishlayapti")
            self._dot(self.side_dot, C_OK, 8)
        else:
            self.status_lbl.setText("Server to'xtagan")
            self._dot(self.status_dot, C_BAD)
            self.side_status.setText("Server to'xtagan")
            self._dot(self.side_dot, C_BAD, 8)

        # Kiosk registri: DB'dagi doimiy ro'yxat + jonli holat.
        # Onlayn = WS ulanishi bor YOKI heartbeat so'nggi 15 soniyada kelgan.
        ws_ids = {c.get("device_id") for c in ws.manager.clients()}
        try:
            kiosks = db.get_kiosks()
        except Exception:
            kiosks = []   # DB band bo'lsa keyingi siklda
        now = datetime.now()
        online_n = 0
        self._kiosk_rows = kiosks
        self.empty_lbl.setVisible(not kiosks)
        self.kiosk_table.setRowCount(len(kiosks))
        mon_icon = svg_icon("monitor", C_MUTED, 32)
        total_av = self._av_total()
        for r, k in enumerate(kiosks):
            online = k.get("device_id") in ws_ids
            if not online and k.get("last_seen"):
                try:
                    seen = datetime.strptime(k["last_seen"],
                                             "%Y-%m-%d %H:%M:%S")
                    online = (now - seen).total_seconds() < 15
                except ValueError:
                    pass
            online_n += online
            # Lokal kesh ustuni: o'chirilgan / "N/M media" + yuklanayotgan ⬇NN%
            if not k.get("cache_enabled", 1):
                kesh = "— o'chirilgan"
            else:
                kesh = f"{k.get('cached_n') or 0}/{total_av} media"
                try:
                    cg = json.loads(k.get("caching") or "null") or {}
                except (ValueError, TypeError):
                    cg = {}
                if online and cg.get("id") is not None:
                    pct = cg.get("pct", -1)
                    kesh += f"  ·  ⬇ {pct}%" if isinstance(pct, int) and pct >= 0 \
                            else "  ·  ⬇ yuklanmoqda"
            cells = [
                k.get("kiosk_no") or "—",
                k.get("room") or "—",
                k.get("device_id") or "",
                k.get("ip") or "",
                "● Onlayn" if online else "● Oflayn",
                k.get("last_seen") or "—",
                kesh,
            ]
            for col, val in enumerate(cells):
                item = QTableWidgetItem(str(val))
                if col == 2:
                    item.setIcon(mon_icon)
                if col == 4:
                    item.setForeground(QColor("#16A34A") if online
                                       else QColor("#94A3B8"))
                elif col in (3, 5, 6):
                    item.setForeground(Qt.GlobalColor.darkGray)
                self.kiosk_table.setItem(r, col, item)
            self.kiosk_table.setCellWidget(r, 7, self._disk_cell(k))
        self._stat_lbls["kiosks"].setText(str(online_n))

    @staticmethod
    def _cacheable_av():
        """Kioskka yuklanadigan media ro'yxati: video/audio fayli bor VA
        admin "Kiosklarga yuklab qo'yilsin" belgisini qo'ygan kontentlar."""
        try:
            return [c for c in db.get_content()
                    if c.get("type") in ("movie", "cartoon", "music",
                                         "audiobook", "book")
                    and c.get("file_path")
                    and c.get("visible", 1)
                    and (c.get("cache_enabled") is None
                         or c.get("cache_enabled"))]
        except Exception:
            return []

    def _av_total(self):
        return len(self._cacheable_av())

    @staticmethod
    def _disk_cell(k):
        """Kiosk diski indikatori: band foiz + «N GB bo'sh / M GB» yozuvi.
        Bo'sh joy ozayganda rang yashil -> sariq -> qizilga o'tadi."""
        total, free = k.get("disk_total") or 0, k.get("disk_free") or 0
        if not total:
            lbl = QLabel("—")
            lbl.setStyleSheet("color: #94A3B8; padding-left: 8px;")
            return lbl
        used_pct = round((total - free) * 100 / total)
        free_pct = 100 - used_pct
        chunk = ("#FCA5A5" if free_pct < 10
                 else "#FCD34D" if free_pct < 25 else "#86EFAC")
        gb = 1024 ** 3
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(used_pct)
        bar.setFormat(f"{free / gb:.1f} GB bo'sh / {total / gb:.0f} GB")
        bar.setStyleSheet(f"QProgressBar::chunk {{ background: {chunk};"
                          f" border-radius: 8px; }}")
        wrap = QWidget()
        wl = QHBoxLayout(wrap)
        wl.setContentsMargins(6, 4, 10, 4)
        wl.addWidget(bar)
        return wrap

    def _show_kiosk_cache(self, row, _col):
        """Kiosk qatoriga ikki marta bosilganda: shu qurilmada qaysi media
        yuklangan/yuklanmaganini ko'rsatadigan oyna."""
        if row >= len(self._kiosk_rows):
            return
        k = self._kiosk_rows[row]
        try:
            ids = set(json.loads(k.get("cached_ids") or "[]"))
        except (ValueError, TypeError):
            ids = set()
        av = self._cacheable_av()
        dev = k.get("device_id")
        dlg = QDialog(self)
        title = k.get("kiosk_no") or k.get("device_id") or "Kiosk"
        dlg.setWindowTitle(f"Kiosk {title} — lokal kesh"
                           + (f" (xona {k['room']})" if k.get("room") else ""))
        dlg.setMinimumSize(560, 420)
        lay = QVBoxLayout(dlg)
        info = QLabel("")
        info.setObjectName("cardTitle")
        lay.addWidget(info)
        # Global "Lokal media kesh" o'chiq bo'lsa — hech narsa yuklanmaydi.
        # Admin sababini bilsin (aks holda hammasi "Navbatda" qotib turadi).
        try:
            cache_on = str(db.get_settings().get("media_cache", "1")) != "0"
        except Exception:
            cache_on = True
        if not cache_on:
            warn = QLabel("⚠ «Lokal media kesh» Sozlamalarda O'CHIRILGAN — "
                          "kiosklar yuklamaydi. Yoqib qo'ying.")
            warn.setStyleSheet("color:#B45309; background:#FEF3C7;"
                               " border:1px solid #FCD34D; border-radius:8px;"
                               " padding:8px 12px; font-weight:600;")
            warn.setWordWrap(True)
            lay.addWidget(warn)

        # --- Shu kiosk uchun lokal kesh yoq/yo'q (xotirasiz kiosklar uchun) ---
        from ui.toggle import ToggleSwitch
        crow = QHBoxLayout()
        clbl = QLabel("Bu kioskda lokal kesh (kontentni diskka yuklab olish):")
        clbl.setStyleSheet("font-weight: 600;")
        crow.addWidget(clbl)
        crow.addStretch(1)
        dev_toggle = ToggleSwitch()
        dev_toggle.setChecked(bool(k.get("cache_enabled", 1)))
        dev_toggle.setEnabled(bool(dev))
        dev_toggle.toggled.connect(
            lambda on, d=dev: self._set_kiosk_cache_enabled(d, on))
        crow.addWidget(dev_toggle)
        lay.addLayout(crow)

        table = QTableWidget(len(av), 3)
        table.setHorizontalHeaderLabels(["Holat", "Nomi", "Turi"])
        th = table.horizontalHeader()
        th.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._setup_table(table)
        from ui.styles import TYPE_LABELS
        # Nomi/Turi ustunlari o'zgarmaydi — bir marta to'ldiramiz
        for r, c in enumerate(av):
            table.setItem(r, 0, QTableWidgetItem(""))
            table.setItem(r, 1, QTableWidgetItem(c.get("title") or ""))
            table.setItem(r, 2, QTableWidgetItem(
                TYPE_LABELS.get(c.get("type"), c.get("type"))))
        lay.addWidget(table, 1)

        def _refresh_status():
            """Heartbeat'dan kelgan jonli holatni o'qib qatorlarni yangilaydi:
            ✓ Yuklandi / ⬇ NN% / ○ Navbatda."""
            row = next((x for x in db.get_kiosks()
                        if x.get("device_id") == dev), None) if dev else None
            if row is None:
                row = k
            try:
                cur_ids = set(json.loads(row.get("cached_ids") or "[]"))
            except (ValueError, TypeError):
                cur_ids = set()
            try:
                cg = json.loads(row.get("caching") or "null") or {}
            except (ValueError, TypeError):
                cg = {}
            cg_id = cg.get("id")
            cg_pct = cg.get("pct", -1)
            done = len(cur_ids & {c["id"] for c in av})
            head = f"Yuklangan: {done} / {len(av)} ta media"
            if cg_id is not None and cg_id not in cur_ids:
                pc = f"{cg_pct}%" if isinstance(cg_pct, int) and cg_pct >= 0 \
                     else "yuklanmoqda…"
                head += f"   •   Hozir: «{cg.get('title') or ''}» {pc}"
            info.setText(head)
            for r, c in enumerate(av):
                it = table.item(r, 0)
                if c["id"] in cur_ids:
                    it.setText("✓ Yuklandi"); it.setForeground(QColor("#16A34A"))
                elif c["id"] == cg_id:
                    pc = f"{cg_pct}%" if isinstance(cg_pct, int) and cg_pct >= 0 \
                         else "yuklanmoqda…"
                    it.setText(f"⬇ {pc}"); it.setForeground(QColor("#2563EB"))
                else:
                    it.setText("○ Navbatda"); it.setForeground(QColor("#94A3B8"))

        _refresh_status()
        # Jonli yangilanish (heartbeat har ~5s keladi — biz 1.5s da o'qiymiz)
        live = QTimer(dlg)
        live.timeout.connect(_refresh_status)
        live.start(1500)
        dlg.finished.connect(lambda _r: live.stop())
        # Pastki qator: hoziroq yuklash + keshni tozalash + Yopish
        foot = QHBoxLayout()
        online = k.get("device_id") in {c.get("device_id")
                                        for c in ws.manager.clients()}
        sync_btn = self._btn("Hoziroq yukla", "refresh-cw",
                             lambda: self._sync_kiosk_cache(k),
                             kind="primary")
        sync_btn.setEnabled(bool(online and k.get("device_id")))
        if not online:
            sync_btn.setToolTip("Kiosk oflayn — buyruq qabul qilolmaydi")
        foot.addWidget(sync_btn)
        clear_btn = self._btn("Bu kioskning keshini tozalash", "trash-2",
                              lambda: self._clear_kiosk_cache(k, dlg),
                              kind="ghost")
        clear_btn.setEnabled(bool(online and k.get("device_id")))
        if not online:
            clear_btn.setToolTip("Kiosk oflayn — buyruq qabul qilolmaydi")
        foot.addWidget(clear_btn)
        # Registrdan o'chirish — eskirgan/almashtirilgan qurilma litsenziya
        # kiosk-limitidagi o'rnini bo'shatadi (yangi kiosk shu o'ringa kiradi).
        del_btn = self._btn("Registrdan o'chirish", "trash-2",
                            lambda: self._delete_kiosk(k, dlg), kind="danger")
        del_btn.setEnabled(bool(k.get("device_id")))
        del_btn.setToolTip("Qurilmani ro'yxatdan o'chiradi — litsenziya "
                           "limitidagi o'rni bo'shaydi. Qurilma yana ulansa "
                           "qaytadan (navbat oxiridan) ro'yxatga tushadi.")
        foot.addWidget(del_btn)
        foot.addStretch(1)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        # Close tugmasi "reject" rolida — `rejected` o'zi yetarli. `clicked`'ni
        # ham accept'ga ulasak bitta bosishda accept+reject ikkalasi otiladi.
        btns.rejected.connect(dlg.reject)
        foot.addWidget(btns)
        lay.addLayout(foot)
        dlg.exec()

    def _delete_kiosk(self, k, dlg):
        """Kiosk yozuvini registrdan o'chiradi (litsenziya limitida o'rin
        bo'shaydi). Qurilma hali ham ulanib tursa keyingi heartbeat'da qayta
        ro'yxatga tushadi — bu tugma eskirgan/almashtirilgan qurilmalar uchun."""
        dev = k.get("device_id")
        if not dev:
            return
        name = k.get("kiosk_no") or dev
        if QMessageBox.question(
                self, "Registrdan o'chirish",
                f"«{name}» qurilmasi ro'yxatdan o'chirilsinmi?\n\n"
                "Litsenziya kiosk-limitidagi o'rni bo'shaydi. Qurilma hali "
                "ishlayotgan bo'lsa, keyingi ulanishda qayta ro'yxatga tushadi."
                ) != QMessageBox.StandardButton.Yes:
            return
        db.delete_kiosk(dev)
        db.log_action("kiosk_delete", dev)
        self.statusBar().showMessage(f"«{name}» registrdan o'chirildi.", 4000)
        dlg.accept()
        self._update_status()   # kiosk jadvali darhol yangilanadi

    def _clear_kiosk_cache(self, k, dlg):
        """Tanlangan kioskka faqat o'ziga «keshni tozalash» buyrug'ini yuboradi."""
        dev = k.get("device_id")
        if not dev:
            return
        name = k.get("kiosk_no") or dev
        if QMessageBox.question(
                self, "Keshni tozalash",
                f"«{name}» kioskining lokal media keshi o'chirilsinmi?\n\n"
                "Kesh yoqiq bo'lsa fayllar keyingi sinxda qaytadan yuklanadi."
                ) != QMessageBox.StandardButton.Yes:
            return
        ws.manager.send_to_device_threadsafe(dev, {"type": "cache_clear"})
        db.log_action("cache_clear_device", dev)
        self.statusBar().showMessage(
            f"«{name}» keshini tozalash buyrug'i yuborildi.", 4000)
        dlg.accept()

    def _set_kiosk_cache_enabled(self, dev, on):
        """Admin shu kiosk uchun lokal keshni yoqadi/o'chiradi. Yoqilganда —
        darhol yuklash boshlanadi; o'chirilganда — yuklash to'xtaydi (mavjud
        keshni «...keshini tozalash» tugmasi bilan bo'shatish mumkin)."""
        if not dev:
            return
        db.set_kiosk_cache_enabled(dev, on)
        db.log_action("kiosk_cache_" + ("on" if on else "off"), dev)
        if on:
            ws.manager.send_to_device_threadsafe(dev, {"type": "cache_sync"})
            self.statusBar().showMessage(
                "Bu kioskда lokal kesh YOQILDI — yuklash boshlanadi.", 4000)
        else:
            self.statusBar().showMessage(
                "Bu kioskда lokal kesh O'CHIRILDI — yangi yuklash to'xtaydi "
                "(joyni bo'shatish uchun «...keshini tozalash»ни bosing).", 6000)

    def _sync_kiosk_cache(self, k):
        """Kioskka «hoziroq yukla» buyrug'ini yuboradi — media sinxni darhol
        ishga tushiradi (oyna ochiq qoladi, foiz jonli ko'rinadi)."""
        dev = k.get("device_id")
        if not dev:
            return
        name = k.get("kiosk_no") or dev
        ws.manager.send_to_device_threadsafe(dev, {"type": "cache_sync"})
        db.log_action("cache_sync_device", dev)
        self.statusBar().showMessage(
            f"«{name}» — yuklash boshlandi (sinx buyrug'i yuborildi).", 4000)

    def _update_stats(self):
        """Dashboard'dagi kontent/reklama/sayt sonlarini yangilaydi."""
        try:
            self._stat_lbls["content"].setText(str(len(db.get_content())))
            self._stat_lbls["ads"].setText(str(len(db.get_ads(active_only=False))))
            self._stat_lbls["sites"].setText(str(len(db.get_sites())))
        except Exception:
            pass  # DB hali tayyor bo'lmasa — keyingi siklda

    def send_announcement(self):
        text = self.ann_input.text().strip()
        if not text:
            return
        ws.manager.broadcast_threadsafe({"type": "announcement", "text": text})
        self.ann_input.clear()
        n = len(ws.manager.clients())
        db.log_action("announcement_sent", text)
        self.statusBar().showMessage(
            f"E'lon yuborildi ({n} ta kioskka): {text}", 5000)
