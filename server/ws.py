"""
ws.py — WebSocket ulanishlar boshqaruvchisi (TZ 11.2).

Server real vaqt xabarlarini barcha ulangan userlarga yuboradi:
  - status_update — tezlik/harorat/joriy bekat yangilandi
  - announcement  — barchaga e'lon

Har bir ulangan kiosk haqida ma'lumot saqlanadi (device_id, IP, tizim,
ulangan vaqt) — admin oynasidagi monitoring jadvali shundan foydalanadi.

Admin oynasi (boshqa oqimda) bilan ishlash uchun broadcast'ni server
event-loop'iga xavfsiz uzatadigan yordamchi bor (broadcast_threadsafe).
"""
import asyncio
import time


class ConnectionManager:
    # Bitta socketga yuborish maksimal kutish vaqti — "yarim o'lik" kiosk
    # (TCP buferi to'lgan) butun serverни osib qo'ymasin.
    SEND_TIMEOUT_S = 5

    def __init__(self):
        # websocket -> {"device_id", "ip", "platform", "connected_at", "lock"}
        self.active = {}
        self.loop = None     # server event-loop (admin oqimidan uzatish uchun)

    def set_loop(self, loop):
        self.loop = loop

    async def connect(self, ws):
        await ws.accept()
        ip = None
        try:
            ip = ws.client.host
        except Exception:
            ip = None
        self.active[ws] = {
            "device_id": None,
            "ip": ip,
            "platform": None,
            "connected_at": time.time(),
            # Har socketga ALOHIDA qulf: bir socketда ikki korutina bir vaqtda
            # yozsa Starlette "Concurrent call to send" beradi. Lekin har socket
            # mustaqil — bittasiga yuborish boshqasiniki bilan parallel ketadi.
            "lock": asyncio.Lock(),
        }

    def register(self, ws, device_id, platform=None):
        if ws in self.active:
            self.active[ws]["device_id"] = device_id
            if platform:
                self.active[ws]["platform"] = platform

    def disconnect(self, ws):
        self.active.pop(ws, None)

    def count(self):
        """Hozir ulangan kiosklar soni (admin monitoringi uchun)."""
        return len(self.active)

    def clients(self):
        """Ulangan kiosklar ro'yxati — har biri haqida ma'lumot (admin jadvali).

        Eng so'nggi ulangan kiosk ro'yxat boshida turadi.
        """
        now = time.time()
        out = []
        # Snapshot — admin oqimi o'qiyotganda server loop'i active'ni o'zgartirsa
        # "dictionary changed size during iteration" bo'lmasin.
        for info in list(self.active.values()):
            out.append({
                "device_id": info.get("device_id") or "—",
                "ip": info.get("ip") or "—",
                "platform": info.get("platform") or "—",
                "connected_at": info.get("connected_at"),
                "uptime": int(now - info.get("connected_at", now)),
            })
        out.sort(key=lambda c: c["connected_at"] or 0, reverse=True)
        return out

    async def _safe_send(self, ws, message: dict):
        """Bitta socketga uning ALOHIDA qulfi ostida, timeout bilan yuboradi.
        Muvaffaqiyatsiz bo'lsa (xato/timeout) socketni qaytaradi (o'lik deb
        belgilash uchun), aks holda None."""
        info = self.active.get(ws)
        if info is None:
            return None
        lock = info["lock"]
        try:
            async with lock:
                await asyncio.wait_for(ws.send_json(message),
                                       timeout=self.SEND_TIMEOUT_S)
        except Exception:
            return ws
        return None

    async def send_personal(self, ws, message: dict):
        """Bitta socketga yuboradi (o'sha socket qulfi ostida)."""
        await self._safe_send(ws, message)

    async def broadcast(self, message: dict):
        # Barcha socketlarga PARALLEL yuboramiz — bitta sekin/yarim o'lik kiosk
        # qolganlarini bloklamaydi (har biri o'z qulfi + timeoutida).
        targets = list(self.active)
        results = await asyncio.gather(
            *(self._safe_send(ws, message) for ws in targets),
            return_exceptions=True)
        for r in results:
            if isinstance(r, BaseException):
                continue
            if r is not None:        # _safe_send o'lik socketni qaytardi
                self.disconnect(r)

    def broadcast_threadsafe(self, message: dict):
        """Admin oqimidan (Qt) chaqiriladi — broadcast'ni server loop'iga qo'yadi."""
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast(message), self.loop)

    async def _send_to_device(self, device_id, message: dict):
        targets = [ws for ws, info in list(self.active.items())
                   if info.get("device_id") == device_id]
        results = await asyncio.gather(
            *(self._safe_send(ws, message) for ws in targets),
            return_exceptions=True)
        for r in results:
            if not isinstance(r, BaseException) and r is not None:
                self.disconnect(r)

    def send_to_device_threadsafe(self, device_id, message: dict):
        """Admin oqimidan — buyruqni faqat shu device_id'li kiosk(lar)ga yuboradi."""
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._send_to_device(device_id, message), self.loop)


# Yagona umumiy manager (main.py va admin.py shundan foydalanadi)
manager = ConnectionManager()
