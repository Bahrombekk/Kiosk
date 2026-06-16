"""ui/server_thread.py — FastAPI backendni alohida oqimda ishga tushirish."""
import uvicorn
from PyQt6.QtCore import QThread

import config
import security
from main import app as fastapi_app


class ServerThread(QThread):
    """FastAPI backendni (uvicorn) alohida oqimda ishga tushiradi."""

    def __init__(self):
        super().__init__()
        # TLS sertifikat uvicorn.Config'dan oldin tayyor bo'lsin (USE_TLS bo'lsa
        # https/wss bilan ishlaymiz — kiosklar sertifikatni pin qiladi).
        security.ensure_identity()
        ssl_kw = ({"ssl_certfile": security.TLS_CERT_PATH,
                   "ssl_keyfile": security.TLS_KEY_PATH}
                  if config.USE_TLS else {})
        cfg = uvicorn.Config(fastapi_app, host=config.HOST, port=config.PORT,
                             log_level="warning", log_config=None, **ssl_kw)
        self.server = uvicorn.Server(cfg)
        # Asosiy oqimda emasligi uchun signal handlerlarni o'chiramiz
        self.server.install_signal_handlers = lambda: None

    def run(self):
        self.server.run()

    def stop(self):
        self.server.should_exit = True
