"""
discovery.py — Serverni avtomatik topish (imzolangan UDP beacon'ni tutish).

Kiosk DISCOVERY_PORT'ni tinglaydi va serverdan kelgan beacon'larni
core/trust.py'dagi OCHIQ kalit bilan tekshiradi. Faqat imzosi to'g'ri, vaqti
yangi (replay emas) va sertifikat fingerprint'i provisioning qilingan pin
bilan MOS kelgan beacon qabul qilinadi.

Ishlatilishi (main.py'da, QApplication yaratilgach, MainWindow'dan oldin):
    from services import discovery
    discovery.resolve_server()

Agar server.txt/trust.json/KIOSK_SERVER orqali manzil allaqachon berilgan
bo'lsa (config.SERVER_CONFIGURED), discovery o'tkazib yuboriladi.
"""
import json
import time
import base64
import socket
import logging

from core import config
from core import trust

log = logging.getLogger(__name__)

# Beacon vaqti shu soniyadan eski/kelajak bo'lsa — rad etiladi (replay himoyasi
# + soat farqiga bardosh). Server har 3s yuborgani uchun yangi beacon doim keladi.
_MAX_SKEW_S = 30

# Tinglash davomiyligi — bir necha beacon davriga yetadi (server har 3s yuboradi).
_LISTEN_S = 4.0


def listen(timeout_s=_LISTEN_S):
    """`timeout_s` davomida beacon'larni tinglaydi va tekshirilgan serverlar
    ro'yxatini qaytaradi: [{name, url, port, fp}] (url bo'yicha takrorsiz).

    trust.json (ochiq kalit) bo'lmasa — bo'sh ro'yxat (imzosiz hech narsaga
    ishonmaymiz)."""
    if not trust.has_trust():
        log.warning("trust.json yo'q — discovery xavfsiz tekshira olmaydi")
        return []
    pin = trust.cert_fingerprint()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("", config.DISCOVERY_PORT))
    except OSError as e:
        log.warning("Discovery portini tinglab bo'lmadi (%s): %s",
                    config.DISCOVERY_PORT, e)
        sock.close()
        return []

    found = {}   # url -> candidate
    deadline = time.monotonic() + timeout_s
    try:
        while time.monotonic() < deadline:
            sock.settimeout(max(0.1, deadline - time.monotonic()))
            try:
                data, _addr = sock.recvfrom(4096)
            except socket.timeout:
                break
            except OSError:
                break
            cand = _parse_and_verify(data, pin)
            if cand:
                found[cand["url"]] = cand
    finally:
        sock.close()
    out = sorted(found.values(), key=lambda c: c.get("name") or c["url"])
    log.info("Discovery: %d ta server topildi", len(out))
    return out


def _parse_and_verify(data, pin):
    """Bitta beacon datagrammasini tekshiradi. To'g'ri bo'lsa candidate dict,
    aks holda None."""
    try:
        wire = json.loads(data.decode("utf-8"))
        payload_str = wire["p"]
        sig = base64.b64decode(wire["s"])
    except (ValueError, KeyError, TypeError):
        return None
    # 1) Imzo (eng muhim) — soxta server payloadni imzolay olmaydi.
    if not trust.verify_beacon(payload_str.encode("utf-8"), sig):
        return None
    try:
        p = json.loads(payload_str)
    except ValueError:
        return None
    # 2) Replay: vaqt yangi bo'lsin.
    try:
        if abs(time.time() - int(p["ts"])) > _MAX_SKEW_S:
            return None
    except (KeyError, ValueError, TypeError):
        return None
    # 3) Sertifikat pin: beacon e'lon qilgan fp provisioning pin bilan mos
    # kelsin (qo'shimcha qatlam — imzo allaqachon kafolatlaydi).
    if pin and (p.get("fp") or "").lower() != pin:
        log.warning("Beacon fingerprint pin bilan mos kelmadi — rad etildi")
        return None
    url = (p.get("url") or "").strip()
    if not url:
        return None
    return {"name": p.get("name") or url, "url": url,
            "port": p.get("port"), "fp": p.get("fp")}


def _apply(candidate):
    """Tanlangan serverni config'ga o'rnatadi (api_key trust.json'dan)."""
    config.set_server(candidate["url"], api_key=trust.api_key() or config.API_KEY)
    log.info("Server tanlandi: %s (%s)", candidate.get("name"), candidate["url"])


def _choose(candidates, parent=None):
    """Bir nechta server topilganda foydalanuvchidan tanlashni so'raydi.
    Qt bo'lmasa yoki bekor qilinsa — birinchisini qaytaradi."""
    try:
        from PyQt6.QtWidgets import QInputDialog
        from core.i18n import tr
    except Exception:
        return candidates[0]
    items = [f"{c['name']}  —  {c['url']}" for c in candidates]
    title = tr("conn.choose_title") if _has_key("conn.choose_title") else "Server tanlang"
    label = (tr("conn.choose_label") if _has_key("conn.choose_label")
             else "Bir nechta server topildi. Qaysi biriga ulanamiz?")
    choice, ok = QInputDialog.getItem(parent, title, label, items,
                                      0, False)
    if ok and choice in items:
        return candidates[items.index(choice)]
    return candidates[0]


def _has_key(key):
    """i18n'da kalit bormi (bo'lmasa zaxira matn ishlatamiz)."""
    try:
        from core import i18n
        return key in getattr(i18n, "_STRINGS", {}).get(i18n.get_lang(), {})
    except Exception:
        return False


def resolve_server(parent=None, timeout_s=_LISTEN_S):
    """Server manzilini aniqlaydi va config'ga o'rnatadi.

    - Manzil qo'lda berilgan bo'lsa (SERVER_CONFIGURED) — hech narsa qilmaydi.
    - Aks holda beacon'larni tinglaydi: 1 ta topilsa o'rnatadi, bir nechta
      bo'lsa tanlatadi, hech biri bo'lmasa False (chaqiruvchi keyin qayta
      urinishi yoki standart manzilda qolishi mumkin).

    True — server o'rnatildi (yoki allaqachon konfiguratsiyalangan)."""
    if config.SERVER_CONFIGURED:
        return True
    candidates = listen(timeout_s)
    if not candidates:
        return False
    chosen = candidates[0] if len(candidates) == 1 else _choose(candidates, parent)
    _apply(chosen)
    return True
