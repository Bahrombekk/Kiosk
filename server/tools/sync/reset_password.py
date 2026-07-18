#!/usr/bin/env python3
"""
reset_password.py — Nishon serverdagi admin parolni MASOFADAN tiklaydi.

Mavjud receiver.ps1 protokolidan foydalanadi (yangi kod kerak emas):
  stop -> get_db -> admin_password_hash'ni o'chirish -> put db -> start

Natijada nishon server keyingi ochilishda "Yangi admin parol yarating"
oynasini chiqaradi. Kontent/kiosklar/litsenziya tegilmaydi.

Foydalanish (nishonда Ishga-tushirish.bat ochiq turgan holda):
  py -3 reset_password.py --host 192.168.136.114 --port 8799 --token <token>
"""
import argparse
import os
import sqlite3
import sys
import tempfile

import sender  # protokol funksiyalari (cmd, cmd_get_db, cmd_put) — import
                # hech narsa parse qilmaydi (argparse sender.main() ichida)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True)
    ap.add_argument("--port", type=int, default=8799)
    ap.add_argument("--token", required=True)
    ap.add_argument("--no-restart", action="store_true")
    cfg = ap.parse_args()

    print(f"Nishon: {cfg.host}:{cfg.port}")
    hi = sender.cmd(cfg, {"cmd": "hello"})
    print(f"Nishon papka: {hi.get('base')} (baza: {'bor' if hi.get('has_db') else 'yoq'})")
    if not hi.get("has_db"):
        print("Nishonда baza yo'q — tiklash uchun narsa yo'q.")
        return

    print("Server to'xtatilmoqda...")
    sender.cmd(cfg, {"cmd": "stop"})

    tmp = tempfile.mkdtemp(prefix="kiosk_reset_")
    dbp = os.path.join(tmp, "target.db")
    print("Baza olinmoqda...")
    sender.cmd_get_db(cfg, dbp)

    c = sqlite3.connect(dbp, timeout=10)
    before = c.execute(
        "select count(*) from settings where key='admin_password_hash'"
    ).fetchone()[0]
    c.execute("delete from settings where key='admin_password_hash'")
    try:
        c.execute("insert into audit_log(action,details) "
                  "values('admin_password_reset','masofadan tiklandi')")
    except Exception:
        pass
    c.commit()
    c.close()
    print(f"admin_password_hash o'chirildi (avval mavjud edi: {bool(before)}).")

    print("Baza qaytarilmoqda...")
    sender.cmd_put(cfg, "data.db", dbp, label="data.db")

    if not cfg.no_restart:
        print("Server qayta ishga tushirilmoqda...")
        sender.cmd(cfg, {"cmd": "start"})

    print("\nTAYYOR. Nishon server ochilganda YANGI parol so'raydi.")


if __name__ == "__main__":
    main()
