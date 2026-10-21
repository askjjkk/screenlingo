"""«Живая зона»: следит за областью экрана и переводит текст, когда он меняется."""
from PySide6.QtCore import QObject, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ..capture import exclude_from_capture, grab_rect
from ..change import ChangeDetector
from ..languages import LANGUAGES
from ..worker import Job
from . import theme
from .overlay import TranslationOverlay

INTERVAL_MS = 500
CLICK_THROUGH = (Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool
                 | Qt.WindowType.WindowTransparentForInput | Qt.WindowType.NoDropShadowWindowHint)


class _Transparent(QWidget):
    def __init__(self):
        super().__init__(None, CLICK_THROUGH)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

    def showEvent(self, e):
        super().showEvent(e)
        exclude_from_capture(self)


class ZoneFrame(_Transparent):
    """Пунктирная рамка вокруг зоны и ярлычок с подсказкой."""
    TAB_H = 22

    def __init__(self, rect: QRect, hotkey: str):
        super().__init__()
        self.label = f"Живая зона. Выключить: {hotkey}"
        self.status = ""
        self.setGeometry(rect.adjusted(-3, -3 - self.TAB_H, 3, 3))

    def set_status(self, text: str) -> None:
        self.status = text
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        zone = QRectF(1.5, self.TAB_H + 1.5, self.width() - 3, self.height() - self.TAB_H - 3)
        pen = QPen(theme.MARKER, 2, Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.drawRoundedRect(zone, 3, 3)
        font = QFont(theme.FONT)
        font.setPixelSize(12)
        p.setFont(font)
        text = self.label + (f"  ({self.status})" if self.status else "")
        w = QFontMetrics(font).horizontalAdvance(text) + 16
        tab = QRectF(0, 0, min(w, self.width()), self.TAB_H - 2)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(theme.MARKER)
        p.drawRoundedRect(tab, 5, 5)
        p.setPen(theme.INK)
        p.drawText(tab, int(Qt.AlignmentFlag.AlignCenter), text)


class CaptionBox(_Transparent):
    """Перевод отдельной плашкой над или под зоной (как субтитры)."""

    def __init__(self, zone: QRect, position: str):
        super().__init__()
        self.zone, self.position = zone, position
        self.text = ""
        self.opacity = 0.92

    def set_text(self, text: str, opacity: float) -> None:
        self.text = text
        self.opacity = opacity
        font = self._font()
        width = max(320, self.zone.width())
        flags = int(Qt.TextFlag.TextWordWrap)
        h = QFontMetrics(font).boundingRect(QRect(0, 0, width - 28, 10000), flags, text).height() + 20
        y = self.zone.bottom() + 8 if self.position == "below" else self.zone.top() - 8 - h - ZoneFrame.TAB_H
        self.setGeometry(self.zone.left(), y, width, h)
        self.setVisible(bool(text))
        self.update()

    def _font(self) -> QFont:
        font = QFont(theme.FONT)
        font.setPixelSize(17)
        font.setWeight(QFont.Weight.Medium)
        return font

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg = QColor(theme.INK)
        bg.setAlphaF(self.opacity)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(QRectF(self.rect()), 10, 10)
        p.setPen(theme.PAPER)
        p.setFont(self._font())
        p.drawText(QRectF(self.rect()).adjusted(14, 10, -14, -10), int(Qt.TextFlag.TextWordWrap), self.text)


class LiveZone(QObject):
    stopped = Signal()

    def __init__(self, rect: QRect, ocr, translator, get_settings, pool):
        super().__init__()
        self.rect, self.ocr, self.translator, self.pool = rect, ocr, translator, pool
        self.get_settings = get_settings  # настройки могут поменяться, пока зона работает
        settings = get_settings()
        self.detector = ChangeDetector()
        self.busy = False
        self.jobs = []
        self.frame = ZoneFrame(rect, settings.hotkey_live)
        self.frame.show()
        if settings.live_position == "over":
            self.view = TranslationOverlay(click_through=True)
            self.view.opacity = settings.opacity
            self.view.font_px = settings.font_size
            self.view.place(rect)
        else:
            self.view = CaptionBox(rect, settings.live_position)
        self.view.show()
        self.timer = QTimer(self, interval=INTERVAL_MS, timeout=self._tick)
        self.timer.start()
        self._tick()

    def _tick(self) -> None:
        if self.busy:
            return
        img, scale = grab_rect(self.rect)
        if not self.detector.feed(img):
            return
        self.busy = True
        self.frame.set_status("перевожу…")
        s = self.get_settings()
        job = Job(self.ocr, self.translator, s.source_lang, s.target_lang, img=img)
        job.signals.done.connect(lambda res, img=img, scale=scale: self._on_done(res, img, scale))
        self.jobs.append(job)
        self.pool.start(job)

    def _on_done(self, res, img, scale) -> None:
        self.busy = False
        self.jobs = self.jobs[-4:]  # держим ссылки, чтобы сигналы не удалились раньше времени
        if self.timer is None or not self.timer.isActive():
            return
        if res.error and res.error != "Текст не найден":
            status = res.error
        elif res.source:
            status = f"{LANGUAGES.get(res.source, res.source).lower()} → {LANGUAGES.get(self.get_settings().target_lang, '').lower()}"
        else:
            status = ""
        self.frame.set_status(status)
        if isinstance(self.view, TranslationOverlay):
            if res.blocks:
                self.view.set_result(img, scale, res.blocks, res.translations)
            else:
                self.view.clear()
        else:
            self.view.set_text("\n".join(res.translations), self.get_settings().opacity)

    def retranslate(self) -> None:
        """Сменили язык: перевести текущий текст заново при следующем тике."""
        self.detector.reset()

    def stop(self) -> None:
        if self.timer is None:
            return
        self.timer.stop()
        self.timer = None
        for w in (self.frame, self.view):
            w.close()
            w.deleteLater()
        self.stopped.emit()
