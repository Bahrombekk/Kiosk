"""
web_server.py — Veb kiosk (Nuxt) ilovasini server BILAN BIRGA ishga tushiradi.

Maqsad: admin (server) ochilganda veb-ilova ham avtomatik ko'tarilsin — qo'lda
alohida `npm run dev` qilish shart emas. Server yopilganda veb ham to'xtaydi.

Talab: mashinada **Node.js** o'rnatilgan bo'lsin. Topilmasa jim o'tamiz —
server baribir ishlayveradi, faqat veb ko'tarilmaydi (log'ga yoziladi).

Rejim aniqlash:
  - `<web>/.output/server/index.mjs` bor bo'lsa  -> `node` (build, tez, prod)
  - aks holda `<web>/package.json` bor bo'lsa     -> `npm run dev` (ishlab chiqish)

Veb papka:
  - manba rejimi: `<repo>/kiosk`
  - frozen (exe):  exe yonidagi `web/` papka
  - `KIOSK_WEB_DIR` muhit o'zgaruvchisi bilan bekor qilinadi

Sozlash (muhit o'zgaruvchilari):
  KIOSK_WEB_DISABLE=1   — veb'ni umuman ishga tushirmaslik
  KIOSK_WEB_DIR=...     — veb ilova papkasi (avto-aniqlashni bekor qiladi)
  KIOSK_WEB_HOST=...    — veb bind manzili (standart 0.0.0.0 — LAN'dan ochiladi)
  KIOSK_WEB_PORT=...    — veb porti (standart 80)
"""
import os
import sys
import shutil
import logging
import subprocess
import threading

import config

log = logging.getLogger("kiosk.web")

# Veb kioskning oflayn (LAN) domeni. Kiosk qurilmalar shu nom bilan ochadi —
# DNS kerak emas, har qurilmaning hosts fayliga yoziladi (internetga chiqmaydi).
WEB_DOMAIN = os.environ.get("KIOSK_WEB_DOMAIN", "poyezd.uz")


def _hosts_path():
    return os.path.join(os.environ.get("WINDIR", r"C:\Windows"),
                        "System32", "drivers", "etc", "hosts")


def ensure_hosts_entry(domain, ip="127.0.0.1"):
    """`<ip> <domain>` yozuvini hosts fayliga qo'shadi (bo'lmasa). Idempotent —
    har ishga tushishda tekshiradi, faqat yo'q bo'lsa yozadi. Admin kerak;
    bo'lmasa jim ogohlantirib o'tadi (installer admin bilan ham qiladi)."""
    if os.name != "nt":
        return
    path = _hosts_path()
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except OSError:
        return
    for line in content.splitlines():
        s = line.strip()
        if s and not s.startswith("#") and domain in s.split()[1:]:
            return   # allaqachon bor
    try:
        with open(path, "a", encoding="utf-8") as f:
            if content and not content.endswith("\n"):
                f.write("\n")
            f.write(f"{ip}\t{domain}\t# Kiosk veb (avto)\n")
        log.info("hosts: %s -> %s qo'shildi", domain, ip)
    except OSError as e:
        log.warning("hosts'ga yozib bo'lmadi (admin kerak): %s", e)


def ensure_firewall(port, node_path=None):
    """Veb porti uchun inbound firewall qoidasini qo'shadi (bo'lmasa) VA
    AYNAN BIZ ishlatadigan node.exe uchun Windows avto-yaratgan BLOCK
    qoidalarini o'chiradi.

    MUHIM: Windows'da Block qoidasi Allow'dan USTUN. Node birinchi marta portni
    ochganda Windows firewall oynasi chiqadi; "Bekor" bosilsa 'Node.js JavaScript
    Runtime' Block qoidasi yaratiladi va port ochiq bo'lsa ham LAN'dan ulanishni
    to'sadi (kiosk qurilma "connection timed out" oladi). Shuni tozalaymiz.

    Faqat `node_path`ga aniq mos qoidalar o'chiriladi — avvalgi '*node*'
    wildcard butun tizimdagi (boshqa ilovalar ataylab qo'ygan) node block
    qoidalarini ham o'chirib yuborardi."""
    if os.name != "nt":
        return
    name = f"Kiosk Web {port}"
    try:
        # 1) Bizning node.exe uchun Block qoidalarini o'chiramiz
        if node_path:
            np = node_path.replace("'", "''")
            subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-NetFirewallRule -Action Block -Enabled True -ErrorAction SilentlyContinue |"
                 " Where-Object { ($_ | Get-NetFirewallApplicationFilter -ErrorAction SilentlyContinue)."
                 f"Program -eq '{np}' }} | Remove-NetFirewallRule -ErrorAction SilentlyContinue"],
                capture_output=True, text=True, timeout=30)
        # 2) Port uchun Allow qoidasi (bo'lmasa)
        chk = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"Get-NetFirewallRule -DisplayName '{name}' -ErrorAction SilentlyContinue"],
            capture_output=True, text=True, timeout=15)
        if not chk.stdout.strip():
            subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"New-NetFirewallRule -DisplayName '{name}' -Direction Inbound "
                 f"-Action Allow -Protocol TCP -LocalPort {port} -Profile Any"],
                capture_output=True, text=True, timeout=15)
            log.info("Firewall: %s-port ochildi", port)
    except Exception:                                    # noqa: BLE001
        log.warning("Firewall qoidasini sozlab bo'lmadi (admin kerak)")


def _default_web_dir():
    """Veb ilova papkasini topadi (yo'q bo'lsa None)."""
    if getattr(sys, "frozen", False):
        d = os.path.join(os.path.dirname(sys.executable), "web")
    else:
        # ui/ -> server/ -> <repo>/kiosk
        repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        d = os.path.join(os.path.dirname(repo), "kiosk")
    return d if os.path.isdir(d) else None


# web.log shu hajmdan oshsa yangi ishga tushishda .1 nusxaga suriladi
_LOG_MAX_BYTES = 5 * 1024 * 1024


def _kill_orphan_web():
    """Oldingi seansdan qolgan "yetim" Nuxt node jarayonini o'ldiradi.

    Server nokorrekt yopilса (crash / majburiy taskkill) web bola jarayoni
    o'lmay qolib, 80-portni band qilib turishi mumkin — u holda yangi server
    eski (nomuvofiq) build'ni ko'rsatib qoladi. Startда commandline'da
    `.output/server/index.mjs` bo'lgan node.exe'ни topib o'ldiramiz."""
    if os.name != "nt":
        return
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name='node.exe'\" | "
             "Where-Object { $_.CommandLine -like '*.output*server*index.mjs*' } | "
             "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"],
            capture_output=True, timeout=20)
    except Exception:                                # noqa: BLE001
        log.debug("Yetim web jarayonini tozalashda xato", exc_info=True)


class WebServer:
    """Nuxt veb-ilovani bola jarayon sifatida boshqaradi (start/stop)."""

    def __init__(self):
        self.proc = None
        self._logf = None
        self._stopped = False
        self._start_thread = None

    def start(self):
        """Veb'ni FON oqimida ko'taradi — ensure_firewall/hosts sinxron
        PowerShell chaqiruvlari (30s+ timeout) GUI (login) oynasini bloklab
        qo'ymasin. stop() bilan poyga _stopped flag orqali hal qilinadi."""
        t = threading.Thread(target=self._start_impl, name="kiosk-web-start",
                             daemon=True)
        self._start_thread = t
        t.start()

    def _start_impl(self):
        if os.environ.get("KIOSK_WEB_DISABLE") == "1":
            log.info("Veb o'chirilgan (KIOSK_WEB_DISABLE=1)")
            return

        web_dir = os.environ.get("KIOSK_WEB_DIR") or _default_web_dir()
        if not web_dir or not os.path.isdir(web_dir):
            log.info("Veb ilova papkasi topilmadi — veb ishga tushirilmaydi")
            return

        host = os.environ.get("KIOSK_WEB_HOST", "0.0.0.0")
        port = os.environ.get("KIOSK_WEB_PORT", "80")

        # Oldingi seansdan qolgan yetim node'ни tozalaymiz (80-port bo'shasin,
        # yangi build ko'rinsin — aks holda eski node eski build'ni beradi).
        _kill_orphan_web()

        built = os.path.join(web_dir, ".output", "server", "index.mjs")
        node = shutil.which("node")
        npm = shutil.which("npm") or shutil.which("npm.cmd")

        if os.path.isfile(built) and node:
            cmd, mode = [node, os.path.join(".output", "server", "index.mjs")], "build"
        elif npm and os.path.isfile(os.path.join(web_dir, "package.json")):
            cmd, mode = [npm, "run", "dev"], "dev"
        else:
            log.warning("Node.js/npm yoki veb build topilmadi — veb ishga tushirilmaydi")
            return

        # Oflayn domen + tarmoq: server ishga tushganda avtomatik sozlanadi
        # (qo'lda hech narsa kerak emas). hosts -> server o'zi http://poyezd.uz
        # ni ocha oladi; firewall -> kiosk qurilmalar LAN'dan ulanadi.
        ensure_hosts_entry(WEB_DOMAIN, "127.0.0.1")
        ensure_firewall(port, node_path=node)

        # Veb (Nitro) -> Python backend'ni SHU mashinada (localhost) chaqiradi;
        # API kalitni va TLS sxemasini uzatamiz.
        env = os.environ.copy()
        scheme = "https" if config.USE_TLS else "http"
        env["NUXT_KIOSK_SERVER"] = f"{scheme}://127.0.0.1:{config.PORT}"
        if config.USE_TLS:
            # Self-signed sertifikatni Node'ga TANITAMIZ (SAN'da 127.0.0.1 bor)
            # — TLS tekshiruvi to'liq yoqiq qoladi. Busiz Nitro'ning har fetch'i
            # UNABLE_TO_VERIFY_LEAF_SIGNATURE bilan yiqilar edi; global
            # NODE_TLS_REJECT_UNAUTHORIZED=0 esa xavfsizlik teshigi.
            try:
                import security
                if os.path.isfile(security.TLS_CERT_PATH):
                    env["NODE_EXTRA_CA_CERTS"] = security.TLS_CERT_PATH
                else:
                    log.warning("TLS sertifikat topilmadi (%s) — veb backend'ga "
                                "ulana olmaydi", security.TLS_CERT_PATH)
            except Exception:                            # noqa: BLE001
                log.exception("TLS sertifikat yo'lini aniqlashda xato")
        try:
            import db
            env["NUXT_KIOSK_API_KEY"] = db.get_or_create_api_key()
        except Exception:                                # noqa: BLE001
            log.exception("API kalitni olishda xato — veb kalitsiz ketadi")
        # Nuxt (listhen) va nitro node-server ikkalasi ham shu o'zgaruvchilarni o'qiydi.
        env["HOST"] = host
        env["PORT"] = port
        env["NITRO_HOST"] = host
        env["NITRO_PORT"] = port

        # Bola jarayon chiqishini alohida log'ga yo'naltiramiz (admin konsoli toza qolsin).
        try:
            log_dir = os.path.join(config.BASE_DIR, "logs")
            os.makedirs(log_dir, exist_ok=True)
            log_path = os.path.join(log_dir, "web.log")
            # Oddiy rotatsiya: fayl juda kattarib ketsa .1 ga suramiz
            try:
                if (os.path.isfile(log_path)
                        and os.path.getsize(log_path) > _LOG_MAX_BYTES):
                    os.replace(log_path, log_path + ".1")
            except OSError:
                pass
            self._logf = open(log_path, "a", encoding="utf-8")
        except OSError:
            self._logf = None

        if self._stopped:
            return   # start tugashidan oldin stop() chaqirilgan (login bekor)
        try:
            flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
            self.proc = subprocess.Popen(
                cmd, cwd=web_dir, env=env,
                stdout=self._logf or subprocess.DEVNULL,
                stderr=subprocess.STDOUT,
                creationflags=flags)
            if self._stopped:   # poyga: Popen paytida stop kelgan bo'lsa
                self.stop()
                return
            # Toza URL (port 80 bo'lsa portsiz). Kiosk qurilmalar shu domen
            # bilan ochadi (hosts orqali server IP'ga yo'naladi).
            url = f"http://{WEB_DOMAIN}" if str(port) == "80" else f"http://{WEB_DOMAIN}:{port}"
            log.info("Veb ishga tushdi (%s) — bind %s:%s | oching: %s",
                     mode, host, port, url)
        except Exception:                                # noqa: BLE001
            log.exception("Veb ishga tushirib bo'lmadi")

    def stop(self):
        """Veb bola jarayonini (va uning bolalarini) to'xtatadi."""
        self._stopped = True
        p = self.proc
        self.proc = None
        if p and p.poll() is None:
            try:
                if os.name == "nt":
                    # npm -> node daraxtini butunlay yopamiz (terminate npm'ni
                    # yopib, node'ni tirik qoldirishi mumkin).
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)],
                                   capture_output=True)
                else:
                    p.terminate()
                    p.wait(timeout=5)
            except Exception:                            # noqa: BLE001
                try:
                    p.kill()
                except Exception:                        # noqa: BLE001
                    pass
        if self._logf:
            try:
                self._logf.close()
            except OSError:
                pass
            self._logf = None
