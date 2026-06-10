"""ui/login.py — Admin parol darvozasi (kirish dialogi)."""
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QCheckBox, QDialog,
    QDialogButtonBox
)
from PyQt6.QtCore import Qt

import db
from icons import svg_pixmap
from ui.styles import C_ACCENT, C_MUTED, C_OK, C_BAD


class LoginDialog(QDialog):
    """Admin oynasi ochilishidan oldin parol so'raydi.

    Birinchi ishga tushishda (parol hali o'rnatilmagan) — yangi parol
    yaratish rejimi. 5 marta noto'g'ri kiritilsa dastur yopiladi."""

    MAX_ATTEMPTS = 5

    def __init__(self):
        super().__init__()
        self._attempts = 0
        self._create_mode = not db.get_settings().get("admin_password_hash")
        self.setWindowTitle("Kiosk Server — Kirish")
        self.setModal(True)
        self.setFixedWidth(420)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(12)

        # Brend sarlavha: accent plitka + nom + izoh
        brand_row = QHBoxLayout()
        brand_row.setSpacing(12)
        tile = QLabel()
        tile.setFixedSize(44, 44)
        tile.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tile.setStyleSheet(
            f"background: {C_ACCENT}; border-radius: 12px;")
        tile.setPixmap(svg_pixmap("monitor", "#FFFFFF", 24))
        brand_col = QVBoxLayout()
        brand_col.setSpacing(0)
        brand = QLabel("Kiosk Server")
        brand.setStyleSheet("font-size: 16px; font-weight: 800;")
        brand_sub = QLabel("Boshqaruv paneli")
        brand_sub.setStyleSheet(f"color: {C_MUTED}; font-size: 12px;")
        brand_col.addWidget(brand)
        brand_col.addWidget(brand_sub)
        brand_row.addWidget(tile)
        brand_row.addLayout(brand_col)
        brand_row.addStretch(1)
        lay.addLayout(brand_row)
        lay.addSpacing(8)

        title = QLabel("Yangi admin parol yarating"
                       if self._create_mode else "Admin parolini kiriting")
        title.setStyleSheet("font-size: 17px; font-weight: 800;")
        lay.addWidget(title)

        if self._create_mode:
            sub = QLabel("Birinchi ishga tushirish: server boshqaruvi uchun "
                         "parol o'rnating (kamida 8 belgi).")
            sub.setWordWrap(True)
            sub.setStyleSheet(f"color: {C_MUTED};")
            lay.addWidget(sub)

        self.pw1 = QLineEdit()
        self.pw1.setEchoMode(QLineEdit.EchoMode.Password)
        self.pw1.setPlaceholderText("Parol")
        self.pw1.setMinimumHeight(38)
        lay.addWidget(self.pw1)

        self.pw2 = QLineEdit()
        self.pw2.setEchoMode(QLineEdit.EchoMode.Password)
        self.pw2.setPlaceholderText("Parolni takrorlang")
        self.pw2.setMinimumHeight(38)
        self.pw2.setVisible(self._create_mode)
        lay.addWidget(self.pw2)

        # Parolni ko'rsatish (nima yozganini ko'rish uchun)
        self.show_pw = QCheckBox("Parolni ko'rsatish")
        self.show_pw.toggled.connect(self._toggle_echo)
        lay.addWidget(self.show_pw)

        self.err = QLabel(" ")
        self.err.setStyleSheet(f"color: {C_BAD}; font-weight: 600;")
        lay.addWidget(self.err)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._submit)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)
        self.ok_btn = btns.button(QDialogButtonBox.StandardButton.Ok)
        self.pw1.returnPressed.connect(self._submit)
        self.pw2.returnPressed.connect(self._submit)

        # Yangi parol rejimida — jonli tekshiruv (belgilar soni, moslik)
        if self._create_mode:
            self.pw1.textChanged.connect(self._update_live)
            self.pw2.textChanged.connect(self._update_live)
            self._update_live()

    def _toggle_echo(self, show):
        mode = (QLineEdit.EchoMode.Normal if show
                else QLineEdit.EchoMode.Password)
        self.pw1.setEchoMode(mode)
        self.pw2.setEchoMode(mode)

    def _update_live(self):
        """Yangi parol rejimida jonli holat: uzunlik va moslik; OK tugmasi."""
        pw, pw2 = self.pw1.text(), self.pw2.text()
        long_ok = len(pw) >= 8
        match_ok = bool(pw) and pw == pw2
        if not long_ok:
            self.err.setText(f"Parol uzunligi: {len(pw)}/8 belgi")
            self.err.setStyleSheet(f"color: {C_MUTED}; font-weight: 600;")
        elif not match_ok:
            self.err.setText("Ikkala maydonga bir xil parol kiriting.")
            self.err.setStyleSheet(f"color: {C_MUTED}; font-weight: 600;")
        else:
            self.err.setText("✓ Parol tayyor — OK bosing.")
            self.err.setStyleSheet(f"color: {C_OK}; font-weight: 600;")
        if hasattr(self, "ok_btn") and self.ok_btn:
            self.ok_btn.setEnabled(long_ok and match_ok)

    def _submit(self):
        pw = self.pw1.text()
        if self._create_mode:
            if len(pw) < 8:
                self.err.setText("Parol kamida 8 belgi bo'lsin.")
                self.err.setStyleSheet(f"color: {C_BAD}; font-weight: 600;")
                return
            if pw != self.pw2.text():
                self.err.setText("Parollar mos kelmadi.")
                self.err.setStyleSheet(f"color: {C_BAD}; font-weight: 600;")
                return
            db.set_setting("admin_password_hash", db.hash_secret(pw))
            db.log_action("admin_password_created")
            self.accept()
            return
        stored = db.get_settings().get("admin_password_hash", "")
        if db.verify_secret(pw, stored):
            db.log_action("admin_login_ok")
            self.accept()
            return
        self._attempts += 1
        db.log_action("admin_login_fail", f"attempt={self._attempts}")
        left = self.MAX_ATTEMPTS - self._attempts
        if left <= 0:
            self.reject()
            return
        self.err.setText(f"Parol noto'g'ri ({left} urinish qoldi).")
        self.pw1.clear()
