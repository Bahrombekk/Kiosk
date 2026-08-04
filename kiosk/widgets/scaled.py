"""
scaled.py — ScaledScreen: kontentni qat'iy o'lchamli "canvas" sifatida saqlab,
QGraphicsView orqali nisbatni saqlagan holda ekranga miqyoslaydi.

Figma maketlari qat'iy 2048×1536 sahnani `transform: scale()` bilan miqyoslaydi;
shuning ekvivalenti. Shu tufayli ekran katta-kichik bo'lganda ham ko'rinish
buzilmaydi — shrift, masofa, rasm hammasi birga o'zgaradi.

Canvas widget quyidagilarga ega bo'lishi kerak:
  - apply_theme(name)
  - ixtiyoriy on_show()
  - ixtiyoriy timer (sahifadan chiqilganda to'xtatiladi)
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QGraphicsView, QGraphicsScene
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QColor

from core import theme as T


class ScaledScreen(QWidget):
    def __init__(self, canvas):
        super().__init__()
        self.canvas = canvas
        self.scene = QGraphicsScene(self)
        self.proxy = self.scene.addWidget(canvas)
        self.view = QGraphicsView(self.scene, self)
        self.view.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setRenderHints(QPainter.RenderHint.Antialiasing
                                 | QPainter.RenderHint.SmoothPixmapTransform)
        self.view.setStyleSheet("background: transparent; border: none;")
        # Shaffof — orqada turgan oyna foni (atlas rasmi) ko'rinsin
        self.view.setBackgroundBrush(Qt.GlobalColor.transparent)
        self.view.viewport().setAutoFillBackground(False)
        self.view.viewport().setStyleSheet("background: transparent;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.view)

    def _fit(self):
        self.view.fitInView(self.proxy, Qt.AspectRatioMode.KeepAspectRatio)

    def resizeEvent(self, e):
        self._fit()
        super().resizeEvent(e)

    def showEvent(self, e):
        self._fit()
        super().showEvent(e)

    # --- main.py kutadigan interfeys ---
    def apply_theme(self, name):
        self.canvas.apply_theme(name)
        # Sahna/ko'rinish shaffof — letterbox ham oyna fonini (atlas) ko'rsatadi
        self.view.setBackgroundBrush(Qt.GlobalColor.transparent)
        self.scene.setBackgroundBrush(Qt.GlobalColor.transparent)

    def on_show(self):
        if hasattr(self.canvas, "on_show"):
            self.canvas.on_show()
        self._fit()

    def hideEvent(self, e):
        t = getattr(self.canvas, "timer", None)
        if t is not None:
            t.stop()
        super().hideEvent(e)
