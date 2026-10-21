"""Выделение области мышкой поверх «замороженного» снимка всех мониторов."""
from PySide6.QtCore import QObject, QRect, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ..capture import qimage_to_numpy
from . import theme


class _Shade(QWidget):
    def __init__(self, owner, screen, hint: str):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.Tool)
        self.owner, self.screen_ = owner, screen
        self.shot = screen.grabWindow(0)  # снимок до появления окна: текст не исчезнет, пока выделяем
        self.hint = hint
        self.start = self.end = None
        self.setScreen(screen)
        self.setGeometry(screen.geometry())
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)

    def selection(self) -> QRect:
        if self.start is None:
            return QRect()
        return QRect(self.start, self.end).normalized()

    def paintEvent(self, _):
        p = QPainter(self)
        p.drawPixmap(self.rect(), self.shot)
        sel = self.selection()
        shade = QColor(theme.INK)
        shade.setAlpha(140)
        if sel.isEmpty():
            p.fillRect(self.rect(), shade)
        else:
            r = self.rect()
            for part in (QRect(r.left(), r.top(), r.width(), sel.top() - r.top()),
                         QRect(r.left(), sel.bottom() + 1, r.width(), r.bottom() - sel.bottom()),
                         QRect(r.left(), sel.top(), sel.left() - r.left(), sel.height()),
                         QRect(sel.right() + 1, sel.top(), r.right() - sel.right(), sel.height())):
                p.fillRect(part, shade)
            p.setPen(QPen(theme.MARKER, 2))
            p.drawRect(sel.adjusted(-1, -1, 0, 0))
            p.setFont(QFont(theme.FONT, 9))
            p.setPen(theme.PAPER)
            p.drawText(sel.left(), sel.top() - 6, f"{sel.width()} × {sel.height()}")
        p.setFont(QFont(theme.FONT, 12))
        box = QRect(0, 24, self.width(), 40)
        p.setPen(theme.PAPER)
        p.drawText(box, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, self.hint)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.RightButton:
            self.owner.cancel()
            return
        self.start = self.end = e.position().toPoint()
        self.update()

    def mouseMoveEvent(self, e):
        if self.start is not None:
            self.end = e.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, e):
        if self.start is None or e.button() != Qt.MouseButton.LeftButton:
            return
        self.end = e.position().toPoint()
        sel = self.selection()
        if sel.width() < 8 or sel.height() < 8:
            self.start = self.end = None
            self.update()
            return
        scale = self.shot.width() / max(1, self.width())
        phys = QRect(int(sel.x() * scale), int(sel.y() * scale), int(sel.width() * scale), int(sel.height() * scale))
        img = qimage_to_numpy(self.shot.toImage().copy(phys))
        self.owner.finish(sel.translated(self.screen_.geometry().topLeft()), img, scale)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.owner.cancel()


class Selector(QObject):
    selected = Signal(QRect, object, float)  # глобальный прямоугольник, RGB-картинка, масштаб
    cancelled = Signal()

    def __init__(self, hint: str):
        super().__init__()
        self.shades = [_Shade(self, s, hint) for s in QGuiApplication.screens()]
        for w in self.shades:
            w.show()
        under_cursor = QGuiApplication.screenAt(QCursor.pos())
        main = next((w for w in self.shades if w.screen_ is under_cursor), self.shades[0])
        main.activateWindow()
        main.raise_()
        main.setFocus()

    def _close(self):
        for w in self.shades:
            w.close()
            w.deleteLater()
        self.shades = []

    def finish(self, rect: QRect, img, scale: float):
        self._close()
        self.selected.emit(rect, img, scale)

    def cancel(self):
        self._close()
        self.cancelled.emit()
