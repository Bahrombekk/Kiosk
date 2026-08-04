"""
vlcsetup.py — O'rnatilgan (PyInstaller) nusxada birga keladigan VLC'ni ulash.

MUHIM: `players.video` (import vlc) yuklanishidan OLDIN `setup_vlc()`
chaqirilishi shart (main.py modul darajasida chaqiradi). VLC o'rnatilmagan
kompyuterda ham video ishlashi uchun libvlc dasturga qo'shib beriladi
(_internal/vlc), python-vlc'ga yo'lini env orqali ko'rsatamiz.
"""
import os
import sys


def setup_vlc():
    """Frozen buildda birga kelgan libvlc'ni python-vlc uchun sozlaydi."""
    if getattr(sys, "frozen", False):
        # Zaxira yo'l: _MEIPASS bo'lmasa user/ ildizi (bu fayl system/ ichida)
        _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        _vlc_dir = os.path.join(getattr(sys, "_MEIPASS", _root), "vlc")
        if os.path.isdir(_vlc_dir):
            os.environ.setdefault("PYTHON_VLC_LIB_PATH",
                                  os.path.join(_vlc_dir, "libvlc.dll"))
            os.environ.setdefault("VLC_PLUGIN_PATH",
                                  os.path.join(_vlc_dir, "plugins"))
            os.add_dll_directory(_vlc_dir)
