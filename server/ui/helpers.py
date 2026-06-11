"""ui/helpers.py — Kichik yordamchi funksiyalar (media, format, tarmoq)."""
import os
import socket

from PyQt6.QtWidgets import QApplication, QWidget, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt, QObject, QEvent


class _WheelGuard(QObject):
    """Spinbox/combo ustida sahifa aylantirilganda qiymat ADASHIB o'zgarib
    ketmasin: fokus bo'lmasa g'ildirak hodisasi widgetga yetmaydi, ota-
    widgetga (scroll'ga) uzatiladi — sahifa odatdagidek aylanaveradi.
    Qiymatni ataylab o'zgartirish: avval bosib (fokus), keyin g'ildirak."""

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Type.Wheel and not obj.hasFocus():
            parent = obj.parentWidget()
            if parent is not None:
                QApplication.sendEvent(parent, ev)
            return True
        return False


_wheel_guard = None


def no_wheel(*widgets):
    """Berilgan spinbox/combo'larda tasodifiy g'ildirak o'zgarishini o'chiradi."""
    global _wheel_guard
    if _wheel_guard is None:
        _wheel_guard = _WheelGuard()
    for w in widgets:
        # WheelFocus emas — g'ildirakning o'zi fokus bermasin
        w.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        w.installEventFilter(_wheel_guard)


def _media_duration(path):
    """Media fayl davomiyligini (soniya) o'qiydi. ffprobe -> cv2 -> None."""
    try:
        import subprocess
        import json as _json
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        out = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "json", path],
            capture_output=True, text=True, timeout=20, creationflags=flags)
        dur = _json.loads(out.stdout or "{}").get("format", {}).get("duration")
        if dur:
            return int(round(float(dur)))
    except Exception:
        pass
    try:
        import cv2
        cap = cv2.VideoCapture(path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        cap.release()
        if fps and frames:
            return int(round(frames / fps))
    except Exception:
        pass
    return None


def _title_from_filename(path):
    """Fayl nomidan toza sarlavha hosil qiladi (kengaytmasiz, _ va - -> bo'sh joy)."""
    base = os.path.splitext(os.path.basename(path))[0]
    return base.replace("_", " ").replace("-", " ").strip()


def _pill(text, fg, bg):
    """Jadval katagi uchun rangli 'badge' (pill) widget yasaydi.

    Sichqoncha hodisalarini o'tkazib yuboradi — qator tanlash/dblclick
    odatdagidek ishlayveradi."""
    wrap = QWidget()
    row = QHBoxLayout(wrap)
    row.setContentsMargins(10, 0, 10, 0)
    lab = QLabel(text)
    lab.setStyleSheet(
        f"background: {bg}; color: {fg}; border-radius: 10px;"
        f"padding: 3px 10px; font-weight: 600; font-size: 12px;")
    row.addWidget(lab, 0, Qt.AlignmentFlag.AlignLeft)
    for x in (wrap, lab):
        x.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    return wrap


def _fmt_uptime(secs):
    """Soniyalarni odam o'qiydigan ko'rinishga ('2s 14m' kabi) aylantiradi."""
    secs = int(secs)
    if secs < 60:
        return f"{secs} soniya"
    m, s = divmod(secs, 60)
    if m < 60:
        return f"{m} daq {s} son"
    h, m = divmod(m, 60)
    return f"{h} soat {m} daq"


def port_in_use(port, host="127.0.0.1"):
    """Port allaqachon band emasmi? (oldingi server nusxasi ishlayotgan bo'lishi mumkin)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def local_ips():
    """Tarmoqdagi mahalliy IP manzillarni qaytaradi (user qurilmalar shunga ulanadi)."""
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except socket.gaierror:
        pass
    ips.discard("127.0.0.1")
    return sorted(ips) or ["127.0.0.1"]
