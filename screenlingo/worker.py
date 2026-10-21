"""Фоновая задача: распознать и перевести (интерфейс в это время не зависает)."""
from dataclasses import dataclass, field

import numpy as np
from PySide6.QtCore import QObject, QRunnable, Signal

from .languages import script_for
from .ocr import Block, group_lines
from .translate import TranslateError


@dataclass
class Result:
    blocks: list[Block] = field(default_factory=list)
    translations: list[str] = field(default_factory=list)
    error: str | None = None
    source: str | None = None  # язык оригинала, который определил переводчик


class JobSignals(QObject):
    done = Signal(object)


class Job(QRunnable):
    """img=None и blocks!=None: только перевести заново (например, сменили язык)."""

    def __init__(self, ocr, translator, src: str, dst: str, img: np.ndarray | None = None,
                 blocks: list[Block] | None = None):
        super().__init__()
        self.ocr, self.translator = ocr, translator
        self.src, self.dst = src, dst
        self.img, self.blocks = img, blocks
        self.signals = JobSignals()

    def run(self) -> None:
        self._emit(self._work())

    def _work(self) -> Result:
        try:
            blocks = self.blocks
            if blocks is None:
                blocks = group_lines(self.ocr.recognize(self.img, script_for(self.src)))
            if not blocks:
                return Result(error="Текст не найден")
            try:
                tr, source = self.translator.translate_detect([b.text for b in blocks], self.src, self.dst)
                return Result(blocks, tr, source=source)
            except TranslateError:
                return Result(blocks, [b.text for b in blocks], "Нет сети: показан оригинал")
        except Exception as e:  # noqa: BLE001 — любая ошибка должна дойти до пользователя, а не уронить поток
            return Result(error=f"Ошибка: {e}")

    def _emit(self, result: Result) -> None:
        try:
            self.signals.done.emit(result)
        except RuntimeError:
            pass  # окно, ждавшее результат, уже закрыли

