"""Панель рядом с выделенной областью: текст перевода, язык, копирование."""
from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout,
                               QWidget)

from ..capture import exclude_from_capture
from ..languages import LANGUAGES
from . import theme

WIDTH = 420


def language_combo(current: str, with_auto: bool = False) -> QComboBox:
    box = QComboBox()
    if with_auto:
        box.addItem("Определить автоматически", "auto")
    first = ["ru", "en", "uk", "de", "fr", "es", "ja", "zh-CN", "ko"]
    for code in first + sorted((c for c in LANGUAGES if c not in first), key=LANGUAGES.get):
        box.addItem(LANGUAGES[code], code)
    box.setCurrentIndex(max(0, box.findData(current)))
    box.setMaxVisibleItems(16)
    return box


class ResultPanel(QWidget):
    closed = Signal()
    target_changed = Signal(str)
    original_toggled = Signal(bool)

    def __init__(self, target_lang: str):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet(theme.PANEL_QSS)
        self.setFixedWidth(WIDTH)

        card = self.card = QWidget(objectName="card")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(card)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 10, 10, 12)
        lay.setSpacing(8)

        top = QHBoxLayout()
        self.status = QLabel("Распознаю и перевожу…", objectName="muted")
        self.lang = language_combo(target_lang)
        self.lang.currentIndexChanged.connect(lambda _: self.target_changed.emit(self.lang.currentData()))
        close = QPushButton("✕", objectName="close")
        close.setToolTip("Закрыть (Esc)")
        close.clicked.connect(self.close)
        top.addWidget(self.status, 1)
        top.addWidget(QLabel("на", objectName="muted"))
        top.addWidget(self.lang)
        top.addWidget(close)
        lay.addLayout(top)

        self.text = QTextEdit(readOnly=True)
        self.text.setFixedHeight(40)
        self.text.document().setDocumentMargin(2)
        self.text.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.text.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        lay.addWidget(self.text)

        bottom = QHBoxLayout()
        self.original = QPushButton("Показать оригинал", checkable=True)
        self.original.toggled.connect(self._on_original)
        self.copy = QPushButton("Копировать перевод")
        self.copy.clicked.connect(self._copy)
        bottom.addWidget(self.original)
        bottom.addStretch(1)
        bottom.addWidget(self.copy)
        lay.addLayout(bottom)

        self._translation = ""
        self._source = ""

    def set_loading(self, text: str = "Распознаю и перевожу…") -> None:
        self.status.setObjectName("muted")
        self.status.setText(text)
        self._restyle()

    def set_result(self, result) -> None:
        self._translation = "\n\n".join(result.translations)
        self._source = "\n\n".join(b.text for b in result.blocks)
        if result.error:
            self.status.setObjectName("error")
            self.status.setText(result.error)
        else:
            self.status.setObjectName("muted")
            self.status.setText(f"Определён: {LANGUAGES.get(result.source, result.source)}" if result.source
                                else "Перевод готов")
            self.status.setToolTip("Зажмите перевод на экране мышкой, чтобы увидеть оригинал")
        self._restyle()
        self.copy.setText("Копировать перевод")
        self.original.setEnabled(bool(result.blocks))
        self.copy.setEnabled(bool(result.blocks))
        self._show_text()

    def _restyle(self):
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    def _show_text(self):
        self.text.setPlainText(self._source if self.original.isChecked() else self._translation)
        self.text.document().setTextWidth(WIDTH - 32)
        doc_h = int(self.text.document().size().height()) + 14
        self.text.setFixedHeight(max(40, min(240, doc_h)))
        self.card.layout().activate()  # сначала внутренняя раскладка, потом внешняя: иначе размер устаревший
        self.layout().activate()
        self.resize(WIDTH, self.sizeHint().height())

    def _on_original(self, on: bool):
        self.original.setText("Показать перевод" if on else "Показать оригинал")
        self._show_text()
        self.original_toggled.emit(on)

    def _copy(self):
        QGuiApplication.clipboard().setText(self.text.toPlainText())
        self.copy.setText("Скопировано")

    def place_near(self, rect: QRect) -> None:
        """Под областью, если хватает места; иначе над ней; иначе внутри у нижнего края."""
        screen = QGuiApplication.screenAt(rect.center()) or QGuiApplication.primaryScreen()
        avail = screen.availableGeometry()
        h = max(self.sizeHint().height(), 200)  # запас: после перевода панель станет выше
        x = min(max(avail.left() + 8, rect.left()), avail.right() - WIDTH - 8)
        if rect.bottom() + 12 + h < avail.bottom():
            y = rect.bottom() + 12
        elif rect.top() - 12 - h > avail.top():
            y = rect.top() - 12 - self.sizeHint().height()
        else:
            y = avail.bottom() - h - 8
        self.move(x, y)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(e)

    def showEvent(self, e):
        super().showEvent(e)
        exclude_from_capture(self)

    def closeEvent(self, e):
        super().closeEvent(e)
        self.closed.emit()
