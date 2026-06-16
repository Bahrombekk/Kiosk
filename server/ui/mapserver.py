"""ui/mapserver.py — Bekat xaritasi uchun kichik LOKAL HTTP server.

Nega kerak: oflayn vektor xarita (MapLibre + PMTiles) ma'lumotni HTTP "Range"
so'rovlari bilan o'qiydi — bu `file://` da ishlamaydi. Shuning uchun xarita
assetlari (assets/map/) 127.0.0.1 dagi ixtiyoriy portda, Range qo'llab-quvvatlovchi
oddiy server orqali beriladi. Server faqat lokal (admin oynasi WebEngine) uchun;
asosiy API serveriga (auth/TLS) aralashmaydi.

Bitta nusxa butun ilova davomida ishlaydi (ensure_map_server bir marta yoqadi).
"""
import functools
import http.server
import os
import threading

from icons import ICON_DIR

MAP_DIR = os.path.join(os.path.dirname(ICON_DIR), "map")   # assets/map

_httpd = None
_port = None
_lock = threading.Lock()


class _RangeHandler(http.server.SimpleHTTPRequestHandler):
    """Belgilangan papkadan fayl beradi, HTTP Range bilan (PMTiles uchun shart)."""

    def end_headers(self):
        # WebEngine'dan o'qishda CORS to'siq bo'lmasin (pmtiles fetch)
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def do_GET(self):
        rng = self.headers.get("Range")
        if not rng:
            return super().do_GET()
        path = self.translate_path(self.path)
        if not os.path.isfile(path):
            return super().do_GET()
        size = os.path.getsize(path)
        try:
            start, end = self._parse_range(rng, size)
        except ValueError:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.end_headers()
            return
        length = end - start + 1
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(length))
        self.end_headers()
        with open(path, "rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                chunk = f.read(min(65536, remaining))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    return   # WebEngine ulanishni uzdi — jim chiqamiz
                remaining -= len(chunk)

    @staticmethod
    def _parse_range(h, size):
        units, _, rng = h.partition("=")
        if units.strip() != "bytes" or "," in rng:
            raise ValueError("faqat bitta bytes oralig'i")
        s, _, e = rng.partition("-")
        s, e = s.strip(), e.strip()
        if s == "":
            if not e:
                raise ValueError("bo'sh range")
            start, end = max(0, size - int(e)), size - 1
        else:
            start = int(s)
            end = min(int(e), size - 1) if e else size - 1
        if start > end or start >= size:
            raise ValueError("chegaradan tashqari")
        return start, end

    def log_message(self, *_a):
        pass   # konsolni ifloslantirmaslik uchun jim


def ensure_map_server():
    """Lokal xarita serverini (bir marta) yoqadi va port raqamini qaytaradi.
    Xarita papkasi bo'lmasa yoki yoqib bo'lmasa None qaytaradi."""
    global _httpd, _port
    with _lock:
        if _httpd is not None:
            return _port
        if not os.path.isdir(MAP_DIR):
            return None
        try:
            handler = functools.partial(_RangeHandler, directory=MAP_DIR)
            httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        except OSError:
            return None
        _httpd = httpd
        _port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        return _port


def map_url(path="index.html"):
    """Lokal xarita URL'i (yoki None — server yo'q)."""
    port = ensure_map_server()
    if port is None:
        return None
    return f"http://127.0.0.1:{port}/{path}"
