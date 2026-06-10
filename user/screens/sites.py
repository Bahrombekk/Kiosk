"""
sites.py — Saytlar (Websites) bo'limi (TZ 8.12-8.13).

Kiosk internetga ulanmaydi — saytlar QR kod orqali yo'lovchining telefonida
ochiladi. Kartochkalar (ikonka plitka + nom + havola + tavsif + → tugma);
bosilganda detal modal: sarlavha karta, tavsif, imkoniyatlar ro'yxati va
QR kod + 3 qadamli yo'riqnoma.
"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QFrame, QLabel, QScrollArea, QPushButton,
                             QSizePolicy, QGraphicsDropShadowEffect)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QColor

from core import theme as T
from core.i18n import tr
from core.threads import track
from widgets.empty import EmptyState
from widgets.modal import Modal
from widgets.qr import QRWidget
from widgets.card import _svg_pixmap, _set_pressed
from widgets.spinner import StatusLabel

# --- Sayt turiga qarab ikonka (inline SVG, stroke=currentColor) ---
_ICONS = {
    "globe": ("<svg viewBox='0 0 24 24' fill='none'>"
              "<circle cx='12' cy='12' r='9' stroke='currentColor' stroke-width='1.9'/>"
              "<ellipse cx='12' cy='12' rx='4' ry='9' stroke='currentColor' stroke-width='1.9'/>"
              "<path d='M3.5 9h17M3.5 15h17' stroke='currentColor' stroke-width='1.9'/></svg>"),
    "ticket": ("<svg viewBox='0 0 24 24' fill='none'>"
               "<path d='M4 8.5C4 7.7 4.7 7 5.5 7h13c.8 0 1.5.7 1.5 1.5v2a1.8 1.8 0 0 0 0 3.6v.4"
               "c0 .8-.7 1.5-1.5 1.5h-13C4.7 16 4 15.3 4 14.5v-.4a1.8 1.8 0 0 0 0-3.6v-2Z'"
               " stroke='currentColor' stroke-width='1.7' stroke-linejoin='round'/>"
               "<path d='M13.5 7.5v8' stroke='currentColor' stroke-width='1.6' stroke-dasharray='2 2.4'/></svg>"),
    "mobile": ("<svg viewBox='0 0 24 24' fill='none'>"
               "<rect x='6.5' y='3' width='11' height='18' rx='2.4' stroke='currentColor' stroke-width='1.8'/>"
               "<path d='M10.5 18h3' stroke='currentColor' stroke-width='1.8' stroke-linecap='round'/></svg>"),
    "train": ("<svg viewBox='0 0 24 24' fill='none'>"
              "<rect x='5' y='4' width='14' height='12.5' rx='3' stroke='currentColor' stroke-width='1.8'/>"
              "<path d='M5 11h14' stroke='currentColor' stroke-width='1.8'/>"
              "<path d='M8.5 16.5 6.5 20M15.5 16.5 17.5 20' stroke='currentColor' stroke-width='1.8' stroke-linecap='round'/>"
              "<circle cx='9' cy='13.6' r='1' fill='currentColor'/><circle cx='15' cy='13.6' r='1' fill='currentColor'/></svg>"),
    "box": ("<svg viewBox='0 0 24 24' fill='none'>"
            "<path d='M12 3 21 7.5v9L12 21 3 16.5v-9L12 3Z' stroke='currentColor' stroke-width='1.7' stroke-linejoin='round'/>"
            "<path d='M3 7.5 12 12l9-4.5M12 12v9' stroke='currentColor' stroke-width='1.7' stroke-linejoin='round'/></svg>"),
    "send": ("<svg viewBox='0 0 24 24' fill='none'>"
             "<path d='M21 4 3.5 10.5l5.5 2 2 5.5L21 4Z' stroke='currentColor' stroke-width='1.7' stroke-linejoin='round'/>"
             "<path d='m9 15.5 3-3' stroke='currentColor' stroke-width='1.7' stroke-linecap='round'/></svg>"),
    "briefcase": ("<svg viewBox='0 0 24 24' fill='none'>"
                  "<rect x='3' y='7' width='18' height='13' rx='2.2' stroke='currentColor' stroke-width='1.8'/>"
                  "<path d='M8 7V5.5A1.5 1.5 0 0 1 9.5 4h5A1.5 1.5 0 0 1 16 5.5V7' stroke='currentColor' stroke-width='1.8'/></svg>"),
    "suitcase": ("<svg viewBox='0 0 24 24' fill='none'>"
                 "<rect x='5' y='8' width='14' height='12' rx='2.2' stroke='currentColor' stroke-width='1.8'/>"
                 "<path d='M9.5 8V6a1.5 1.5 0 0 1 1.5-1.5h2A1.5 1.5 0 0 1 14.5 6v2M9.5 8v12M14.5 8v12'"
                 " stroke='currentColor' stroke-width='1.8'/></svg>"),
    "building": ("<svg viewBox='0 0 24 24' fill='none'>"
                 "<rect x='5' y='3' width='14' height='18' rx='1.6' stroke='currentColor' stroke-width='1.8'/>"
                 "<path d='M9 7h2M13 7h2M9 11h2M13 11h2M9 15h2M13 15h2'"
                 " stroke='currentColor' stroke-width='1.8' stroke-linecap='round'/></svg>"),
}


def _icon_key(item):
    """Sayt nomi/havolasiga qarab mos ikonka kalitini tanlaydi."""
    s = ((item.get("name") or "") + " " + (item.get("url") or "")).lower()
    rules = [
        (("chipta", "ticket"), "ticket"),
        (("mobil", "ilova", "app"), "mobile"),
        (("cargo", "yuk"), "box"),
        (("telegram", "kanal", "t.me"), "send"),
        (("express", "afrosiy", "poyezd", "tezlik"), "train"),
        (("tour", "sayohat"), "suitcase"),
        (("vakansiya", "hr.", "ish"), "briefcase"),
        (("korporativ", "b2b", "mijoz"), "building"),
    ]
    for keys, icon in rules:
        if any(k in s for k in keys):
            return icon
    return "globe"


class _Loader(QThread):
    done = pyqtSignal(list)
    fail = pyqtSignal()

    def __init__(self, api):
        super().__init__()
        self.api = api

    def run(self):
        try:
            self.done.emit(self.api.get_sites())
        except Exception:
            self.fail.emit()


def _features(item):
    """features matnini ro'yxatga ajratadi (';' yoki yangi qator bo'yicha)."""
    raw = item.get("features") or ""
    parts = [p.strip() for p in raw.replace("\n", ";").split(";")]
    return [p for p in parts if p]


def _icon_tile(svg, accent, bg, size=52, icon_px=28, radius=15):
    """Yumaloq plitka ichida rangli ikonka (QLabel) qaytaradi."""
    tile = QLabel()
    tile.setObjectName("siteTile")
    tile.setFixedSize(T.s(size), T.s(size))
    tile.setAlignment(Qt.AlignmentFlag.AlignCenter)
    tile.setPixmap(_svg_pixmap(svg, accent, T.s(icon_px)))
    tile.setStyleSheet(
        f"#siteTile {{ background: {bg}; border-radius: {T.s(radius)}px; }}")
    return tile


class SiteCard(QFrame):
    clicked = pyqtSignal(dict)

    def __init__(self, item, theme_name="light"):
        super().__init__()
        self.item = item
        self.theme_name = theme_name
        self._icon = _ICONS[_icon_key(item)]
        self.setObjectName("siteCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.setMinimumHeight(T.s(230))

        # Faint globus suv-belgisi (orqa fonda, past-o'ngda)
        self._wm = QLabel(self)
        self._wm.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(T.s(22), T.s(22), T.s(22), T.s(22))
        lay.setSpacing(0)

        # Sarlavha: ikonka plitka + (nom, havola)
        head = QHBoxLayout()
        head.setSpacing(T.s(16))
        c = T.THEMES[theme_name]
        self.tile = _icon_tile(self._icon, c["accent"], c["surface2"])
        namecol = QVBoxLayout()
        namecol.setSpacing(T.s(4))
        self.name = QLabel(item.get("name", ""))
        self.name.setObjectName("siteName")
        self.name.setWordWrap(True)
        self.url = QLabel(item.get("url", ""))
        self.url.setObjectName("siteUrl")
        namecol.addWidget(self.name)
        namecol.addWidget(self.url)
        head.addWidget(self.tile, 0, Qt.AlignmentFlag.AlignTop)
        head.addLayout(namecol, 1)
        lay.addLayout(head)

        lay.addSpacing(T.s(16))
        self.desc = QLabel(item.get("description") or "")
        self.desc.setObjectName("siteDesc")
        self.desc.setWordWrap(True)
        self.desc.setAlignment(Qt.AlignmentFlag.AlignTop)
        lay.addWidget(self.desc)
        lay.addStretch(1)

        # Past-o'ngda → tugma (oq doira)
        arow = QHBoxLayout()
        arow.addStretch(1)
        self.arrow = QLabel("→")
        self.arrow.setObjectName("siteArrow")
        self.arrow.setFixedSize(T.s(46), T.s(46))
        self.arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arow.addWidget(self.arrow)
        lay.addLayout(arow)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(T.s(40))
        shadow.setOffset(0, T.s(14))
        shadow.setColor(QColor(40, 55, 90, 55))
        self.setGraphicsEffect(shadow)

        self.apply_theme(theme_name)

    def _place_wm(self):
        sz = T.s(150)
        self._wm.setFixedSize(sz, sz)
        self._wm.move(self.width() - sz + T.s(20), self.height() - sz + T.s(20))
        self._wm.lower()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._place_wm()

    def apply_theme(self, name):
        self.theme_name = name
        c = T.THEMES[name]
        self.tile.setPixmap(_svg_pixmap(self._icon, c["accent"], T.s(28)))
        self.tile.setStyleSheet(
            f"#siteTile {{ background: {c['surface2']}; border-radius: {T.s(15)}px; }}")
        # Suv-belgisi — juda och rang
        self._wm.setPixmap(_svg_pixmap(self._icon, "#EDF1F8", T.s(150)))
        self.setStyleSheet(
            f"#siteCard {{ background: {c['surface']};"
            f" border-radius: {T.RADIUS['card']}px; }}"
            f"#siteCard:hover {{ background: {c['surface2']}; }}"
            f"#siteCard[pressed=\"true\"] {{ background: {c['border']}; }}"
            f"#siteName {{ background: transparent; color: {c['text']};"
            f" font-size: {T.FONT['card_title']}px; font-weight: 700; }}"
            f"#siteUrl {{ background: transparent; color: {c['accent']};"
            f" font-size: {T.FONT['body']}px; font-weight: 600; }}"
            f"#siteDesc {{ background: transparent; color: {c['text_secondary']};"
            f" font-size: {T.FONT['small']}px; }}"
            f"#siteArrow {{ background: {c['surface']}; color: {c['text']};"
            f" border: 1px solid {c['border']};"
            f" border-radius: {T.s(23)}px; font-size: {T.s(22)}px; font-weight: 600; }}")
        self._place_wm()

    def mousePressEvent(self, e):
        _set_pressed(self, True)
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        _set_pressed(self, False)
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.item)


class SitesScreen(QWidget):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self.theme_name = "light"
        self.sites = []
        self.cards = []
        self._cols = 0
        self._loader = None
        self._modal = None
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(T.SPACE["page"], 0, T.SPACE["page"], T.SPACE["page"])
        root.setSpacing(T.SPACE["gap"])

        self.status = StatusLabel(self.theme_name)
        root.addWidget(self.status)
        self.empty = EmptyState(icon="globe", theme=self.theme_name)
        root.addWidget(self.empty)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.grid_host = QWidget()
        self.grid_host.setObjectName("gridHost")
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, T.s(8), 0, T.s(40))
        self.grid.setHorizontalSpacing(T.s(28))
        self.grid.setVerticalSpacing(T.s(28))
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.grid_host)
        root.addWidget(self.scroll, 1)

    def on_show(self):
        if not self.sites:
            self.reload()

    def reload(self):
        self.empty.hide()
        self.status.loading(tr("common.loading"))
        self._loader = track(_Loader(self.api))
        self._loader.done.connect(self._on_loaded)
        self._loader.fail.connect(
            lambda: self.status.text(tr("common.load_failed")))
        self._loader.start()

    def _on_loaded(self, sites):
        self.sites = sites
        self._render()

    def _render(self):
        while self.grid.count():
            w = self.grid.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.cards = []
        if not self.sites:
            self.status.clear()
            self.empty.set_message(tr("sites.empty"))
            self.empty.show()
            return
        self.status.clear()
        self.empty.hide()
        cols = self._calc_cols()
        self._cols = cols
        for i, s in enumerate(self.sites):
            card = SiteCard(s, self.theme_name)
            card.clicked.connect(self._open_detail)
            self.cards.append(card)
            self.grid.addWidget(card, i // cols, i % cols)
        # Faol ustunlar teng cho'ziladi; ortiqcha "fantom" ustunlarni nollaymiz.
        for cidx in range(16):
            self.grid.setColumnStretch(cidx, 1 if cidx < cols else 0)
        # Layout o'rnashgach qayta tekshiramiz (birinchi ochilishda viewport
        # kengligi hali yakuniy emas — kartalar kichik/siqilgan chiqadi).
        QTimer.singleShot(0, self._recheck_cols)

    def _recheck_cols(self):
        if self.sites and self.isVisible() and self._calc_cols() != self._cols:
            self._render()

    def showEvent(self, e):
        super().showEvent(e)
        QTimer.singleShot(0, self._recheck_cols)

    # Ekran kengligiga qarab ustunlar soni (dizayn: 3 ustun; kichik ekranda ham >=2).
    def _calc_cols(self):
        avail = self.scroll.viewport().width()
        if avail <= 0:
            avail = self.width() - 2 * T.SPACE["page"]
        spacing = self.grid.horizontalSpacing()
        target = T.s(360)
        cols = (avail + spacing) // (target + spacing)
        return max(2, int(cols))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.sites and self._calc_cols() != getattr(self, "_cols", 0):
            self._render()

    def _open_detail(self, item):
        self._modal = _SiteDetail(self.window(), item)
        self._modal.show_over(self.theme_name)

    def apply_theme(self, name):
        self.theme_name = name
        c = T.THEMES[name]
        # Sahifa foni (satin) ko'rinsin — scroll/host shaffof
        self.scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            + T.scrollbar_qss(c))
        self.scroll.viewport().setStyleSheet("background: transparent;")
        self.grid_host.setStyleSheet("#gridHost { background: transparent; }")
        self.status.apply_theme(name)
        self.empty.apply_theme(name)
        for card in self.cards:
            card.apply_theme(name)


class _SiteDetail(Modal):
    """Sayt detali va QR kod (TZ 8.13) — tik (vertikal) tartib:
    ← Ortga, sarlavha karta (ikonka+nom+havola), tavsif, imkoniyatlar ro'yxati
    va pastda chegarali 'Telefoningizda oching' qutisi (QR + 3 qadam)."""

    PANEL_W = 640

    def __init__(self, parent, item):
        self._pw = T.s(self.PANEL_W)
        super().__init__(parent, width=self._pw, height=T.s(640))
        self.item = item
        self._icon = _ICONS[_icon_key(item)]

        # Kenglik qat'iy, balandlik tarkibga moslashadi (panel sizeHint'ga teng)
        self.panel.setFixedWidth(self._pw)
        self.panel.setMinimumHeight(0)
        self.panel.setMaximumHeight(16777215)
        self.layout().setAlignment(self.panel, Qt.AlignmentFlag.AlignCenter)

        # Bazaviy X tugmani yashiramiz — o'rniga "← Ortga" pill
        self.close_btn.hide()
        while self.body.count():
            self.body.takeAt(0)
        self.body.setContentsMargins(T.s(26), T.s(24), T.s(26), T.s(28))
        self.body.setSpacing(0)

        # ← Ortga
        backrow = QHBoxLayout()
        self.back = QPushButton(tr("common.back"))
        self.back.setObjectName("sdBack")
        self.back.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back.clicked.connect(self.close_modal)
        backrow.addWidget(self.back)
        backrow.addStretch(1)
        self.body.addLayout(backrow)
        self.body.addSpacing(T.s(20))

        # Sarlavha karta: ikonka plitka + nom + havola
        self.header = QFrame()
        self.header.setObjectName("sdHeader")
        hl = QHBoxLayout(self.header)
        hl.setContentsMargins(T.s(18), T.s(16), T.s(18), T.s(16))
        hl.setSpacing(T.s(16))
        self.tile = _icon_tile(self._icon, T.THEMES["light"]["accent"],
                               T.THEMES["light"]["surface"], size=54, icon_px=30)
        namecol = QVBoxLayout()
        namecol.setSpacing(T.s(4))
        self.name = QLabel(item.get("name", ""))
        self.name.setObjectName("sdName")
        self.url = QLabel(item.get("url", ""))
        self.url.setObjectName("sdUrl")
        namecol.addWidget(self.name)
        namecol.addWidget(self.url)
        hl.addWidget(self.tile, 0, Qt.AlignmentFlag.AlignVCenter)
        hl.addLayout(namecol, 1)
        self.body.addWidget(self.header)
        self.body.addSpacing(T.s(20))

        # Tavsif
        self.desc = QLabel(item.get("description") or "")
        self.desc.setObjectName("sdDesc")
        self.desc.setWordWrap(True)
        self.body.addWidget(self.desc)

        # Imkoniyatlar ro'yxati (• ...)
        self._feat_lbls = []
        feats = _features(item)
        if feats:
            self.body.addSpacing(T.s(14))
            for f in feats:
                lbl = QLabel(f"•   {f}")
                lbl.setObjectName("sdFeat")
                lbl.setWordWrap(True)
                self._feat_lbls.append(lbl)
                self.body.addWidget(lbl)
                self.body.addSpacing(T.s(8))

        self.body.addSpacing(T.s(12))

        # 'Telefoningizda oching' qutisi: QR (chap) + 3 qadam (o'ng)
        self.qrbox = QFrame()
        self.qrbox.setObjectName("sdQrBox")
        ql = QHBoxLayout(self.qrbox)
        ql.setContentsMargins(T.s(18), T.s(18), T.s(20), T.s(18))
        ql.setSpacing(T.s(20))
        self.qr = QRWidget(T.s(150))
        self.qr.set_url(item.get("url", ""))
        ql.addWidget(self.qr, 0, Qt.AlignmentFlag.AlignVCenter)

        steps = QVBoxLayout()
        steps.setSpacing(T.s(10))
        self.qr_title = QLabel(tr("sites.qr_title"))
        self.qr_title.setObjectName("sdQrTitle")
        steps.addWidget(self.qr_title)
        steps.addSpacing(T.s(4))
        self._step_nums = []
        step_texts = [tr("sites.step1"), tr("sites.step2"), tr("sites.step3")]
        for i, txt in enumerate(step_texts, 1):
            srow = QHBoxLayout()
            srow.setSpacing(T.s(12))
            num = QLabel(str(i))
            num.setObjectName("sdStepNum")
            num.setFixedSize(T.s(30), T.s(30))
            num.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._step_nums.append(num)
            stxt = QLabel(txt)
            stxt.setObjectName("sdStepTxt")
            stxt.setWordWrap(True)
            srow.addWidget(num, 0, Qt.AlignmentFlag.AlignTop)
            srow.addWidget(stxt, 1)
            steps.addLayout(srow)
        steps.addStretch(1)
        ql.addLayout(steps, 1)
        self.body.addWidget(self.qrbox)

    def show_over(self, name="light"):
        super().show_over(name)
        c = T.THEMES[name]
        accent_soft = c["surface2"]
        # Ikonka plitkalar
        self.tile.setPixmap(_svg_pixmap(self._icon, c["accent"], T.s(30)))
        self.tile.setStyleSheet(
            f"#siteTile {{ background: {c['surface']}; border-radius: {T.s(15)}px; }}")
        self.panel.setStyleSheet(
            f"#modalPanel {{ background: {c['surface']};"
            f" border-radius: {T.RADIUS['card']}px; }}"
            f"#sdBack {{ background: {accent_soft}; color: {c['accent']}; border: none;"
            f" border-radius: {T.RADIUS['pill']}px; padding: {T.s(10)}px {T.s(24)}px;"
            f" font-size: {T.FONT['nav']}px; font-weight: 700; }}"
            f"#sdBack:hover {{ background: {c['border']}; }}"
            f"#sdBack:pressed {{ background: {c['border']}; color: {c['text']}; }}"
            f"#sdHeader {{ background: {accent_soft}; border-radius: {T.s(18)}px; }}"
            f"#sdName {{ background: transparent; color: {c['text']};"
            f" font-size: {T.s(26)}px; font-weight: 700; }}"
            f"#sdUrl {{ background: transparent; color: {c['accent']};"
            f" font-size: {T.FONT['body']}px; font-weight: 600; }}"
            f"#sdDesc {{ background: transparent; color: {c['text_secondary']};"
            f" font-size: {T.s(19)}px; line-height: 150%; }}"
            f"#sdFeat {{ background: transparent; color: {c['text']};"
            f" font-size: {T.s(19)}px; }}"
            f"#sdQrBox {{ background: {accent_soft};"
            f" border: 1px solid {c['border']}; border-radius: {T.s(18)}px; }}"
            f"#sdQrTitle {{ background: transparent; color: {c['text']};"
            f" font-size: {T.s(22)}px; font-weight: 700; }}"
            f"#sdStepNum {{ background: {c['surface']}; color: {c['accent']};"
            f" border-radius: {T.s(15)}px; font-size: {T.s(16)}px; font-weight: 700; }}"
            f"#sdStepTxt {{ background: transparent; color: {c['text_secondary']};"
            f" font-size: {T.s(18)}px; }}")
