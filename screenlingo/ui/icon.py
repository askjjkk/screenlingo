"""Иконка программы, нарисованная кодом: плашка-«наклейка» с буквой A поверх иероглифа."""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap

from . import theme


def make_pixmap(size: int = 256, live: bool = False) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = size / 256
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(theme.INK)
    p.drawRoundedRect(QRectF(8 * s, 8 * s, 240 * s, 240 * s), 56 * s, 56 * s)
    # оригинал: иероглиф на заднем плане
    f = QFont("Yu Gothic UI")
    f.setPixelSize(int(150 * s))
    f.setWeight(QFont.Weight.Bold)
    p.setFont(f)
    p.setPen(QColor(theme.MUTED))
    p.drawText(QRectF(18 * s, 6 * s, 170 * s, 170 * s), int(Qt.AlignmentFlag.AlignCenter), "文")
    # перевод: жёлтая плашка, наклеенная поверх
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(theme.ERROR) if live else theme.MARKER)
    p.drawRoundedRect(QRectF(104 * s, 104 * s, 128 * s, 128 * s), 26 * s, 26 * s)
    f = QFont(theme.FONT)
    f.setPixelSize(int(104 * s))
    f.setWeight(QFont.Weight.Black)
    p.setFont(f)
    p.setPen(theme.INK)
    p.drawText(QRectF(104 * s, 104 * s, 128 * s, 128 * s), int(Qt.AlignmentFlag.AlignCenter), "A")
    p.end()
    return pm


def make_icon(live: bool = False) -> QIcon:
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(make_pixmap(size, live))
    return icon
