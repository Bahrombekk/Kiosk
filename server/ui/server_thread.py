"""ui/server_thread.py — FastAPI backendni alohida oqimda ishga tushirish."""
import uvicorn
from PyQt6.QtCore import QThread

import config


class ServerThread(QThread):
    """FastAPI backendni (uvicorn) alohida oqimda ishga tushiradi."""

    def __init__(self):
        super().__init__()
        cfg = uvicorn.Config("main:app", host=config.HOST, port=config.PORT,
                             log_level="warning")
        self.server = uvicorn.Server(cfg)
        # Asosiy oqimda emasligi uchun signal handlerlarni o'chiramiz
        self.server.install_signal_handlers = lambda: None

    def run(self):
        self.server.run()

    def stop(self):
        self.server.should_exit = True
