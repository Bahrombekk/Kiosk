"""
discovery.py — Imzolangan UDP broadcast "beacon" (kiosklar serverni topadi).

Har DISCOVERY_INTERVAL_S soniyada LAN broadcast manzilga
(255.255.255.255:DISCOVERY_PORT) kichik JSON beacon yuboriladi. Beacon
Ed25519 maxfiy kalit bilan IMZOLANADI — kiosk faqat serverning ochiq kalitiga
mos imzoni qabul qiladi. Demak:
  * soxta kompyuter "men serverman" deb beacon yuborolmaydi (imzo yo'q),
  * sirlar (API kalit) HECH QACHON beacon ichida yuborilmaydi — faqat ulanish
    ma'lumoti va sertifikat fingerprint'i (kiosk pin bilan solishtiradi).

Beacon ichida `ts` (vaqt) va `nonce` bor — kiosk eski beacon'ni qayta
yuborishni (replay) rad etadi.

Beacon har bir LAN IP uchun alohida yuboriladi (kiosk to'g'ri url'ni olsin).
"""
import json
import time
import socket
import logging
import threading
import secrets

import config
import security

log = logging.getLogger("kiosk.discovery")

_thread = None
_stop = threading.Event()


def _scheme():
    return "https" if config.USE_TLS else "http"


def _make_beacon(ip, fingerprint):
    """Bitta IP uchun imzolangan beacon baytlarini (wire) qaytaradi.

    payload qat'iy (sort_keys, ixcham) JSON sifatida imzolanadi — kiosk aynan
    shu baytlarni tekshiradi. Wire: {"p": <payload-json>, "s": <imzo b64>}."""
    import base64
    payload = {
        "v": 1,
        "name": config.SERVER_NAME,
        "url": f"{_scheme()}://{ip}:{config.PORT}",
        "port": config.PORT,
        "fp": fingerprint,
        "ts": int(time.time()),
        "nonce": secrets.token_hex(8),
    }
    payload_str = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    sig = security.sign(payload_str.encode("utf-8"))
    wire = json.dumps({"p": payload_str,
                       "s": base64.b64encode(sig).decode("ascii")})
    return wire.encode("utf-8")


def _local_ipv4s():
    """LAN IP'lari (security bilan bir xil; beacon url'iga yoziladi)."""
    return security._local_ipv4s() or ["127.0.0.1"]


def _run():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    fingerprint = security.cert_fingerprint() if config.USE_TLS else ""
    log.info("Discovery beacon ishga tushdi (port %d, %s)",
             config.DISCOVERY_PORT, _scheme())
    try:
        while not _stop.is_set():
            try:
                for ip in _local_ipv4s():
                    data = _make_beacon(ip, fingerprint)
                    sock.sendto(data, ("255.255.255.255", config.DISCOVERY_PORT))
            except OSError as e:
                log.warning("Beacon yuborilmadi: %s", e)
            # Uyquni mayda bo'laklarga bo'lamiz — stop() darhol ta'sir qilsin.
            _stop.wait(config.DISCOVERY_INTERVAL_S)
    finally:
        sock.close()
        log.info("Discovery beacon to'xtadi")


def start():
    """Beacon oqimini ishga tushiradi (DISCOVERY_ENABLED bo'lsa)."""
    global _thread
    if not config.DISCOVERY_ENABLED:
        log.info("Discovery o'chirilgan (KIOSK_DISCOVERY=0)")
        return
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_run, name="discovery", daemon=True)
    _thread.start()


def stop():
    """Beacon oqimini to'xtatadi."""
    _stop.set()
