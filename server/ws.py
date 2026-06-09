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
    def __init__(self):
        # websocket -> {"device_id", "ip", "platform", "connected_at"}
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
        for info in self.active.values():
            out.append({
                "device_id": info.get("device_id") or "—",
                "ip": info.get("ip") or "—",
                "platform": info.get("platform") or "—",
                "connected_at": info.get("connected_at"),
                "uptime": int(now - info.get("connected_at", now)),
            })
        out.sort(key=lambda c: c["connected_at"] or 0, reverse=True)
        return out

    async def broadcast(self, message: dict):
        dead = []
        for ws in list(self.active):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    def broadcast_threadsafe(self, message: dict):
        """Admin oqimidan (Qt) chaqiriladi — broadcast'ni server loop'iga qo'yadi."""
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast(message), self.loop)


# Yagona umumiy manager (main.py va admin.py shundan foydalanadi)
manager = ConnectionManager()
