"""Окно, которое рисует перевод прямо поверх оригинального текста."""
import numpy as np
from PySide6.QtCore import QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import QWidget

from ..capture import exclude_from_capture
from . import theme

MARGIN = 6       # запас вокруг зоны, чтобы плашки могли чуть выходить за края
OVERFLOW = 160   # место снизу, если перевод длиннее оригинала


def background_of(img: np.ndarray, box) -> QColor:
    """Цвет фона вокруг блока текста: медиана пикселей рамки шириной 3 px."""
    h, w = img.shape[:2]
    x, y, bw, bh = box
    x0, y0 = max(0, x - 3), max(0, y - 3)
    x1, y1 = min(w, x + bw + 3), min(h, y + bh + 3)
    region = img[y0:y1, x0:x1]
    if region.size == 0:
        return QColor(theme.INK)
    ring = np.concatenate([region[:3].reshape(-1, 3), region[-3:].reshape(-1, 3),
                           region[:, :3].reshape(-1, 3), region[:, -3:].reshape(-1, 3)])
    r, g, b = np.median(ring, axis=0).astype(int)
    return QColor(int(r), int(g), int(b))


def text_color_for(bg: QColor) -> QColor:
    lum = 0.299 * bg.red() + 0.587 * bg.green() + 0.114 * bg.blue()
    return QColor("#121521") if lum > 140 else QColor("#F7F8FC")


def fit_font(text: str, rect: QRectF, start_px: int, fixed_px: int = 0) -> tuple[QFont, int]:
    """Самый крупный шрифт (не больше start_px), при котором текст помещается в рамку.
    Возвращает шрифт и нужную высоту (может быть больше рамки, если не влез даже мелкий)."""
    font = QFont(theme.FONT)
    font.setWeight(QFont.Weight.Medium)
    flags = int(Qt.TextFlag.TextWordWrap)
    sizes = [fixed_px] if fixed_px else range(max(9, start_px), 8, -1)
    height = 0
    for px in sizes:
        font.setPixelSize(px)
        height = QFontMetrics(font).boundingRect(QRect(0, 0, int(rect.width()), 100000), flags, text).height()
        if height <= rect.height() + 2:
            break
    return font, height


class TranslationOverlay(QWidget):
    hold_changed = Signal(bool)  # True = кнопку мыши зажали: показать оригинал

    def __init__(self, click_through: bool = False):
        flags = (Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                 | Qt.WindowType.Tool | Qt.WindowType.NoDropShadowWindowHint)
        if click_through:
            flags |= Qt.WindowType.WindowTransparentForInput
        super().__init__(None, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.img = None
        self.scale = 1.0
        self.blocks, self.translations = [], []
        self.show_original = False
        self.opacity = 0.92
        self.font_px = 0
        self._layout = []  # кэш: (прямоугольник, цвет фона, цвет текста, шрифт, текст)

    def place(self, rect: QRect) -> None:
        self.setGeometry(rect.adjusted(-MARGIN, -MARGIN, MARGIN, MARGIN + OVERFLOW))

    def set_result(self, img, scale: float, blocks, translations) -> None:
        self.img, self.scale = img, scale
        self.blocks, self.translations = blocks, translations
        self._relayout()
        self.update()

    def clear(self) -> None:
        self.set_result(None, 1.0, [], [])

    def set_original(self, on: bool) -> None:
        self.show_original = on
        self.update()

    def _relayout(self) -> None:
        self._layout = []
        if self.img is None:
            return
        for block, text in zip(self.blocks, self.translations):
            x, y, w, h = (v / self.scale for v in block.box)
            rect = QRectF(x + MARGIN - 3, y + MARGIN - 2, w + 6, h + 4)
            line_h = sum(l.box[3] for l in block.lines) / len(block.lines) / self.scale
            font, need = fit_font(text, rect.adjusted(4, 0, -4, 0), int(line_h * 0.78), self.font_px)
            if need > rect.height():
                rect.setHeight(need + 4)
            bg = background_of(self.img, block.box)
            self._layout.append((rect, bg, text_color_for(bg), font, text))

    def paintEvent(self, _):
        if self.show_original or not self._layout:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        for rect, bg, fg, font, text in self._layout:
            fill = QColor(bg)
            fill.setAlphaF(self.opacity)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(fill)
            p.drawRoundedRect(rect, 4, 4)
            p.setPen(fg)
            p.setFont(font)
            p.drawText(rect.adjusted(4, 0, -4, 0), int(Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap), text)

    def mousePressEvent(self, e):
        self.set_original(True)
        self.hold_changed.emit(True)

    def mouseReleaseEvent(self, e):
        self.set_original(False)
        self.hold_changed.emit(False)

    def showEvent(self, e):
        super().showEvent(e)
        exclude_from_capture(self)
