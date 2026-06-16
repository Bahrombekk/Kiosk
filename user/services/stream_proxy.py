"""
stream_proxy.py — Kiosk ichidagi LOKAL striming proxy (VLC/pleyer uchun).

Nega kerak: server TLS (https) + self-signed sertifikat bilan ishlaydi. Kiosk
HTTP mijozi (netpin) sertifikatni FINGERPRINT bilan pin qiladi — ishonchli.
Lekin LibVLC (va Qt Multimedia) o'z TLS tekshiruvini qiladi: self-signed +
IP hostname'ni RAD etadi -> video ochilmaydi (qora ekran, 00:00).

Yechim: 127.0.0.1 da kichik HTTP server. VLC undan ODDIY http bilan oladi
(sertifikat muammosi yo'q), proxy esa serverdan pinned netpin sessiyasi orqali
oladi (xavfsiz). HTTP Range to'liq uzatiladi — seek/oldinga-orqaga ishlaydi.

Bitta nusxa butun ilova davomida ishlaydi (ensure_proxy bir marta yoqadi).
"""
import http.server
import logging
import threading

from core import config
from core import netpin

log = logging.getLogger(__name__)

_httpd = None
_port = None
_lock = threading.Lock()

# Proxy yo'llari -> server endpointi
_ROUTES = {
    "m": "/api/stream/{id}",     # kino/audio striming
    "ad": "/api/ads/{id}/media",  # video reklama
}


class _Handler(http.server.BaseHTTPRequestHandler):
    """/m/<id> yoki /ad/<id> -> serverdan pinned HTTPS bilan olib uzatadi."""

    protocol_version = "HTTP/1.1"

    def do_GET(self):
        parts = self.path.lstrip("/").split("?", 1)[0].split("/")
        if len(parts) != 2 or parts[0] not in _ROUTES:
            self.send_error(404)
            return
        kind, cid = parts
        if not cid.isdigit():
            self.send_error(404)
            return
        upstream = config.SERVER_URL.rstrip("/") + _ROUTES[kind].format(id=cid)
        headers = {}
        if config.API_KEY:
            headers["X-API-Key"] = config.API_KEY
        rng = self.headers.get("Range")
        if rng:
            headers["Range"] = rng
        try:
            with netpin.session() as s, s.get(
                    upstream, headers=headers, stream=True, timeout=20) as r:
                self.send_response(r.status_code)
                # Content-Type: kino/musiqa (LibVLC) uchun MAJBURAN
                # octet-stream — fayl kengaytmasi noto'g'ri bo'lsa ham (masalan
                # .mp3 deb nomlangan mp4) VLC formatni O'ZI aniqlaydi. Reklama
                # (QMediaPlayer) uchun server bergan turni o'tkazamiz.
                if kind == "m":
                    self.send_header("Content-Type", "application/octet-stream")
                elif "Content-Type" in r.headers:
                    self.send_header("Content-Type", r.headers["Content-Type"])
                for h in ("Content-Length", "Content-Range"):
                    if h in r.headers:
                        self.send_header(h, r.headers[h])
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()
                for chunk in r.iter_content(64 * 1024):
                    if not chunk:
                        break
                    try:
                        self.wfile.write(chunk)
                    except (BrokenPipeError, ConnectionResetError):
                        return   # pleyer ulanishni uzdi (seek/yopish) — jim
        except Exception as e:                           # noqa: BLE001
            log.warning("Stream proxy xato (%s): %s", upstream, e)
            try:
                self.send_error(502)
            except Exception:                            # noqa: BLE001
                pass

    def log_message(self, *_a):
        pass   # konsolni ifloslantirmaslik uchun jim


class _QuietServer(http.server.ThreadingHTTPServer):
    """Pleyer seek/yopishda ulanishni keskin uzadi — bu shovqinli traceback
    bermasin (handle_error'ni jim qilamiz)."""
    daemon_threads = True

    def handle_error(self, request, client_address):
        pass


def ensure_proxy():
    """Lokal proxy serverini (bir marta) yoqadi, port qaytaradi (xato -> None)."""
    global _httpd, _port
    with _lock:
        if _httpd is not None:
            return _port
        try:
            httpd = _QuietServer(("127.0.0.1", 0), _Handler)
        except OSError as e:                             # noqa: BLE001
            log.warning("Stream proxy yoqilmadi: %s", e)
            return None
        _httpd = httpd
        _port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        log.info("Stream proxy 127.0.0.1:%d da ishga tushdi", _port)
        return _port


def play_proxy_url(content_id):
    """Kino/audio uchun lokal proxy URL (yoki None)."""
    port = ensure_proxy()
    return f"http://127.0.0.1:{port}/m/{content_id}" if port else None


def ad_proxy_url(ad_id):
    """Video reklama uchun lokal proxy URL (yoki None)."""
    port = ensure_proxy()
    return f"http://127.0.0.1:{port}/ad/{ad_id}" if port else None
