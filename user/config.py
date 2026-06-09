"""
config.py — Foydalanuvchi ilovasining sozlamalari (bir joyda).

Bu yerda server manzili va ulanish parametrlari turadi. Har bir qurilmaga
o'rnatishda faqat SHU faylni (yoki KIOSK_SERVER muhit o'zgaruvchisini)
o'zgartirasiz — kodga tegmaysiz (TZ 11.3 — "Serverni topish").
"""
import os

# Server manzili. Statik IP tavsiya etiladi (TZ 11.3).
# Muhit o'zgaruvchisi orqali ham berish mumkin: KIOSK_SERVER=http://192.168.1.1:8765
SERVER_URL = os.environ.get("KIOSK_SERVER", "http://127.0.0.1:8765")

# WebSocket manzili (SERVER_URL'dan avtomatik hosil qilinadi: http->ws)
WS_URL = SERVER_URL.replace("http://", "ws://").replace("https://", "wss://") + "/ws"

# HTTP so'rovlar uchun timeout (soniya)
REQUEST_TIMEOUT = 5

# Server uzilganda qayta ulanish oralig'i (millisekund) — TZ 12.2: har 5 soniyada
RECONNECT_INTERVAL_MS = 5000

# Boshlang'ich mavzu: "light" yoki "dark"
DEFAULT_THEME = "light"
