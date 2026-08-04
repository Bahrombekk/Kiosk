"""
relay.py — Agent (poyezd serveri) ulanishlarini boshqaradi.

Poyezdda oq IP yo'q, shuning uchun **server o'zi** bulutga doimiy WebSocket
ochadi (`/agent`). Buyruqlar shu ochiq kanal orqali qaytadi — bulut poyezdga
hech qachon o'zi ulanmaydi.

Bu modul faqat "kim ulangan va unga nima yuborilsin"ni biladi; kelgan
xabarlarni `main.py` o'qiydi va shu yerdagi funksiyalarni chaqiradi.

Buyruq — HAR SAFAR Ed25519 bilan imzolanadi (security.sign_command), agent
ochiq kalit bilan tekshiradi. Fayl havolalari NISBIY (`/dl/<token>`): agent
ularni o'zi ulangan bulut manziliga nisbatan yechadi — bulutda tashqi manzilni
sozlash shart emas (reverse-proxy ortida ham to'g'ri ishlaydi).
"""
import asyncio
import logging

import db
import security
import storage

log = logging.getLogger("cloud.relay")

SEND_TIMEOUT_S = 10


class Relay:
    def __init__(self):
        # server_id -> {"ws":…, "lock":…, "since":…}
        self.active = {}

    # --------------------------------------------------------- ro'yxatga olish
    async def attach(self, server_id, ws):
        """Yangi ulanish. Eski (yetim) ulanish bo'lsa u yopiladi — bitta server
        ikki marta ulanib qolса buyruq qaysi biriga ketishi noaniq bo'lmasin."""
        old = self.active.get(server_id)
        if old:
            try:
                await old["ws"].close(code=1000)
            except Exception:                                    # noqa: BLE001
                pass
        self.active[server_id] = {"ws": ws, "lock": asyncio.Lock()}
        log.info("Agent ulandi: %s (jami %d)", server_id, len(self.active))

    def detach(self, server_id, ws=None):
        cur = self.active.get(server_id)
        if cur and (ws is None or cur["ws"] is ws):
            self.active.pop(server_id, None)
            log.info("Agent uzildi: %s (qoldi %d)", server_id, len(self.active))

    def is_online(self, server_id):
        return server_id in self.active

    def online_ids(self):
        return set(self.active)

    def count(self):
        return len(self.active)

    # ---------------------------------------------------------------- yuborish
    async def send(self, server_id, msg):
        """Xom xabar yuboradi. Muvaffaqiyat bo'lsa True."""
        c = self.active.get(server_id)
        if not c:
            return False
        try:
            async with c["lock"]:
                await asyncio.wait_for(c["ws"].send_json(msg),
                                       timeout=SEND_TIMEOUT_S)
            return True
        except (asyncio.TimeoutError, Exception):                 # noqa: BLE001
            log.warning("%s ga yuborib bo'lmadi (%s) — ulanish yopiladi",
                        server_id, msg.get("type"))
            self.detach(server_id)
            try:
                await c["ws"].close(code=1011)
            except Exception:                                    # noqa: BLE001
                pass
            return False

    async def send_cmd(self, server_id, kind, **fields):
        """Imzolangan buyruq yuboradi.

        TASDIQLANMAGAN serverga hech qanday buyruq ketmaydi — bu tokensiz
        ulanishning xavfsizlik chegarasi (begona qurilma domenni bilса ham
        kontent, sozlama yoki e'lon olmaydi)."""
        if not db.is_approved(server_id):
            log.warning("%s tasdiqlanmagan — '%s' buyrug'i yuborilmadi",
                        server_id, kind)
            return False
        cmd = {"type": kind, "server_id": server_id, **fields}
        signed = security.sign_command(cmd)
        return await self.send(server_id, {"type": "cmd", **signed})

    # ------------------------------------------------------ desired state
    def build_manifest(self, server_id):
        """Serverда BO'LISHI KERAK bo'lgan to'liq kontent ro'yxati.

        Agent buni o'z holati bilan solishtiradi: yo'qini yuklaydi, ro'yxatda
        bo'lmagan bulut kontentini o'chiradi. Ya'ni "yuklash" va "o'chirish"
        bitta mexanizm — alohida delete buyrug'i kerak emas."""
        srv = db.get_server(server_id) or {}
        items = []
        for c in db.desired_content(server_id):
            def part(sha, name, size):
                if not sha or not storage.exists(sha):
                    return None
                return {
                    "sha256": sha,
                    "name": name or sha[:12],
                    "size": size or storage.size_of(sha),
                    "url": "/dl/" + security.make_dl_token(sha, server_id,
                                                           name or ""),
                }
            media = part(c["media_sha"], c["media_name"], c["media_size"])
            cover = part(c["cover_sha"], c["cover_name"], c["cover_size"])
            text = part(c["text_sha"], c["text_name"], c["text_size"])
            items.append({
                "cloud_id": c["id"],
                "type": c["type"],
                "title": c["title"],
                "author": c["author"],
                "genre": c["genre"],
                "description": c["description"],
                "duration": c["duration"],
                "pages": c["pages"],
                "lang": c["lang"],
                "category_tab": c["category_tab"],
                "is_recommended": c["is_recommended"],
                "cache_enabled": c["cache_enabled"],
                "visible": c["visible"],
                "media": media, "cover": cover, "text": text,
            })
        return {"rev": srv.get("desired_rev", 0), "items": items}

    async def push_manifest(self, server_id, job_id=None):
        """Manifestni yuboradi (offlayn bo'lsa False — navbatda qoladi)."""
        m = self.build_manifest(server_id)
        return await self.send_cmd(server_id, "manifest", rev=m["rev"],
                                   items=m["items"], job_id=job_id)

    async def dispatch_job(self, job_id, server_ids):
        """Ishni nishonlarga yuboradi. Offlayn serverlar `queued` bo'lib qoladi
        va ulangan zahoti (`on_register`) o'zi tortib oladi."""
        for sid in server_ids:
            if not self.is_online(sid):
                db.set_target(job_id, sid, state="queued")
                continue
            ok = await self.push_manifest(sid, job_id=job_id)
            db.set_target(job_id, sid, state="running" if ok else "queued")

    async def on_register(self, server_id):
        """Agent ulanib register qilgach: kutib qolgan ishlar va farqli rev
        bo'lsa manifest yuboriladi."""
        srv = db.get_server(server_id) or {}
        if not srv.get("approved"):
            log.info("%s tasdiqlanmagan — sinxronizatsiya kutib turadi",
                     server_id)
            return
        pend = db.pending_targets(server_id)
        job_id = pend[0]["job_id"] if pend else None
        need = bool(pend) or srv.get("applied_rev") != srv.get("desired_rev")
        if not need:
            return
        ok = await self.push_manifest(server_id, job_id=job_id)
        for p in pend:
            db.set_target(p["job_id"], server_id,
                          state="running" if ok else "queued")


relay = Relay()
