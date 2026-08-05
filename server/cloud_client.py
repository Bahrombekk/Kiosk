"""
cloud_client.py — Markaziy bulut AGENTI (poyezd serveri tomoni).

Nima uchun kerak: poyezdda oq IP yo'q va SIM-internet uzilib turadi. Shuning
uchun bulut poyezdga ulanmaydi — **server o'zi** bulutga doimiy WebSocket
ochadi (`wss://cloud/agent`) va buyruqlar shu kanal orqali qaytadi.

Ishlash tartibi:
  1. **Enroll** — birinchi ishga tushishda bir martalik `KIOSK_CLOUD_ENROLL`
     tokeni doimiy `server_token` + bulutning ochiq kalitiga almashtiriladi
     (bazada `settings`da saqlanadi, ikkinchi marta enroll qilinmaydi).
  2. **Ulanish** — WS ochiladi, `register` yuboriladi, 30 soniyada `heartbeat`.
     Uzilса eksponensial kutish bilan qayta ulanadi (5s → 60s).
  3. **Buyruqlar** — har biri Ed25519 bilan imzolangan; imzo bulutning ochiq
     kaliti bilan TEKSHIRILADI, aks holda tashlanadi. Ya'ni kanalga tushgan
     begona "o'chir" buyrug'i ishlamaydi.
  4. **Manifest (desired state)** — bulut "shu serverда shu kontent bo'lishi
     kerak" deb to'liq ro'yxat yuboradi. Agent solishtiradi: yo'qini Range
     bilan yuklab oladi (uzilса to'xtagan joyidan davom etadi, sha256 bilan
     tekshiradi), ro'yxatda yo'q BULUT kontentini o'chiradi. Qo'lда qo'shilgan
     kontentga (origin='local') tegmaydi.
  5. **Statistika/loglar** — kiosklardan yig'ilgani va server loglari davriy
     batch bilan yuboriladi. Navbat = bazaning o'zi (`cloud_stats_last_id`),
     shuning uchun oflaynда hech narsa yo'qolmaydi.
"""
from __future__ import annotations

import asyncio
import base64
import collections
import hashlib
import json
import logging
import os
import shutil
import time
import urllib.error
import urllib.request

import config
import db
import licensing
import ws as wsmod

log = logging.getLogger("kiosk.cloud")

# --- sozlamalar (settings jadvalidagi kalitlar) ---
K_ID = "cloud_server_id"
K_TOKEN = "cloud_token"
K_PUBKEY = "cloud_pubkey"
K_REV = "cloud_applied_rev"
K_STATS = "cloud_stats_last_id"

RECONNECT_MIN_S = 5
RECONNECT_MAX_S = 60
PROGRESS_EVERY_S = 2
DL_CHUNK = 512 * 1024
DL_TIMEOUT_S = 60
# Statistika: bitta xabarda nechta event va bitta aylanishда jami nechta
# (birinchi ulanishda oylab yig'ilgan tarix ham shu tezlikda o'tadi).
STATS_BATCH = 1000
STATS_MAX_PER_CYCLE = 5000

# Bulutdan MASOFADAN o'zgartirilishi mumkin bo'lgan sozlamalar (OQ RO'YXAT).
# Bu yerda yo'q kalitni bulut o'zgartira olmaydi — masalan `api_key`,
# `admin_pass_hash`, `cloud_token`, litsenziya/trial kalitlari ATAYLAB yo'q:
# ular xavfsizlik chegarasi va ularni faqat joyidagi admin boshqaradi.
REMOTE_SETTINGS = {
    # Poyezd / vagon ma'lumotlari
    "wagon_number", "wagon_note", "train_name", "route", "depart_time",
    "kiosk_location", "active_route_direction",
    # Ko'rsatkichlar
    "weather_auto", "temperature", "speed_auto", "speed",
    # Reklama
    "ad_interval_min", "ad_algorithm", "media_ad_slots",
    # Kesh
    "media_cache", "cache_limit_gb",
    # SOS va ko'rinish
    "sos_enabled", "sos_numbers", "default_theme",
    # Sinov muddati / bloklash — bu VENDOR boshqaruvi (bulut sizning
    # nazoratingizda). Litsenziya FAYLI esa alohida `set_license` buyrug'i
    # bilan keladi va imzosi tekshiriladi.
    "trial_enabled", "trial_start", "trial_days", "trial_blocked",
    # Veb ilova
    "web_enabled",
    # Wi-Fi (qiymat yoziladi; qo'llanishi uchun server qayta ishga tushadi)
    "wifi_hotspot", "wifi_ssid", "wifi_password",
}

# Serverning o'z loglari (bulut "Loglar" ekranida ko'rinadi). Ring bufer —
# oflaynда to'lib ketmaydi, eng oxirgilari saqlanadi.
_log_queue: collections.deque = collections.deque(maxlen=500)


class _CloudLogHandler(logging.Handler):
    """WARNING va yuqori darajali loglarni bulutga yuborish uchun yig'adi.
    INFO'lar yuborilmaydi — SIM-trafik behuda ketmasin."""

    def emit(self, record):
        try:
            if record.levelno < logging.WARNING:
                return
            _log_queue.append({
                "ts": time.strftime("%Y-%m-%d %H:%M:%S",
                                    time.localtime(record.created)),
                "level": "ERROR" if record.levelno >= logging.ERROR else "WARN",
                "source": record.name.replace("kiosk.", "")[:32],
                "msg": record.getMessage()[:1000],
            })
        except Exception:                                        # noqa: BLE001
            pass


def _fresh(ts, seconds):
    """`ts` ("YYYY-MM-DD HH:MM:SS") shu necha soniya ichidami."""
    if not ts:
        return False
    try:
        t = time.strptime(str(ts)[:19], "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return False
    return (time.time() - time.mktime(t)) <= seconds


def db_int(v, default=0):
    """Bulutdan kelgan qiymatni butun songa o'giradi (bo'sh/xato -> default)."""
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def cloud_log(msg, level="INFO", source="cloud"):
    """Bulut loglariga ataylab yozish (muhim hodisalar — INFO ham o'tadi)."""
    _log_queue.append({
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"), "level": level,
        "source": source, "msg": str(msg)[:1000],
    })


# =====================================================================
class CloudClient:
    def __init__(self):
        self.server_id = None
        self.token = None
        self.pubkey = None            # ed25519 ochiq kalit (bytes)
        self.connected = False
        # Bulut adminini tasdiqlaganmi (tokensiz ulanishda muhim)
        self.approved = True
        # Veb ilova boshqaruvchisi (admin.py `bind_web` bilan beradi). Backend
        # o'zi veb'ni ko'tarmaydi — u admin jarayonида turadi, shuning uchun
        # masofadan yoqish/o'chirish uchun havola kerak.
        self.web = None
        self.job_id = None            # hozir bajarilayotgan ish
        self.progress = {"pct": 0, "bytes": 0, "total": 0}
        self._task = None
        self._stop = asyncio.Event()

    # ------------------------------------------------------------ holat
    def _load_state(self):
        s = db.get_settings()
        self.server_id = s.get(K_ID)
        self.token = s.get(K_TOKEN)
        pk = s.get(K_PUBKEY)
        self.pubkey = base64.b64decode(pk) if pk else None

    @property
    def applied_rev(self):
        try:
            return int(db.get_settings().get(K_REV) or 0)
        except (TypeError, ValueError):
            return 0

    def bind_web(self, web):
        """Veb ilova boshqaruvchisini ulaydi (admin.py chaqiradi) — shundan
        keyin bulut veb'ni masofadan yoqib/o'chira oladi va holatini ko'radi."""
        self.web = web

    def status(self):
        """Admin oynasidagi "Bulut" kartasi uchun qisqa holat."""
        return {
            "enabled": bool(config.CLOUD_URL),
            "url": config.CLOUD_URL,
            "enrolled": bool(self.server_id and self.token),
            "server_id": self.server_id or "",
            "connected": self.connected,
            "approved": self.approved,
            "applied_rev": self.applied_rev,
        }

    # ----------------------------------------------------------- enroll
    def _enroll_sync(self):
        """Serverni bulutda ro'yxatga oladi va doimiy token oladi (bloklovchi —
        `asyncio.to_thread` bilan chaqiriladi).

        Token BERILMASA ham ishlaydi: bulut serverni "tasdiqlash kerak" holatida
        ro'yxatga oladi, admin panelda bir marta tasdiqlaydi. Ya'ni poyezd
        serveriga faqat bulut DOMENI yoziladi, boshqa hech narsa emas."""
        body = json.dumps({
            "enroll_token": config.CLOUD_ENROLL,      # bo'sh bo'lishi mumkin
            "hw_id": licensing.hardware_id(),
            "name": config.SERVER_NAME,
            "version": config.APP_VERSION,
        }).encode()
        req = urllib.request.Request(
            config.CLOUD_URL + "/api/enroll", data=body,
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())

    async def _ensure_enrolled(self):
        self._load_state()
        if self.server_id and self.token:
            return True
        try:
            r = await asyncio.to_thread(self._enroll_sync)
        except (urllib.error.URLError, OSError, ValueError) as e:
            log.warning("Bulut: enroll bo'lmadi (%s) — keyinroq urinamiz", e)
            return False
        if not r.get("server_id") or not r.get("server_token"):
            log.error("Bulut: enroll javobi kutilganidek emas")
            return False
        db.set_setting(K_ID, r["server_id"])
        db.set_setting(K_TOKEN, r["server_token"])
        if r.get("cloud_pubkey"):
            db.set_setting(K_PUBKEY, r["cloud_pubkey"])
        self._load_state()
        self.approved = bool(r.get("approved", True))
        log.info("Bulut: ro'yxatdan o'tdik — %s (tasdiqlangan=%s)",
                 self.server_id, self.approved)
        db.log_action("cloud_enrolled", self.server_id)
        if self.approved:
            cloud_log(f"Server bulutga ulandi: {self.server_id}")
        else:
            log.warning("Bulut: server ro'yxatga olindi, lekin TASDIQLASH "
                        "kutilmoqda — bulut panelidan tasdiqlang")
        return True

    # ------------------------------------------------------- asosiy sikl
    async def run(self):
        if not config.CLOUD_URL:
            log.info("Bulut: KIOSK_CLOUD_URL berilmagan — agent o'chiq")
            return
        logging.getLogger("kiosk").addHandler(_CloudLogHandler())
        delay = RECONNECT_MIN_S
        while not self._stop.is_set():
            if not await self._ensure_enrolled():
                await self._sleep(60)
                continue
            try:
                await self._session()
                delay = RECONNECT_MIN_S          # muvaffaqiyatli seans
            except asyncio.CancelledError:
                raise
            except Exception as e:                               # noqa: BLE001
                log.warning("Bulut: aloqa uzildi (%s) — %ss dan keyin qayta",
                            type(e).__name__, delay)
            finally:
                self.connected = False
            await self._sleep(delay)
            delay = min(delay * 2, RECONNECT_MAX_S)

    async def _sleep(self, s):
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=s)
        except asyncio.TimeoutError:
            pass

    def _ws_url(self):
        base = config.CLOUD_URL.replace("https://", "wss://").replace(
            "http://", "ws://")
        return (f"{base}/agent?server_id={self.server_id}"
                f"&token={self.token}")

    async def _session(self):
        import websockets                     # uvicorn[standard] bilan keladi
        async with websockets.connect(self._ws_url(), open_timeout=20,
                                      ping_interval=25, ping_timeout=20,
                                      max_size=8 * 1024 * 1024) as sock:
            self.connected = True
            log.info("Bulut: ulandi (%s)", config.CLOUD_URL)
            await self._send(sock, {"type": "register", **self._state_payload()})
            hb = asyncio.create_task(self._heartbeat_loop(sock))
            push = asyncio.create_task(self._push_loop(sock))
            try:
                async for raw in sock:
                    try:
                        msg = json.loads(raw)
                    except (json.JSONDecodeError, TypeError):
                        continue
                    if isinstance(msg, dict):
                        await self._on_message(sock, msg)
            finally:
                hb.cancel()
                push.cancel()

    async def _send(self, sock, msg):
        await sock.send(json.dumps(msg, ensure_ascii=False))

    # ------------------------------------------------------------- holat
    def _state_payload(self):
        kiosks = db.get_kiosks()
        online_ids = {c.get("device_id") for c in wsmod.manager.clients()}
        try:
            du = shutil.disk_usage(config.BASE_DIR)
            disk_total, disk_free = du.total, du.free
        except OSError:
            disk_total = disk_free = 0
        lic = licensing.state()
        if lic.get("blocked"):
            lstate = "blocked" if lic.get("present") else "expired"
        elif lic.get("days_left") is not None:
            lstate = "trial"
        else:
            lstate = "active"
        return {
            "version": config.APP_VERSION,
            "name": config.SERVER_NAME,
            "kiosks_total": len(kiosks),
            "kiosks_online": len(online_ids),
            "disk_total": disk_total, "disk_free": disk_free,
            "license": lstate,
            "license_note": (f"{lic['days_left']} kun qoldi"
                             if lic.get("days_left") is not None else ""),
            # To'liq litsenziya holati — bulut panelda ko'rsatadi va yangi
            # license.key yasash uchun Qurilma ID (hw) shu yerдan olinadi.
            "license_info": {
                "hw_id": lic.get("hw_id"),
                "present": lic.get("present"), "valid": lic.get("valid"),
                "reason": lic.get("reason"), "customer": lic.get("customer"),
                "issued": lic.get("issued"), "expires": lic.get("expires"),
                "days_left": lic.get("days_left"),
                "max_kiosks": lic.get("max_kiosks"),
                "blocked": lic.get("blocked"),
            },
            "applied_rev": self.applied_rev,
            "queue_active": 1 if self.job_id else 0,
            "queue_pending": 0,
            # Bulutga hali yuborilmagan statistika (panelда ko'rinadi —
            # "hammasi tortib olindimi" degan savolga javob)
            "stats_pending": db.stats_pending_count(self._stats_pointer()),
            "stats_total": db.stats_count(),
            # Veb ilova (poyezd.uz) hozir ishlayaptimi
            "web_running": bool(self.web and self.web.is_running()),
            # Masofadan boshqariladigan sozlamalarning JORIY qiymatlari —
            # panel shu qiymatlarni forma sifatida ko'rsatadi
            "settings": {k: v for k, v in db.get_settings().items()
                         if k in REMOTE_SETTINGS},
            "kiosks": [{
                "device_id": k.get("device_id"),
                "kiosk_no": k.get("kiosk_no"), "room": k.get("room"),
                "ip": k.get("ip"), "platform": k.get("platform"),
                "cached_n": k.get("cached_n"),
                "disk_total": k.get("disk_total"), "disk_free": k.get("disk_free"),
                # Lokal kesh yoqilganmi — busiz bulutда holat ko'rinmasdi va
                # o'chirilgan keshni QAYTA YOQIB bo'lmasdi.
                "cache_enabled": 1 if k.get("cache_enabled", 1) else 0,
                # Onlayn: WS ulanishi BOR yoki oxirgi heartbeat 30 soniya
                # ichida (kiosk 5 soniyada yuboradi — qisqa uzilishда
                # "offlayn" deb ko'rsatmaymiz).
                "online": (k.get("device_id") in online_ids
                           or _fresh(k.get("last_seen"), 30)),
                "last_seen": k.get("last_seen"),
            } for k in kiosks],
        }

    async def _heartbeat_loop(self, sock):
        while True:
            await asyncio.sleep(config.CLOUD_HEARTBEAT_S)
            await self._send(sock, {"type": "heartbeat", **self._state_payload()})

    async def _push_loop(self, sock):
        """Statistika va loglarni davriy yuboradi. Loglar tez-tez (15s), chunki
        ular kichkina; statistika esa CLOUD_STATS_S da bir marta — SIM-trafikni
        tejash uchun batch bo'lib ketadi.

        MUHIM: agar orqada ko'p tarix qolgan bo'lsa (birinchi ulanish yoki uzoq
        oflayn), keyingi yuborish 5 soniyadan keyin bo'ladi — ya'ni navbat tez
        drenaj bo'ladi, keyin oddiy ritmga qaytadi."""
        next_stats = 0.0                     # birinchi aylanishда darhol
        while True:
            await asyncio.sleep(5)
            # TASDIQLANMAGUNCHA hech narsa yubormaymiz: bulut tasdiqlanmagan
            # serverdan kelgan statistikani QABUL QILMAYDI, agar shunda ham
            # yuborsak ko'rsatkich (cloud_stats_last_id) surilib, o'sha eventlar
            # butunlay yo'qolib ketardi.
            if not self.approved:
                continue
            await self._push_logs(sock)
            if time.monotonic() < next_stats:
                continue
            backlog = await self._push_stats(sock)
            next_stats = time.monotonic() + (5 if backlog else config.CLOUD_STATS_S)

    def _stats_pointer(self):
        try:
            return int(db.get_settings().get(K_STATS) or 0)
        except (TypeError, ValueError):
            return 0

    async def _push_stats(self, sock):
        """Yuborilmagan eventlarni batch bilan uzatadi.

        Bir aylanishда ko'pi bilan STATS_MAX_PER_CYCLE yozuv ketadi — kanal
        band bo'lib qolmasin va heartbeat kechikmasin. Orqada yana qolsa True
        qaytaradi (chaqiruvchi tezroq qayta chaqiradi)."""
        last = self._stats_pointer()
        sent = 0
        while sent < STATS_MAX_PER_CYCLE:
            rows = db.stats_since_id(last, STATS_BATCH)
            if not rows:
                return False
            events = [{
                "device_id": r["device_id"], "session": r["session"],
                "ts": r["ts"], "event": r["event"], "source": r["source"],
                "data": (json.loads(r["data"]) if r["data"] else None),
            } for r in rows]
            await self._send(sock, {"type": "stats", "events": events})
            last = rows[-1]["id"]
            db.set_setting(K_STATS, str(last))
            sent += len(rows)
            if len(rows) < STATS_BATCH:
                return False                 # navbat tugadi
            await asyncio.sleep(0.15)        # kanalni bo'g'masin
        left = db.stats_pending_count(last)
        if sent:
            log.info("Bulut: %d event yuborildi, navbatda %d qoldi", sent, left)
        return left > 0

    async def _push_logs(self, sock):
        if not _log_queue:
            return
        batch = [_log_queue.popleft() for _ in range(min(len(_log_queue), 100))]
        await self._send(sock, {"type": "logs", "entries": batch})

    # ---------------------------------------------------------- buyruqlar
    def _verify(self, payload, sig_b64):
        """Ed25519 imzosini tekshiradi. To'g'ri bo'lsa buyruq dict, aks holda None."""
        if not self.pubkey:
            log.warning("Bulut: ochiq kalit yo'q — buyruq tashlandi")
            return None
        try:
            from cryptography.exceptions import InvalidSignature
            from cryptography.hazmat.primitives.asymmetric import ed25519
            key = ed25519.Ed25519PublicKey.from_public_bytes(self.pubkey)
            try:
                key.verify(base64.b64decode(sig_b64), payload.encode("utf-8"))
            except InvalidSignature:
                log.warning("Bulut: IMZO YAROQSIZ — buyruq tashlandi")
                return None
            cmd = json.loads(payload)
        except (ValueError, TypeError, json.JSONDecodeError) as e:
            log.warning("Bulut: buyruqni o'qib bo'lmadi (%s)", e)
            return None
        if not isinstance(cmd, dict):
            return None
        if cmd.get("server_id") and cmd["server_id"] != self.server_id:
            log.warning("Bulut: buyruq BOSHQA serverga tegishli — tashlandi")
            return None
        return cmd

    async def _on_message(self, sock, msg):
        kind = msg.get("type")
        if kind == "cmd":
            cmd = self._verify(msg.get("payload") or "", msg.get("sig") or "")
            if cmd:
                await self._run_cmd(sock, cmd)
        elif kind in ("hello", "hb_ack"):
            # Tasdiqlash holati o'zgarganini kuzatamiz (admin panelda bosilganda)
            was = self.approved
            self.approved = bool(msg.get("approved", True))
            if not was and self.approved:
                log.info("Bulut: server TASDIQLANDI — sinxronizatsiya boshlanadi")
                cloud_log("Server bulutda tasdiqlandi")
        elif kind in ("stats_ack", "logs_ack", "settings_ack", "web_ack",
                      "kiosk_ack", "license_ack"):
            pass                                  # xabar tasdiqlari — e'tibor yo'q
        else:
            log.debug("Bulut: noma'lum xabar %s", kind)

    async def _run_cmd(self, sock, cmd):
        kind = cmd.get("type")
        if kind == "manifest":
            await self._apply_manifest(sock, cmd)
        elif kind == "announce":
            text = str(cmd.get("text") or "")[:300]
            if text:
                await wsmod.manager.broadcast({"type": "announcement", "text": text})
                db.log_action("cloud_announcement", text)
                cloud_log(f"E'lon tarqatildi: {text}")
        elif kind == "cache_clear":
            await wsmod.manager.broadcast({"type": "cache_clear"})
            db.log_action("cloud_cache_clear", "")
            cloud_log("Kiosklarga kesh tozalash buyrug'i yuborildi")
        elif kind == "set_settings":
            await self._apply_settings(sock, cmd.get("values"))
        elif kind == "web":
            await self._web_cmd(sock, str(cmd.get("action") or ""))
        elif kind == "kiosk":
            await self._kiosk_cmd(sock, cmd)
        elif kind == "set_license":
            await self._set_license(sock, cmd.get("text"))
        elif kind == "reboot":
            # Ataylab bajarilmaydi: masofadan qayta ishga tushirish poyezdda
            # kioskni ishlamay qoldirish xavfini tug'diradi. Faqat qayd etamiz.
            cloud_log("Qayta ishga tushirish so'raldi — qo'lда bajarilishi kerak",
                      "WARN")
        else:
            log.warning("Bulut: qo'llab-quvvatlanmaydigan buyruq: %s", kind)

    # ------------------------------------------------- masofaviy boshqaruv
    async def _apply_settings(self, sock, values):
        """Bulutdan kelgan sozlamalarni yozadi (faqat OQ RO'YXATдagi kalitlar)."""
        if not isinstance(values, dict):
            return
        written, skipped = [], []
        for k, v in values.items():
            if k not in REMOTE_SETTINGS:
                skipped.append(k)
                continue
            db.set_setting(k, "" if v is None else str(v)[:2000])
            written.append(k)
        if skipped:
            log.warning("Bulut: ruxsat etilmagan sozlama(lar) tashlandi: %s",
                        ", ".join(skipped))
        if not written:
            return
        db.log_action("cloud_settings", ", ".join(written))
        cloud_log(f"Sozlamalar bulutdan yangilandi: {', '.join(written)}")

        # Veb ilovani darhol qo'llaymiz (qolgan sozlamalar keyingi so'rovдa
        # o'zi kuchga kiradi — kiosklar /api/settings dan o'qiydi).
        if "web_enabled" in written and self.web:
            want = str(values.get("web_enabled") or "1") != "0"
            await asyncio.to_thread(self.web.start if want else self.web.stop)
        # Kiosklarga "katalog/sozlama o'zgardi" signali
        await wsmod.manager.broadcast({"type": "catalog_update"})
        await self._send(sock, {"type": "settings_ack", "keys": written})

    async def _web_cmd(self, sock, action):
        """Veb ilovani masofadan yoqish/o'chirish."""
        if not self.web:
            cloud_log("Veb boshqaruvi mavjud emas (server admin oynasiz "
                      "ishlayapti)", "WARN")
            return
        if action == "start":
            db.set_setting("web_enabled", "1")
            await asyncio.to_thread(self.web.start)
        elif action == "stop":
            db.set_setting("web_enabled", "0")
            await asyncio.to_thread(self.web.stop)
        else:
            return
        db.log_action("cloud_web", action)
        cloud_log(f"Veb ilova bulutdan {'yoqildi' if action == 'start' else 'ochirildi'}")
        await self._send(sock, {"type": "web_ack", "action": action,
                                "running": self.web.is_running()})

    async def _set_license(self, sock, text):
        """Bulutdan kelgan `license.key` mazmunini o'rnatadi.

        Fayl VENDOR imzosi bilan tekshiriladi (`licensing.install_file`) —
        ya'ni bulut o'zboshimchalik bilan litsenziya "yasab" bermaydi; imzosi
        yaroqsiz fayl mavjud YAROQLI litsenziyani almashtirmaydi."""
        text = str(text or "").strip()
        if not text:
            return
        tmp = os.path.join(config.BASE_DIR, "license.incoming")
        try:
            with open(tmp, "w", encoding="ascii", errors="ignore") as f:
                f.write(text + "\n")
            st = await asyncio.to_thread(licensing.install_file, tmp)
            ok = bool(st.get("valid"))
            msg = ("Litsenziya o'rnatildi: "
                   + (f"{st.get('customer') or '-'}, muddat "
                      f"{st.get('expires') or 'cheksiz'}, kiosk limiti "
                      f"{st.get('max_kiosks') or 'cheksiz'}" if ok
                      else f"YAROQSIZ — {st.get('reason')}"))
            log.info("Bulut: %s", msg)
            cloud_log(msg, "INFO" if ok else "ERROR")
            db.log_action("cloud_license", msg[:200])
            await self._send(sock, {"type": "license_ack", "valid": ok,
                                    "reason": st.get("reason")})
        except Exception as e:                                   # noqa: BLE001
            log.warning("Bulut: litsenziya o'rnatilmadi (%s)", e)
            cloud_log(f"Litsenziya o'rnatilmadi: {e}", "ERROR")
            await self._send(sock, {"type": "license_ack", "valid": False,
                                    "reason": str(e)[:200]})
        finally:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except OSError:
                pass

    async def _kiosk_cmd(self, sock, cmd):
        """Bitta kioskка tegishli buyruq (bulut paneldagi kiosk qatoridan)."""
        dev = str(cmd.get("device_id") or "").strip()
        action = str(cmd.get("action") or "")
        if not dev:
            return
        if action == "sync":
            await wsmod.manager._send_to_device(dev, {"type": "cache_sync"})
        elif action == "cache_clear":
            await wsmod.manager._send_to_device(dev, {"type": "cache_clear"})
        elif action in ("cache_on", "cache_off"):
            db.set_kiosk_cache_enabled(dev, action == "cache_on")
            # Kiosk keyingi heartbeatда javobдan o'qiydi, lekin darhol ham
            # xabar beramiz — kesh yoqilsa yuklashni boshlaydi.
            if action == "cache_on":
                await wsmod.manager._send_to_device(dev, {"type": "cache_sync"})
            else:
                await wsmod.manager._send_to_device(dev, {"type": "cache_clear"})
        elif action == "forget":
            db.delete_kiosk(dev)
        else:
            log.warning("Bulut: noma'lum kiosk buyrug'i: %s", action)
            return
        db.log_action("cloud_kiosk_" + action, dev)
        cloud_log(f"Kiosk {dev}: {action} (bulutdan)")
        await self._send(sock, {"type": "kiosk_ack", "device_id": dev,
                                "action": action})

    # ------------------------------------------------------- desired state
    async def _apply_manifest(self, sock, cmd):
        """Bulut yuborgan to'liq ro'yxatni qo'llaydi (yuklash + o'chirish)."""
        rev = int(cmd.get("rev") or 0)
        items = cmd.get("items") or []
        self.job_id = cmd.get("job_id") if isinstance(cmd.get("job_id"), int) else None
        log.info("Bulut: manifest rev=%s, %d yozuv", rev, len(items))

        local = {r["cloud_id"]: r for r in db.get_cloud_content()}
        want = {i["cloud_id"]: i for i in items if isinstance(i.get("cloud_id"), int)}

        # 1) Ro'yxatda yo'q bulut kontenti — o'chiriladi (fayllari ham)
        removed = 0
        for cid, row in local.items():
            if cid not in want:
                db.delete_content(row["id"])
                removed += 1
        if removed:
            cloud_log(f"{removed} kontent o'chirildi (bulut ro'yxatida yo'q)")

        # 2) Yuklab olinishi kerak bo'lgan fayllarni rejalashtiramiz
        plan = []           # (item, part_name, part, dest_dir, db_field)
        for cid, it in want.items():
            cur = local.get(cid) or {}
            for part_name, dest, sha_col in (
                    ("media", config.MEDIA_DIR, "media_sha"),
                    ("cover", config.COVERS_DIR, "cover_sha"),
                    ("text", config.BOOKS_DIR, "text_sha")):
                p = it.get(part_name)
                if not p or not p.get("sha256"):
                    continue
                if cur.get(sha_col) == p["sha256"] and self._file_ok(cur, part_name, dest):
                    continue          # allaqachon bor va sha mos — trafik tejaldi
                plan.append((cid, part_name, p, dest, sha_col))

        total = sum(int(p[2].get("size") or 0) for p in plan)
        self.progress = {"pct": 0 if total else 100, "bytes": 0, "total": total}
        if plan:
            log.info("Bulut: %d fayl yuklanadi (%.1f MB)", len(plan), total / 1e6)
            cloud_log(f"{len(plan)} fayl yuklanmoqda ({total / 1e6:.0f} MB)")

        reporter = asyncio.create_task(self._report_progress(sock))
        done_bytes = 0
        files = {}          # (cloud_id, part) -> saqlangan fayl nomi
        try:
            for cid, part_name, p, dest, sha_col in plan:
                try:
                    name = await asyncio.to_thread(
                        self._download, p, dest,
                        lambda got, base=done_bytes: self._tick(base + got, total))
                    files[(cid, part_name)] = name
                    done_bytes += int(p.get("size") or 0)
                    self._tick(done_bytes, total)
                except Exception as e:                           # noqa: BLE001
                    log.warning("Bulut: %s yuklanmadi (%s)", p.get("name"), e)
                    cloud_log(f"Yuklash xatosi: {p.get('name')} — {e}", "ERROR")
                    if self.job_id:
                        await self._send(sock, {
                            "type": "progress", "job_id": self.job_id,
                            "state": "error", "error": str(e)[:200],
                            "pct": self.progress["pct"],
                            "bytes": done_bytes, "total": total})
                        self.job_id = None
                    return
        finally:
            reporter.cancel()

        # 3) Bazaga yozamiz (yangi yoki yangilangan)
        for cid, it in want.items():
            cur = local.get(cid)
            row = self._row_from_item(it, files, cur)
            if cur:
                db.update_content(cur["id"], row)
                # Bulutda fayl almashtirilgan/olib tashlangan bo'lsa eski fayl
                # diskda yetim qolib ketmasin (boshqa yozuv ishlatmasa o'chadi).
                stale = {k: cur.get(k) for k in
                         ("file_path", "cover_path", "text_path")
                         if cur.get(k) and cur.get(k) != row.get(k)}
                if stale:
                    db.cleanup_files(stale)
            else:
                db.add_content(row)

        # 4) Reklama, saytlar va bekatlar (kontent bilan bir xil mantiq:
        #    faqat origin='cloud' yozuvlar boshqariladi, qo'lда qo'shilganlarga
        #    tegilmaydi)
        await self._apply_ads(cmd.get("ads"))
        await self._apply_branding(cmd.get("branding"))
        self._apply_simple("sites", cmd.get("sites"), (
            "name", "url", "description", "features", "icon", "sort_order"))
        self._apply_simple("route_stops", cmd.get("stops"), (
            "name", "arrival_time", "departure_time", "latitude", "longitude",
            "distance_km", "sort_order", "direction"))

        db.set_setting(K_REV, str(rev))
        await wsmod.manager.broadcast({"type": "catalog_update"})
        await self._send(sock, {"type": "applied", "rev": rev})
        if self.job_id:
            await self._send(sock, {"type": "progress", "job_id": self.job_id,
                                    "state": "done", "pct": 100,
                                    "bytes": total, "total": total})
        self.job_id = None
        log.info("Bulut: manifest qo'llanildi (rev=%s)", rev)
        cloud_log(f"Sinxronizatsiya tugadi — rev {rev}, {len(want)} kontent")

    # -------------------------------------- reklama / sayt / bekat qo'llash
    async def _apply_ads(self, ads):
        """Bulutdan kelgan reklama ro'yxatini qo'llaydi (media faylini ham
        tortadi). Ro'yxatда yo'q bulut reklamalari o'chiriladi."""
        if not isinstance(ads, list):
            return
        local = {r["cloud_id"]: r for r in db.cloud_rows("ads")}
        want = {a["cloud_id"]: a for a in ads
                if isinstance(a.get("cloud_id"), int)}
        removed = db.delete_cloud_rows("ads", want.keys())
        if removed:
            cloud_log(f"{removed} reklama o'chirildi (bulut ro'yxatida yo'q)")

        for cid, a in want.items():
            cur = local.get(cid) or {}
            row = {
                "cloud_id": cid, "origin": "cloud",
                "title": a.get("title"), "subtitle": a.get("subtitle"),
                "link_url": a.get("link_url"),
                "duration": db_int(a.get("duration"), 10),
                "interval_min": (db_int(a.get("interval_min"))
                                 if a.get("interval_min") else None),
                "start_time": a.get("start_time") or None,
                "end_time": a.get("end_time") or None,
                "placement": a.get("placement") or "popup",
                "is_active": 1 if a.get("is_active", 1) else 0,
                "sort_order": db_int(a.get("sort_order")),
            }
            p = a.get("media")
            if p and p.get("sha256"):
                same = (cur.get("media_sha") == p["sha256"]
                        and cur.get("media_path")
                        and os.path.isfile(os.path.join(config.ADS_DIR,
                                                        cur["media_path"])))
                if same:
                    row["media_path"] = cur["media_path"]
                    row["media_sha"] = cur["media_sha"]
                else:
                    try:
                        name = await asyncio.to_thread(
                            self._download, p, config.ADS_DIR, None)
                        row["media_path"] = name
                        row["media_sha"] = p["sha256"]
                    except Exception as e:                       # noqa: BLE001
                        log.warning("Bulut: reklama fayli yuklanmadi (%s)", e)
                        cloud_log(f"Reklama fayli yuklanmadi: {p.get('name')}",
                                  "ERROR")
                        continue
            if cur:
                db.update_ad(cur["id"], row)
            else:
                db.add_ad(row)

    async def _apply_branding(self, branding):
        """Bulutdan kelgan brending rasmlarini (hero banner) qo'llaydi.

        Fayl `content/branding/` ga tushadi va sozlamaga nomi yoziladi
        (`hero_image`). Veb ilova va kiosk shu sozlama bor bo'lsa serverdan
        oladi, aks holda ilovadagi standart rasmni ko'rsatadi."""
        if not isinstance(branding, dict):
            return
        for kind, key in (("hero", "hero_image"),):
            p = branding.get(kind)
            cur = db.get_settings().get(key) or ""
            if not p or not p.get("sha256"):
                if cur:                        # bulutда olib tashlangan
                    db.set_setting(key, "")
                    old = os.path.join(config.BRANDING_DIR, cur)
                    try:
                        if os.path.isfile(old):
                            os.remove(old)
                    except OSError:
                        pass
                    cloud_log(f"Brending olib tashlandi: {kind}")
                continue
            want = self._safe_name(p["sha256"], p.get("name"))
            if cur == want and os.path.isfile(
                    os.path.join(config.BRANDING_DIR, want)):
                continue                       # o'zgarmagan
            try:
                name = await asyncio.to_thread(
                    self._download, p, config.BRANDING_DIR, None)
            except Exception as e:                               # noqa: BLE001
                log.warning("Bulut: brending yuklanmadi (%s)", e)
                cloud_log(f"Brending yuklanmadi: {kind} — {e}", "ERROR")
                continue
            db.set_setting(key, name)
            # Eski faylni tozalaymiz (yangisi boshqa nomda)
            if cur and cur != name:
                try:
                    old = os.path.join(config.BRANDING_DIR, cur)
                    if os.path.isfile(old):
                        os.remove(old)
                except OSError:
                    pass
            cloud_log(f"Brending yangilandi: {kind} ({name})")

    @staticmethod
    def _apply_simple(table, rows, fields):
        """Fayli yo'q oddiy jadvallar (sites / route_stops) uchun umumiy
        qo'llash: bulut ro'yxatiga MOSLASH (yo'qini qo'shish, ortiqchasini
        o'chirish, borini yangilash)."""
        if not isinstance(rows, list):
            return
        add, upd, delete = {
            "sites": (db.add_site, db.update_site, None),
            "route_stops": (db.add_route_stop, db.update_route_stop, None),
        }[table]
        local = {r["cloud_id"]: r for r in db.cloud_rows(table)}
        want = {r["cloud_id"]: r for r in rows
                if isinstance(r.get("cloud_id"), int)}
        removed = db.delete_cloud_rows(table, want.keys())
        if removed:
            log.info("Bulut: %s dan %d yozuv o'chirildi", table, removed)
        for cid, r in want.items():
            row = {"cloud_id": cid, "origin": "cloud"}
            for f in fields:
                row[f] = r.get(f)
            cur = local.get(cid)
            if cur:
                upd(cur["id"], row)
            else:
                add(row)

    def _tick(self, got, total):
        self.progress = {
            "bytes": got, "total": total,
            "pct": int(100 * got / total) if total else 100,
        }

    async def _report_progress(self, sock):
        while True:
            await asyncio.sleep(PROGRESS_EVERY_S)
            if not self.job_id:
                continue
            await self._send(sock, {
                "type": "progress", "job_id": self.job_id, "state": "running",
                "pct": self.progress["pct"], "bytes": self.progress["bytes"],
                "total": self.progress["total"]})

    @staticmethod
    def _file_ok(row, part_name, dest):
        """Bazada yozilgan fayl haqiqatan diskda bormi (qo'lда o'chirilgan
        bo'lishi mumkin — u holda qayta yuklaymiz)."""
        col = {"media": "file_path", "cover": "cover_path", "text": "text_path"}[part_name]
        name = row.get(col)
        return bool(name) and os.path.isfile(os.path.join(dest, name))

    @staticmethod
    def _safe_name(sha, name):
        """Diskdagi fayl nomi: sha prefiksi + tozalangan asl nom.
        Prefiks — nomlar to'qnashmasligi va sha256 ko'rinib turishi uchun."""
        base = os.path.basename(name or "")
        keep = "".join(ch for ch in base if ch.isalnum() or ch in "._- ")
        keep = keep.strip().replace(" ", "_")[:80] or "fayl"
        return f"{sha[:10]}_{keep}"

    def _download(self, part, dest_dir, on_bytes):
        """Faylni Range bilan yuklaydi (uzilса davom etadi) va sha256'ni
        tekshiradi. Diskdagi nomni qaytaradi.

        Bloklovchi funksiya — `asyncio.to_thread` bilan chaqiriladi."""
        sha = part["sha256"]
        os.makedirs(dest_dir, exist_ok=True)
        final = os.path.join(dest_dir, self._safe_name(sha, part.get("name")))
        if os.path.isfile(final) and self._sha_of(final) == sha:
            return os.path.basename(final)          # allaqachon bor
        tmp = final + ".part"
        url = part["url"]
        if url.startswith("/"):
            url = config.CLOUD_URL + url            # nisbiy havola (relay.py)

        for attempt in range(4):
            have = os.path.getsize(tmp) if os.path.isfile(tmp) else 0
            req = urllib.request.Request(url)
            if have:
                req.add_header("Range", f"bytes={have}-")
            try:
                with urllib.request.urlopen(req, timeout=DL_TIMEOUT_S) as r:
                    # 200 kelsa server Range'ni inkor qildi — boshidan yozamiz
                    mode = "ab" if (have and r.status == 206) else "wb"
                    if mode == "wb":
                        have = 0
                    with open(tmp, mode) as f:
                        while True:
                            chunk = r.read(DL_CHUNK)
                            if not chunk:
                                break
                            f.write(chunk)
                            have += len(chunk)
                            if on_bytes:
                                on_bytes(have)
                break
            except (urllib.error.URLError, OSError) as e:
                if attempt == 3:
                    raise
                log.info("Bulut: yuklash uzildi (%s) — davom etamiz", e)
                time.sleep(2 * (attempt + 1))

        got = self._sha_of(tmp)
        if got != sha:
            os.remove(tmp)
            raise ValueError(f"sha256 mos kelmadi ({got[:12]} != {sha[:12]})")
        os.replace(tmp, final)
        return os.path.basename(final)

    @staticmethod
    def _sha_of(path):
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while True:
                b = f.read(1024 * 1024)
                if not b:
                    break
                h.update(b)
        return h.hexdigest()

    @staticmethod
    def _row_from_item(it, files, cur):
        """Manifest yozuvidan `content` jadvali qatorini yasaydi."""
        cid = it["cloud_id"]
        row = {
            "cloud_id": cid, "origin": "cloud",
            "type": it.get("type") or "movie",
            "title": it.get("title") or "Nomsiz",
            "author": it.get("author"), "genre": it.get("genre"),
            "description": it.get("description"),
            "duration": it.get("duration") or None,
            "pages": it.get("pages") or None,
            "lang": it.get("lang"),
            "category_tab": it.get("category_tab"),
            "is_recommended": 1 if it.get("is_recommended") else 0,
            "cache_enabled": 0 if it.get("cache_enabled") is False else 1,
            # visible=0 bo'lsa fayl serverда bo'ladi, lekin kiosklarga
            # berilmaydi (bulutda "Kiosklarda ko'rsatilsin" o'chirilgan)
            "visible": 0 if (it.get("visible") in (0, False)) else 1,
        }
        for part_name, path_col, sha_col in (
                ("media", "file_path", "media_sha"),
                ("cover", "cover_path", "cover_sha"),
                ("text", "text_path", "text_sha")):
            p = it.get(part_name)
            name = files.get((cid, part_name))
            if name:
                row[path_col] = name
                row[sha_col] = p["sha256"]
            elif cur and cur.get(sha_col) and p and cur[sha_col] == p["sha256"]:
                row[path_col] = cur.get(path_col)      # o'zgarmagan — saqlanadi
                row[sha_col] = cur[sha_col]
            elif not p:
                row[path_col] = None
                row[sha_col] = None
        return row


# =====================================================================
client = CloudClient()


def start():
    """Server lifespan'idan chaqiriladi (asyncio loop ichida)."""
    if not config.CLOUD_URL:
        log.info("Bulut: o'chiq (KIOSK_CLOUD_URL yo'q)")
        return None
    client._stop = asyncio.Event()
    client._task = asyncio.create_task(client.run())
    return client._task


async def stop():
    if client._task:
        client._stop.set()
        client._task.cancel()
        try:
            await client._task
        except (asyncio.CancelledError, Exception):              # noqa: BLE001
            pass
        client._task = None
