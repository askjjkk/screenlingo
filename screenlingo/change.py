"""Определяет, что картинка в «живой зоне» изменилась и успокоилась."""
import numpy as np


def _thumb(img: np.ndarray) -> np.ndarray:
    gray = img[..., :3].mean(axis=2) if img.ndim == 3 else img.astype(float)
    h, w = gray.shape
    sy, sx = max(1, h // 48), max(1, w // 160)
    return gray[: h // sy * sy, : w // sx * sx].reshape(h // sy, sy, w // sx, sx).mean(axis=(1, 3))


class ChangeDetector:
    """feed() возвращает True один раз: когда кадр отличается от уже обработанного
    и при этом не менялся последние stable_frames кадров."""

    def __init__(self, threshold: float = 6.0, stable_frames: int = 1):
        self.threshold = threshold
        self.stable_frames = stable_frames
        self._done = None  # миниатюра последнего обработанного кадра
        self._prev = None
        self._stable = 0

    def _diff(self, a, b) -> float:
        if a is None or a.shape != b.shape:
            return float("inf")
        return float(np.abs(a - b).mean())

    def reset(self) -> None:
        self._done = self._prev = None
        self._stable = 0

    def feed(self, img: np.ndarray) -> bool:
        cur = _thumb(img)
        if self._done is None:
            self._done = self._prev = cur
            return True
        if self._diff(cur, self._prev) < self.threshold:
            self._stable += 1
        else:
            self._stable = 0
        self._prev = cur
        if self._stable >= self.stable_frames and self._diff(cur, self._done) >= self.threshold:
            self._done = cur
            return True
        return False
