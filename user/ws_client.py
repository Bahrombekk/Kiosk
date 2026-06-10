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
import platform

import websockets
from PyQt6.QtCore import QThread, pyqtSignal

import config

log = logging.getLogger(__name__)


class WSClient(QThread):
    status = pyqtSignal(dict)         # status_update keldi
    announcement = pyqtSignal(str)    # announcement keldi
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
                        ping_interval=20, ping_timeout=20) as wsconn:
                    self.link.emit(True)
                    await wsconn.send(json.dumps(
                        {"type": "register", "device_id": self.device_id,
                         "platform": self.platform}))
                    async for raw in wsconn:
                        if self._stop:
                            return
                        self._handle(raw)
            except Exception as e:
                log.warning("WS uzildi (%s), qayta urinamiz", e)
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

    def stop(self):
        self._stop = True
