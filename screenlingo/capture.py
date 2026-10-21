"""Снимки экрана через Qt и исключение наших окон из снимков."""
import ctypes
import os

import numpy as np
from PySide6.QtCore import QRect
from PySide6.QtGui import QGuiApplication, QImage

WDA_EXCLUDEFROMCAPTURE = 0x11  # Windows 10 2004+: окно не попадает в скриншоты


def exclude_from_capture(widget) -> None:
    """Чтобы живая зона не «видела» и не переводила наш же перевод.
    SCREENLINGO_SHOW_IN_CAPTURE=1 отключает это (для скриншотов в README)."""
    if os.environ.get("SCREENLINGO_SHOW_IN_CAPTURE") == "1":
        return
    try:
        ctypes.windll.user32.SetWindowDisplayAffinity(int(widget.winId()), WDA_EXCLUDEFROMCAPTURE)
    except (AttributeError, OSError):
        pass


def qimage_to_numpy(img: QImage) -> np.ndarray:
    img = img.convertToFormat(QImage.Format.Format_RGB888)
    w, h, bpl = img.width(), img.height(), img.bytesPerLine()
    arr = np.frombuffer(img.constBits(), np.uint8, count=bpl * h).reshape(h, bpl)
    return arr[:, : w * 3].reshape(h, w, 3).copy()


def grab_rect(rect: QRect) -> tuple[np.ndarray, float]:
    """Снимок области в глобальных логических координатах.
    Возвращает RGB-картинку и масштаб (сколько пикселей картинки в одном логическом пикселе)."""
    screen = QGuiApplication.screenAt(rect.center()) or QGuiApplication.primaryScreen()
    g = screen.geometry()
    img = screen.grabWindow(0, rect.x() - g.x(), rect.y() - g.y(), rect.width(), rect.height()).toImage()
    return qimage_to_numpy(img), img.width() / max(1, rect.width())
