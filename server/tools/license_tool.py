#!/usr/bin/env python3
"""
license_tool.py — VENDOR litsenziya vositasi (FAQAT SIZNING kompyuteringizda).

MUHIM: `tools/license/vendor_private.pem` — imzo kaliti. U MIJOZGA, o'rnatilgan
serverga yoki git'ga HECH QACHON bermang/qo'ymang. Kalit yo'qolsa yangi
litsenziya bera olmaysiz (server exe'laridagi ochiq kalit unga bog'langan) —
XAVFSIZ JOYGA ZAXIRA NUSXA saqlang.

Buyruqlar:
  keygen                      — yangi kalit juftligi (bor bo'lsa rad etadi)
  hwid                        — shu kompyuterning hardware ID'si
  issue --hw <id> [...]       — litsenziya berish -> license.key
  inspect <fayl>              — litsenziyani tekshirish/ko'rish

Litsenziya berish oqimi:
  1. Mijoz serverida admin oyna: Sozlamalar -> Litsenziya -> "Qurilma ID"ni
     nusxalab sizga yuboradi (yoki o'sha mashinada `license_tool.py hwid`).
  2. Sizda: py -3 license_tool.py issue --hw <id> --customer "Afrosiyob 50x" \
        --days 365 --kiosks 50 -o license.key
     (muddatsiz uchun --days o'rniga --forever)
  3. `license.key` faylini mijoz serverida KioskServer.exe yoniga qo'yasiz
     yoki admin oyna: Sozlamalar -> Litsenziya -> "Litsenziya yuklash".
"""
import argparse
import base64
import json
import os
import sys
from datetime import date, timedelta

TOOL_DIR = os.path.dirname(os.path.abspath(__file__))
KEY_DIR = os.path.join(TOOL_DIR, "license")
PRIV_PATH = os.path.join(KEY_DIR, "vendor_private.pem")

# licensing.py (server ildizida) — format/ochiq kalit bilan bo'lishamiz
sys.path.insert(0, os.path.dirname(TOOL_DIR))
import licensing  # noqa: E402


def _b64e(b):
    return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")


def _load_private():
    from cryptography.hazmat.primitives import serialization
    if not os.path.isfile(PRIV_PATH):
        sys.exit(f"XATO: maxfiy kalit topilmadi: {PRIV_PATH}\n"
                 "Avval `license_tool.py keygen` bajaring.")
    with open(PRIV_PATH, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)


def cmd_keygen(_args):
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.hazmat.primitives import serialization
    if os.path.isfile(PRIV_PATH):
        sys.exit("XATO: kalit allaqachon bor — ustidan yozilmaydi "
                 "(yangi kalit eski litsenziyalarni bekor qiladi).")
    os.makedirs(KEY_DIR, exist_ok=True)
    key = ed25519.Ed25519PrivateKey.generate()
    with open(PRIV_PATH, "wb") as f:
        f.write(key.private_bytes(serialization.Encoding.PEM,
                                  serialization.PrivateFormat.PKCS8,
                                  serialization.NoEncryption()))
    pub = key.public_key().public_bytes(serialization.Encoding.Raw,
                                        serialization.PublicFormat.Raw)
    print("Maxfiy kalit:", PRIV_PATH)
    print("OCHIQ kalit (licensing.py VENDOR_PUBLIC_KEY_B64 ga qo'ying):")
    print(" ", base64.b64encode(pub).decode())
    print("\nDIQQAT: maxfiy kalitni zaxiralang va hech kimga bermang!")


def cmd_hwid(_args):
    print(licensing.hardware_id())


def cmd_issue(args):
    if not args.forever and not args.days and not args.expires:
        sys.exit("Muddat kerak: --days N, --expires YYYY-MM-DD yoki --forever")
    expires = None
    if not args.forever:
        expires = (args.expires or
                   (date.today() + timedelta(days=args.days)).isoformat())
    payload = {
        "v": 1,
        "hw": args.hw.strip().lower(),
        "customer": args.customer or "",
        "issued": date.today().isoformat(),
        "expires": expires,
        "max_kiosks": max(0, args.kiosks),
    }
    payload_bytes = json.dumps(payload, separators=(",", ":"),
                               ensure_ascii=False).encode("utf-8")
    sig = _load_private().sign(payload_bytes)
    token = _b64e(payload_bytes) + "." + _b64e(sig)
    with open(args.out, "w", encoding="ascii") as f:
        f.write(token + "\n")
    print(f"Litsenziya yozildi: {args.out}")
    print(f"  mijoz      : {payload['customer'] or '-'}")
    print(f"  qurilma    : {payload['hw']}")
    print(f"  muddat     : {expires or 'MUDDATSIZ'}")
    print(f"  kiosk soni : {payload['max_kiosks'] or 'cheksiz'}")


def cmd_inspect(args):
    with open(args.file, "r", encoding="ascii") as f:
        raw = f.read()
    payload, err = licensing._verify(raw)
    if payload is None:
        sys.exit(f"YAROQSIZ: {err}")
    print("Imzo: TO'G'RI (vendor ochiq kaliti bilan tasdiqlandi)")
    for k in ("customer", "hw", "issued", "expires", "max_kiosks"):
        print(f"  {k:11}: {payload.get(k)}")
    local_hw = licensing.hardware_id()
    print(f"  shu mashina: {local_hw} "
          f"({'MOS' if local_hw == payload.get('hw') else 'MOS EMAS'})")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("keygen")
    sub.add_parser("hwid")
    p = sub.add_parser("issue")
    p.add_argument("--hw", required=True, help="Mijoz serverining qurilma ID'si")
    p.add_argument("--customer", default="", help="Mijoz nomi (ma'lumot uchun)")
    p.add_argument("--days", type=int, default=0, help="Bugundan necha kun")
    p.add_argument("--expires", default=None, help="Aniq sana YYYY-MM-DD")
    p.add_argument("--forever", action="store_true", help="Muddatsiz")
    p.add_argument("--kiosks", type=int, default=0,
                   help="Maksimal kiosk soni (0 = cheksiz)")
    p.add_argument("-o", "--out", default="license.key")
    p = sub.add_parser("inspect")
    p.add_argument("file")
    args = ap.parse_args()
    {"keygen": cmd_keygen, "hwid": cmd_hwid,
     "issue": cmd_issue, "inspect": cmd_inspect}[args.cmd](args)


if __name__ == "__main__":
    main()
