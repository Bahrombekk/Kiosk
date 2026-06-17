"""
ws_client.py — Serverdan real vaqt xabarlarni tinglovchi (TZ 8 / 11.2).

Alohida oqimda (QThread) WebSocket'ga ulanadi va xabarlarni Qt signallari
orqali UI'ga uzatadi. Ulanish uzilsa avtomatik qayta ulanadi (TZ 12.2 — har
5 soniyada). Asyncio ichki oqimda ishlaydi, UI'ni bloklamaydi.
"""
import asyncio
import json
import logging
import socket
import ssl
import platform

import websockets
from PyQt6.QtCore import QThread, pyqtSignal

from core import config
from core import trust

log = logging.getLogger(__name__)


def _ssl_context():
    """WSS uchun pinned SSL context (yoki ws:// bo'lsa None).

    Server sertifikati trust.json'dagi cert_pem bilan CA sifatida tekshiriladi
    (self-signed = o'ziga o'zi CA). Hostname tekshiruvi o'chiq — IP bilan
    ulanamiz, ishonch sertifikatga pin orqali."""
    if not config.is_tls():
        return None
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    pem = trust.cert_pem()
    if pem:
        try:
            ctx.load_verify_locations(cadata=pem)
            return ctx
        except ssl.SSLError:
            log.warning("trust.json cert_pem o'qilmadi", exc_info=True)
    # Pin materiali yo'q — oxirgi chora (xavfsizroq emas; trust.json bo'lishi shart)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


class WSClient(QThread):
    status = pyqtSignal(dict)         # status_update keldi
    announcement = pyqtSignal(str)    # announcement keldi
    sync = pyqtSignal(dict)           # katalog/sozlama yangilandi
    cache_clear = pyqtSignal()        # admin: lokal keshni tozalash buyrug'i
    cache_sync = pyqtSignal()         # admin: media keshni darhol sinxlash buyrug'i
    link = pyqtSignal(bool)           # ulanish bor/yo'q

    def __init__(self, url=None):
        super().__init__()
        self.url = url or config.WS_URL
        self.device_id = socket.gethostname()
        self.platform = f"{platform.system()} {platform.release()}".strip()
        self._stop = False

    def run(self):
        try:
            asyncio.run(self._loop())
        except Exception:
            log.exception("WS oqimi kutilmagan xato bilan tugadi")

    async def _loop(self):
        while not self._stop:
            try:
                # open_timeout: ulanish osilib qolsa (DNS/yarim ochiq) 10s da
                # uzilib qayta urinadi. ping_*: o'lik ulanishni faol aniqlaydi.
                async with websockets.connect(
                        self.url, open_timeout=10,
                        ping_interval=20, ping_timeout=20,
                        ssl=_ssl_context()) as wsconn:
                    self.link.emit(True)
                    if getattr(self, "_down_logged", False):
                        log.info("WS qayta ulandi")
                        self._down_logged = False
                    await wsconn.send(json.dumps(
                        {"type": "register", "device_id": self.device_id,
                         "platform": self.platform}))
                    async for raw in wsconn:
                        if self._stop:
                            return
                        self._handle(raw)
            except Exception as e:
                # Faqat birinchi uzilishda warning — server o'chiq turganda
                # har 5 soniyada takror yozib log'ni to'ldirmaymiz
                if not getattr(self, "_down_logged", False):
                    log.warning("WS uzildi (%s), qayta urinamiz", e)
                    self._down_logged = True
                else:
                    log.debug("WS qayta urinish (%s)", e)
                # Ulanish uzildi — biroz kutib qayta urinamiz (TZ 12.2).
                # Uyquni mayda bo'laklarga bo'lamiz: stop() darhol ta'sir qilsin
                # (aks holda ilova yopilganda thread 5s ishlab turib, Qt'ni
                #  "Destroyed while thread is still running" bilan to'xtatadi).
                self.link.emit(False)
                slept = 0.0
                while slept < config.RECONNECT_INTERVAL_MS / 1000:
                    if self._stop:
                        return
                    await asyncio.sleep(0.1)
                    slept += 0.1

    def _handle(self, raw):
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            return
        mtype = data.get("type")
        if mtype == "status_update":
            self.status.emit(data)
        elif mtype == "announcement":
            self.announcement.emit(data.get("text", ""))
        elif mtype in ("catalog_update", "settings_update", "reload"):
            self.sync.emit(data)
        elif mtype == "cache_clear":
            self.cache_clear.emit()
        elif mtype == "cache_sync":
            self.cache_sync.emit()

    def stop(self):
        self._stop = True
