"""
icons.py — SVG ikonkalarni istalgan rangda QIcon/QPixmap qilib beradi.
Emoji-stikerlar o'rniga haqiqiy ikonkalar (Lucide to'plami, assets/icons/).
"""
import os
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
from PyQt6.QtSvg import QSvgRenderer

ICON_DIR = os.path.join(os.path.dirname(__file__), "..", "assets", "icons")


def svg_pixmap(name, color_hex, size=24):
    """assets/icons/<name>.svg ni berilgan rang va o'lchamda QPixmap qiladi."""
    path = os.path.join(ICON_DIR, name + ".svg")
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    if os.path.exists(path):
        p = QPainter(pm)
        QSvgRenderer(path).render(p, QRectF(0, 0, size, size))
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        p.fillRect(pm.rect(), QColor(color_hex))
        p.end()
    return pm


def svg_icon(name, color_hex, size=24):
    return QIcon(svg_pixmap(name, color_hex, size))
