"""ui/dialogs.py — Kontent, reklama va umumiy yozuv dialoglari."""
import os
import shutil

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFormLayout, QLineEdit, QComboBox, QTextEdit, QCheckBox, QDialog,
    QFileDialog, QMessageBox, QDialogButtonBox, QSpinBox, QDoubleSpinBox
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap

import config
import db
from icons import svg_icon, svg_pixmap
from ui.styles import (
    CONTENT_TYPES, TYPE_LABELS, VIDEO_EXT, AUDIO_EXT, IMAGE_EXT, TEXT_EXT
)
from ui.helpers import _media_duration, _title_from_filename

# Janr/Tab combo'lari uchun turga mos standart takliflar (bazadagi mavjud
# qiymatlar bilan birlashtiriladi; admin yangisini yozsa ham bo'ladi).
DEFAULT_GENRES = {
    "movie":     ("Badiiy", "Komediya", "Drama", "Sarguzasht", "Tarixiy",
                  "Hujjatli", "Detektiv"),
    "cartoon":   ("Multfilm", "Sarguzasht", "Ertak", "O'quv"),
    "music":     ("Estrada", "Xalq musiqasi", "Klassik", "Zamonaviy",
                  "Instrumental"),
    "book":      ("Badiiy", "She'riyat", "Tarixiy", "Ilmiy", "Bolalar adabiyoti",
                  "Sarguzasht"),
    "audiobook": ("Badiiy", "She'riyat", "Tarixiy", "Ilmiy", "Bolalar adabiyoti",
                  "Sarguzasht"),
}
DEFAULT_TABS = {
    "movie":     ("Kinolar", "Hujjatli", "Bolalarga"),
    "cartoon":   ("Multfilmlar", "Bolalarga"),
    "music":     ("Musiqa", "Konsert"),
    "book":      ("Badiiy", "She'riyat", "Bolalarga", "Tarixiy"),
    "audiobook": ("Badiiy", "She'riyat", "Bolalarga", "Tarixiy"),
}


# ----------------------------------------------------------------------------
#  Kontent qo'shish/tahrirlash dialogi
# ----------------------------------------------------------------------------
class ContentDialog(QDialog):
    def __init__(self, parent=None, item=None):
        super().__init__(parent)
        self.item = item or {}
        self.media_src = None   # tanlangan media fayl yo'li
        self.cover_src = None   # tanlangan muqova rasmi
        self.text_src = None    # tanlangan kitob matni (json/txt)
        self.setWindowTitle("Kontentni tahrirlash" if item else "Yangi kontent qo'shish")
        self.setMinimumWidth(640)
        self.setAcceptDrops(True)   # fayllarni tortib tashlash mumkin
        self._build()
        self._on_type_changed()
        self._update_cover_preview(self.item.get("cover_path"))

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(12)

        # Tepa: chapda forma, o'ngda muqova preview
        top = QHBoxLayout()
        top.setSpacing(18)
        form = QFormLayout()
        form.setSpacing(10)
        self.form = form

        self.type = QComboBox()
        for t in CONTENT_TYPES:
            self.type.addItem(TYPE_LABELS[t], t)
        if self.item.get("type"):
            self.type.setCurrentIndex(CONTENT_TYPES.index(self.item["type"]))
        self.type.currentIndexChanged.connect(self._on_type_changed)

        self.title = QLineEdit(self.item.get("title", ""))
        self.author = QLineEdit(self.item.get("author") or "")
        # Til — kioskda tanlangan interfeys tiliga mos kontentgina ko'rinadi.
        # "Barcha tillarda" — til ahamiyatsiz kontent (instrumental musiqa,
        # tabiat videosi) har tilda chiqaveradi.
        self.lang = QComboBox()
        self.lang.addItem("O'zbekcha", "uz")
        self.lang.addItem("Ruscha", "ru")
        self.lang.addItem("Inglizcha", "en")
        self.lang.addItem("Barcha tillarda (til ahamiyatsiz)", None)
        li = self.lang.findData(self.item.get("lang", "uz"))
        self.lang.setCurrentIndex(li if li >= 0 else 3)

        # Janr/Tab — tanlanadigan (lekin yozish ham mumkin) combo'lar:
        # takliflar = turga mos standartlar + bazada allaqachon ishlatilganlar
        self.genre = QComboBox()
        self.genre.setEditable(True)
        self.genre.lineEdit().setPlaceholderText("Tanlang yoki yozing...")
        self.genre.setCurrentText(self.item.get("genre") or "")
        self.tab = QComboBox()
        self.tab.setEditable(True)
        self.tab.lineEdit().setPlaceholderText(
            "Masalan: Kinolar, Badiiy, Bolalarga...")
        self.tab.setCurrentText(self.item.get("category_tab") or "")
        self.desc = QTextEdit(self.item.get("description") or "")
        self.desc.setFixedHeight(80)

        self.duration = QSpinBox()
        self.duration.setRange(0, 10_000_000)
        self.duration.setValue(self.item.get("duration") or 0)
        self.duration.setSuffix(" soniya")

        self.pages = QSpinBox()
        self.pages.setRange(0, 100000)
        self.pages.setValue(self.item.get("pages") or 0)
        self.pages.setSuffix(" sahifa")

        self.recommended = QCheckBox("Tavsiya blokida ko'rsatilsin")
        self.recommended.setChecked(bool(self.item.get("is_recommended")))

        # Belgilansa — kiosklar bu faylni o'z diskiga fonda yuklab oladi
        # (oflayn ijro); belgilanmasa — faqat serverdan striming.
        self.cacheable = QCheckBox(
            "Kiosklarga yuklab qo'yilsin (lokal kesh)")
        self.cacheable.setChecked(
            bool(self.item.get("cache_enabled", 1)))

        form.addRow("Turi:", self.type)
        form.addRow("Nomi:", self.title)
        form.addRow("Tili:", self.lang)
        form.addRow("Muallif:", self.author)
        form.addRow("Janr:", self.genre)
        form.addRow("Tab (kategoriya):", self.tab)
        form.addRow("Tavsif:", self.desc)
        form.addRow("Davomiylik:", self.duration)
        form.addRow("Sahifalar:", self.pages)

        # Fayl tanlash qatorlari (har biri alohida widget — turga qarab yashiriladi)
        self.file_label, self.media_widget = self._pick_row(
            self.item.get("file_path"), "video",
            "Media (*.mp4 *.mkv *.avi *.mp3 *.m4a *.wav);; Barcha fayllar (*.*)",
            "media")
        self.cover_label, self.cover_widget = self._pick_row(
            self.item.get("cover_path"), "image",
            "Rasm (*.jpg *.jpeg *.png *.webp *.svg);; Barcha fayllar (*.*)",
            "cover")
        self.text_label, self.text_widget = self._pick_row(
            self.item.get("text_path"), "file-text",
            "Kitob matni (*.json *.txt);; Barcha fayllar (*.*)",
            "text")
        form.addRow("Media fayl:", self.media_widget)
        form.addRow("Muqova rasmi:", self.cover_widget)
        form.addRow("Kitob matni:", self.text_widget)
        form.addRow("", self.recommended)
        form.addRow("", self.cacheable)
        top.addLayout(form, 1)

        # Muqova preview (o'ngda)
        prev_col = QVBoxLayout()
        prev_col.setSpacing(6)
        self.cover_preview = QLabel("Muqova\nyo'q")
        self.cover_preview.setObjectName("coverPrev")
        self.cover_preview.setFixedSize(160, 214)
        self.cover_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        prev_col.addWidget(self.cover_preview)
        prev_col.addStretch(1)
        top.addLayout(prev_col)
        lay.addLayout(top)

        drop = QLabel("Maslahat: media, rasm yoki matn faylini shu oynaga tortib "
                      "tashlasangiz — turi avtomatik aniqlanadi (davomiylik ham).")
        drop.setObjectName("dropHint")
        drop.setWordWrap(True)
        lay.addWidget(drop)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    # Turga mos yorliqlar (nomi / muallif / muqova) — har turda mazmunan to'g'ri
    # so'z chiqsin (musiqada "Ijrochi", kinoda "Rejissor", kitobda "Muallif").
    _FIELD_LABELS = {
        "movie":     ("Kino nomi", "Rejissor", "Afisha (poster)"),
        "cartoon":   ("Multfilm nomi", "Studiya", "Afisha (poster)"),
        "music":     ("Qo'shiq nomi", "Ijrochi", "Albom muqovasi"),
        "book":      ("Kitob nomi", "Muallif", "Muqova"),
        "audiobook": ("Audiokitob nomi", "Muallif", "Muqova"),
    }

    def _set_row_label(self, widget, text):
        lbl = self.form.labelForField(widget)
        if lbl is not None:
            lbl.setText(text)

    def _on_type_changed(self):
        """Turga qarab faqat mos maydonlarni ko'rsatadi (ortiqcha ish bo'lmasin),
        yorliqlarni turga moslaydi va Janr/Tab takliflarini yangilaydi."""
        t = self.type.currentData()
        is_book = t == "book"
        # Kitob endi AUDIO ham qabul qiladi (matn + audio bitta yozuvda).
        # Sahifalar va Tab kitobda yashirin (ortiqcha).
        has_dur = t in ("movie", "cartoon", "music", "audiobook")
        has_media = t in ("movie", "cartoon", "music", "audiobook") or is_book
        has_text = t in ("book", "audiobook")
        self.form.setRowVisible(self.duration, has_dur)
        self.form.setRowVisible(self.pages, False)        # Sahifalar olib tashlandi
        self.form.setRowVisible(self.media_widget, has_media)
        self.form.setRowVisible(self.text_widget, has_text)
        self.form.setRowVisible(self.tab, not is_book)    # Tab kitobda yashirin
        # Lokal kesh faqat media fayli bor turlarga tegishli
        self.form.setRowVisible(self.cacheable, has_media)
        # Turga mos yorliqlar
        tl, al, cl = self._FIELD_LABELS.get(t, ("Nomi", "Muallif", "Muqova rasmi"))
        self._set_row_label(self.title, tl + ":")
        self._set_row_label(self.author, al + ":")
        self._set_row_label(self.cover_widget, cl + ":")
        # Kitobda media — bu AUDIO; boshqalarda umumiy media
        self._set_row_label(self.media_widget,
                            "Audio fayl (ixtiyoriy):" if is_book else "Media fayl:")
        # Musiqa uchun "Ijrochi" placeholder ham mos bo'lsin
        self.author.setPlaceholderText(al)
        self._fill_suggestions(self.genre, DEFAULT_GENRES.get(t, ()),
                               "genre", t)
        self._fill_suggestions(self.tab, DEFAULT_TABS.get(t, ()),
                               "category_tab", t)

    @staticmethod
    def _fill_suggestions(combo, defaults, field, ctype):
        """Editable combo ro'yxatini yangilaydi: standart takliflar + shu tur
        bo'yicha bazada mavjud qiymatlar. Yozilgan joriy matn saqlanadi."""
        cur = combo.currentText().strip()
        vals = list(defaults)
        for v in db.content_field_values(field, ctype):
            if v not in vals:
                vals.append(v)
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(vals)
        combo.setCurrentText(cur)   # tanlov/yozilgan matn yo'qolmasin
        combo.blockSignals(False)

    def _pick_row(self, current, icon_name, file_filter, kind):
        """'Fayl nomi + Tanlash...' qatorini yasaydi; (label, widget) qaytaradi."""
        cont = QWidget()
        row = QHBoxLayout(cont)
        row.setContentsMargins(0, 0, 0, 0)
        label = QLabel(current or "Tanlanmagan")
        label.setObjectName("muted" if current else "hint")
        pick = QPushButton(" Tanlash...")
        pick.setObjectName("ghost")
        pick.setIcon(svg_icon(icon_name, "#334155", 32))
        pick.setIconSize(QSize(16, 16))
        pick.clicked.connect(lambda: self._pick_file(kind, file_filter))
        row.addWidget(label, 1)
        row.addWidget(pick)
        cont._label = label
        return label, cont

    def _pick_file(self, kind, file_filter):
        path, _ = QFileDialog.getOpenFileName(self, "Fayl tanlash", "", file_filter)
        if path:
            self._set_file(kind, path)

    @staticmethod
    def _looks_like_webpage(path):
        """Fayl aslida HTML sahifa (saytdan xato yuklangan) bo'lsa True —
        media/rasm o'rniga .mp3/.mp4 deb saqlangan veb-sahifani ushlaydi."""
        try:
            with open(path, "rb") as f:
                head = f.read(64).lstrip().lower()
        except OSError:
            return False
        return (head.startswith(b"<!doctype") or head.startswith(b"<html")
                or head.startswith(b"<?xml") or head.startswith(b"<head"))

    def _set_file(self, kind, path):
        """Tanlangan/tashlangan faylni biriktiradi va aqlli to'ldirishni bajaradi."""
        # Media/rasm o'rniga HTML sahifa tanlangan bo'lsa (saytdan xato yuklash)
        # — kioskda ochilmaydi. Darrov ogohlantiramiz va biriktirmaymiz.
        if kind in ("media", "cover") and self._looks_like_webpage(path):
            QMessageBox.warning(
                self, "Noto'g'ri fayl",
                "Bu media/rasm fayl emas — HTML sahifa (saytdan xato yuklangan "
                "bo'lishi mumkin).\n\nHaqiqiy .mp3/.mp4/.jpg faylni tanlang "
                "(saytda fayl ustida o'ng tugma → 'Faylni saqlash').")
            return
        setattr(self, kind + "_src", path)
        label = {"media": self.file_label, "cover": self.cover_label,
                 "text": self.text_label}[kind]
        label.setText(os.path.basename(path))
        label.setStyleSheet("color: #0F172A;")
        if kind == "media":
            if not self.title.text().strip():
                self.title.setText(_title_from_filename(path))
            dur = _media_duration(path)
            if dur:
                self.duration.setValue(dur)
        elif kind == "cover":
            self._update_cover_preview(path)

    def _update_cover_preview(self, src):
        """Muqova rasmini preview maydonida ko'rsatadi (fayl yo'li yoki nomi)."""
        if not src:
            self.cover_preview.setPixmap(QPixmap())
            self.cover_preview.setText("Muqova\nyo'q")
            return
        path = src if os.path.isabs(src) else os.path.join(config.COVERS_DIR, src)
        pm = QPixmap(path)
        if pm.isNull():
            self.cover_preview.setPixmap(QPixmap())
            self.cover_preview.setText("Muqova\nko'rinmadi")
            return
        self.cover_preview.setText("")
        self.cover_preview.setPixmap(pm.scaled(
            self.cover_preview.size(), Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))

    # --- Drag & drop ---
    def _route_kind(self, path):
        ext = os.path.splitext(path)[1].lower()
        if ext in VIDEO_EXT or ext in AUDIO_EXT:
            return "media"
        if ext in IMAGE_EXT:
            return "cover"
        if ext in TEXT_EXT:
            return "text"
        return None

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        for url in e.mimeData().urls():
            path = url.toLocalFile()
            if not path:
                continue
            kind = self._route_kind(path)
            if kind:
                self._set_file(kind, path)
        e.acceptProposedAction()

    def _accept(self):
        if not self.title.text().strip():
            QMessageBox.warning(self, "Xato", "Nomi bo'sh bo'lmasligi kerak.")
            return
        # Media/matn fayli majburiy — fayl yo'q yozuv kioskda 404 beradi
        # (tahrirda eskisi saqlanib qoladi: self.item'dagi yo'l yetarli)
        t = self.type.currentData()
        if t in ("movie", "cartoon", "music", "audiobook"):
            if not (self.media_src or self.item.get("file_path")):
                QMessageBox.warning(
                    self, "Xato",
                    "Video/audio fayl tanlanmagan — bu turdagi kontent "
                    "faylsiz kioskda ochilmaydi.")
                return
        elif t == "book":
            has_text = self.text_src or self.item.get("text_path")
            has_audio = self.media_src or self.item.get("file_path")
            if not (has_text or has_audio):
                QMessageBox.warning(
                    self, "Xato",
                    "Kitob uchun kamida bittasini tanlang: matn fayli "
                    "(.txt/.json) yoki audio fayl.")
                return
        self.accept()

    def values(self):
        """Dialogdagi qiymatlarni DB uchun dict qilib qaytaradi."""
        data = {
            "type": self.type.currentData(),
            "title": self.title.text().strip(),
            "author": self.author.text().strip() or None,
            "genre": self.genre.currentText().strip() or None,
            "category_tab": self.tab.currentText().strip() or None,
            "description": self.desc.toPlainText().strip() or None,
            "duration": self.duration.value() or None,
            "pages": self.pages.value() or None,
            "lang": self.lang.currentData(),
            "lang_group": self.item.get("lang_group"),   # bog'lanish saqlansin
            "cache_enabled": 1 if self.cacheable.isChecked() else 0,
            "is_recommended": 1 if self.recommended.isChecked() else 0,
        }
        # Tanlangan fayllarni content/ ostidagi papkalarga ko'chiramiz
        for src, dst_dir, key in (
                (self.media_src, config.MEDIA_DIR, "file_path"),
                (self.cover_src, config.COVERS_DIR, "cover_path"),
                (self.text_src, config.BOOKS_DIR, "text_path")):
            if src:
                os.makedirs(dst_dir, exist_ok=True)
                dst_name = os.path.basename(src)
                shutil.copy2(src, os.path.join(dst_dir, dst_name))
                data[key] = dst_name
        return data


# ----------------------------------------------------------------------------
#  Reklama qo'shish/tahrirlash dialogi
# ----------------------------------------------------------------------------
class AdDialog(QDialog):
    """Reklama: media fayl (rasm YOKI video), namoyish davomiyligi va kunlik
    vaqt oralig'i (qaysi soatlarda ko'rsatilsin).

    - Rasm: `duration` soniya ko'rsatiladi.
    - Video: `duration` = 0 bo'lsa video oxirigacha o'ynaydi.
    - start/end bo'sh bo'lsa — kun bo'yi ko'rsatiladi."""

    def __init__(self, parent=None, item=None):
        super().__init__(parent)
        self.item = item or {}
        self.media_src = None
        self.setWindowTitle("Reklamani tahrirlash" if item else "Yangi reklama")
        self.setMinimumWidth(640)
        self.setAcceptDrops(True)
        self._build()
        self._update_preview(self.item.get("media_path"))

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(12)

        top = QHBoxLayout()
        top.setSpacing(18)
        form = QFormLayout()
        form.setSpacing(10)

        self.title = QLineEdit(self.item.get("title") or "")
        self.title.setPlaceholderText("Bo'sh qoldirsangiz fayl nomidan olinadi")

        # Media fayl qatori
        cont = QWidget()
        row = QHBoxLayout(cont)
        row.setContentsMargins(0, 0, 0, 0)
        cur = self.item.get("media_path")
        self.media_label = QLabel(cur or "Tanlanmagan")
        self.media_label.setObjectName("muted" if cur else "hint")
        pick = QPushButton(" Tanlash...")
        pick.setObjectName("ghost")
        pick.setIcon(svg_icon("image", "#334155", 32))
        pick.setIconSize(QSize(16, 16))
        pick.clicked.connect(self._pick_media)
        row.addWidget(self.media_label, 1)
        row.addWidget(pick)

        # Namoyish vaqti — faqat RASM uchun (video davomiyligi fayldan olinadi)
        self.duration = QSpinBox()
        self.duration.setRange(1, 600)
        self.duration.setValue(self.item.get("duration") or 10)
        self.duration.setSuffix(" soniya")
        self.dur_note = QLabel("Video davomiyligi fayldan avtomatik olinadi — "
                               "reklama video tugaguncha ko'rinadi.")
        self.dur_note.setObjectName("hint")
        self.dur_note.setWordWrap(True)
        self._video_dur = None   # yangi tanlangan videoning davomiyligi

        # Joylashuv: popup (qalqib chiquvchi), asosiy sahifa banneri yoki ikkalasi.
        # Banner — bosh sahifa chap ustunidagi katta rasm: bir nechta banner
        # reklama bo'lsa «Namoyish vaqti» soniyasida aylanib turadi.
        self.placement = QComboBox()
        self.placement.addItem("Qalqib chiquvchi oyna (popup)", "popup")
        self.placement.addItem("Asosiy sahifa banneri", "banner")
        self.placement.addItem("Ikkalasi — popup ham, banner ham", "both")
        idx = self.placement.findData(self.item.get("placement") or "popup")
        self.placement.setCurrentIndex(max(0, idx))
        self.placement.currentIndexChanged.connect(
            lambda _i: self._sync_dur_row())

        # Har necha daqiqada chiqishi (takrorlanish oralig'i)
        self.interval = QSpinBox()
        self.interval.setRange(1, 720)
        self.interval.setSuffix(" daqiqada bir marta")
        default_int = 5
        try:
            default_int = int(float(
                db.get_settings().get("ad_interval_min") or 5))
        except (TypeError, ValueError):
            pass
        self.interval.setValue(self.item.get("interval_min") or default_int)

        self.start_t = QLineEdit(self.item.get("start_time") or "")
        self.start_t.setPlaceholderText("08:00 (bo'sh = doim)")
        self.end_t = QLineEdit(self.item.get("end_time") or "")
        self.end_t.setPlaceholderText("20:00")

        self.active = QCheckBox("Kioskda ko'rsatilsin")
        self.active.setChecked(bool(self.item.get("is_active", 1)))

        self.form = form
        form.addRow("Sarlavha:", self.title)
        form.addRow("Media (rasm/video):", cont)
        form.addRow("Joylashuv:", self.placement)
        form.addRow("Namoyish vaqti:", self.duration)
        form.addRow("", self.dur_note)
        form.addRow("Har necha daqiqada:", self.interval)
        form.addRow("Boshlanishi:", self.start_t)
        form.addRow("Tugashi:", self.end_t)
        form.addRow("", self.active)
        top.addLayout(form, 1)
        self._sync_dur_row()

        # O'ngda media preview
        prev_col = QVBoxLayout()
        prev_col.setSpacing(6)
        self.preview = QLabel("Media\nyo'q")
        self.preview.setObjectName("coverPrev")
        self.preview.setFixedSize(220, 124)   # 16:9
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        prev_col.addWidget(self.preview)
        prev_col.addStretch(1)
        top.addLayout(prev_col)
        lay.addLayout(top)

        hint = QLabel("Reklama kioskda qalqib chiquvchi oynada teskari hisob "
                      "bilan chiqadi va vaqti tugagach o'zi yopiladi: rasm — "
                      "«Namoyish vaqti» soniya, video — o'z davomiyligicha. "
                      "«Har necha daqiqada» — shu reklama qancha tez-tez "
                      "takrorlanishi. Vaqt oralig'i bo'sh bo'lsa kun bo'yi "
                      "navbatda. Faylni shu oynaga tortib tashlash ham mumkin.")
        hint.setObjectName("dropHint")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    # --- Media tanlash / preview ---
    def _pick_media(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Reklama faylini tanlash", "",
            "Media (*.jpg *.jpeg *.png *.webp *.mp4 *.mkv *.avi *.mov *.webm);;"
            " Barcha fayllar (*.*)")
        if path:
            self._set_media(path)

    def _set_media(self, path):
        self.media_src = path
        self.media_label.setText(os.path.basename(path))
        self.media_label.setStyleSheet("color: #0F172A;")
        if not self.title.text().strip():
            self.title.setText(_title_from_filename(path))
        # Video bo'lsa davomiylik fayldan avtomatik (admin kiritmaydi)
        if self._is_video(path):
            self._video_dur = _media_duration(path) or 0
        self._sync_dur_row()
        self._update_preview(path)

    def _sync_dur_row(self):
        """Rasm — «Namoyish vaqti» ko'rinadi; video — izoh ko'rinadi.
        «Har necha daqiqada» faqat popup uchun ma'noli (banner aylanmasini
        «Namoyish vaqti» boshqaradi)."""
        is_video = self._is_video(self.media_src or self.item.get("media_path"))
        place = self.placement.currentData()
        self.form.setRowVisible(self.interval, place != "banner")
        self.form.setRowVisible(self.duration, not is_video)
        self.form.setRowVisible(self.dur_note,
                                is_video or place in ("banner", "both"))
        if is_video and place in ("banner", "both"):
            self.dur_note.setText(
                "DIQQAT: video bannerda ko'rsatilmaydi (faqat popup'da). "
                "Banner uchun rasm tanlang.")
        elif is_video:
            self.dur_note.setText(
                "Video davomiyligi fayldan avtomatik olinadi — reklama video "
                "tugaguncha ko'rinadi.")
        else:
            self.dur_note.setText(
                "Banner — bosh sahifadagi katta rasm joyi: bir nechta banner "
                "reklama «Namoyish vaqti» soniyasida almashinib turadi.")

    @staticmethod
    def _is_video(name):
        return os.path.splitext(name or "")[1].lower() in VIDEO_EXT

    def _update_preview(self, src):
        if not src:
            self.preview.setPixmap(QPixmap())
            self.preview.setText("Media\nyo'q")
            return
        path = src if os.path.isabs(src) else os.path.join(config.ADS_DIR, src)
        if self._is_video(path):
            self.preview.setPixmap(svg_pixmap("clapperboard", "#64748B", 40))
            return
        pm = QPixmap(path)
        if pm.isNull():
            self.preview.setPixmap(QPixmap())
            self.preview.setText("Ko'rinmadi")
            return
        self.preview.setText("")
        self.preview.setPixmap(pm.scaled(
            self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))

    # --- Drag & drop ---
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        for url in e.mimeData().urls():
            path = url.toLocalFile()
            ext = os.path.splitext(path)[1].lower()
            if path and (ext in VIDEO_EXT or ext in IMAGE_EXT):
                self._set_media(path)
                break
        e.acceptProposedAction()

    # --- Validatsiya / qiymatlar ---
    def _accept(self):
        import re
        media_name = self.media_src or self.item.get("media_path")
        if not media_name:
            QMessageBox.warning(self, "Xato",
                                "Media fayl tanlanmagan — reklama rasm yoki "
                                "videosiz kioskda ko'rinmaydi.")
            return
        # Sarlavha bo'sh bo'lsa fayl nomidan to'ldiramiz (admin yozmasa ham bo'ladi)
        if not self.title.text().strip():
            self.title.setText(_title_from_filename(media_name))
        # Banner faqat rasm ko'rsatadi — video bilan banner-only saqlanmasin
        if (self.placement.currentData() == "banner"
                and self._is_video(media_name)):
            QMessageBox.warning(self, "Xato",
                                "Video bannerda ko'rsatilmaydi — banner uchun "
                                "rasm tanlang yoki joylashuvni popup qiling.")
            return
        st, en = self.start_t.text().strip(), self.end_t.text().strip()
        if bool(st) != bool(en):
            QMessageBox.warning(self, "Xato",
                                "Vaqt oralig'ining ikkala maydonini to'ldiring "
                                "(yoki ikkalasini bo'sh qoldiring).")
            return
        for t in (st, en):
            if t and not re.fullmatch(r"\d{1,2}:\d{2}", t):
                QMessageBox.warning(self, "Xato",
                                    "Vaqt HH:MM ko'rinishida bo'lsin "
                                    "(masalan 08:00).")
                return
        self.accept()

    def values(self):
        media_name = self.media_src or self.item.get("media_path")
        if self._is_video(media_name):
            # Video: davomiylik fayldan (yangi tanlangan) yoki avvalgisidan
            dur = (self._video_dur if self._video_dur is not None
                   else self.item.get("duration") or 0)
        else:
            dur = self.duration.value()
        data = {
            "title": self.title.text().strip(),
            "duration": dur,
            "interval_min": self.interval.value(),
            "start_time": self.start_t.text().strip() or None,
            "end_time": self.end_t.text().strip() or None,
            "placement": self.placement.currentData(),
            "is_active": 1 if self.active.isChecked() else 0,
        }
        if self.media_src:
            os.makedirs(config.ADS_DIR, exist_ok=True)
            dst_name = os.path.basename(self.media_src)
            shutil.copy2(self.media_src, os.path.join(config.ADS_DIR, dst_name))
            data["media_path"] = dst_name
        return data


# ----------------------------------------------------------------------------
#  Umumiy yozuv dialogi (reklama / sayt / bekat uchun)
# ----------------------------------------------------------------------------
class RecordDialog(QDialog):
    """Bitta jadval yozuvini tahrirlash dialogi.

    fields — [(key, label, kind), ...]; kind: text|multiline|int|float|bool.
    Shu bitta dialog reklama, sayt va bekat formalarini ham hosil qiladi
    (har biri uchun alohida sinf yozish shart emas)."""

    def __init__(self, parent, title, fields, item=None):
        super().__init__(parent)
        self.fields = fields
        self.item = item or {}
        self.widgets = {}
        self.setWindowTitle(title)
        self.setMinimumWidth(440)

        lay = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)
        for key, label, kind in fields:
            val = self.item.get(key)
            if kind == "multiline":
                w = QTextEdit("" if val is None else str(val))
                w.setFixedHeight(70)
            elif kind == "int":
                w = QSpinBox()
                w.setRange(0, 1_000_000)
                w.setValue(int(val or 0))
            elif kind == "float":
                w = QDoubleSpinBox()
                w.setRange(-1e9, 1e9)
                w.setDecimals(6)
                w.setValue(float(val) if val is not None else 0.0)
            elif kind == "bool":
                w = QCheckBox("Ha")
                w.setChecked(bool(val) if val is not None else True)
            else:  # text
                w = QLineEdit("" if val is None else str(val))
            self.widgets[key] = (w, kind)
            form.addRow(label + ":", w)
        lay.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def values(self):
        out = {}
        for key, (w, kind) in self.widgets.items():
            if kind == "multiline":
                out[key] = w.toPlainText().strip() or None
            elif kind in ("int", "float"):
                out[key] = w.value()
            elif kind == "bool":
                out[key] = 1 if w.isChecked() else 0
            else:
                out[key] = w.text().strip() or None
        return out
