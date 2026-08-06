"""
set_password.py — Bulut admin parolini almashtiradi.

Nega alohida skript: parol bazada faqat pbkdf2 XESH ko'rinishida turadi, ya'ni
uni "o'qib olish" imkoni yo'q — esdan chiqsa shu skript bilan yangisi qo'yiladi.
`CLOUD_ADMIN_PASS` env bilan ham bo'ladi, lekin u bulut IShGA TUSHGANDA
qo'llanadi; bu skript esa ishlab turgan bulutda ham darhol ishlaydi (parol har
kirishda bazadan tekshiriladi).

Ishlatish (cloud/ ichida):
    py tools/set_password.py                     # `admin` parolini so'raydi
    py tools/set_password.py kiosk123            # to'g'ridan-to'g'ri beradi
    py tools/set_password.py kiosk123 operator1  # boshqa foydalanuvchi
                                                 # (yo'q bo'lsa yaratiladi)

Boshqa bazani ko'rsatish: CLOUD_DB=/yo'l/cloud.db py tools/set_password.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config      # noqa: E402
import db          # noqa: E402

MIN_LEN = 4


def main():
    plain = sys.argv[1] if len(sys.argv) > 1 else ""
    user = sys.argv[2] if len(sys.argv) > 2 else None
    if not plain:
        try:
            import getpass
            plain = getpass.getpass("Yangi admin parol: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBekor qilindi.")
            return 1
    if len(plain) < MIN_LEN:
        print(f"Parol juda qisqa (kamida {MIN_LEN} belgi).")
        return 1

    db.init_db()
    db.migrate_legacy_password()
    user = (user or db.DEFAULT_USER).strip()
    db.upsert_user(user, plain)
    if user == db.DEFAULT_USER:
        # Eski kalitni ham yangilab qo'yamiz (moslik uchun)
        db.set_setting("admin_pass_hash", db.hash_secret(plain))
    # Tekshirib ko'ramiz — parol haqiqatan ishlashi kerak
    ok = bool(db.get_user(user)
              and db.verify_secret(plain, db.get_user(user)["pass_hash"]))
    print(f"Baza:  {config.DB_PATH}")
    print(f"Login: {user}")
    print(f"Parol: {plain}")
    # DIQQAT: bu yerda faqat ASCII — Windows konsoli cp1251/cp866 bo'lishi
    # mumkin va "✓" kabi belgilar UnicodeEncodeError beradi.
    print("Holat: " + ("almashtirildi (OK)" if ok else "XATO - yozilmadi"))
    if ok:
        print("\nEslatma: bulutni qayta ishga tushirish SHART EMAS - parol har "
              "kirishda bazadan tekshiriladi.\nLekin ishga tushirishda "
              "CLOUD_ADMIN_PASS env berilgan bo'lsa, u har startda parolni "
              "o'ziga qaytaradi — env'ni olib tashlang yoki yangisini yozing.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
