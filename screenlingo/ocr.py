"""Распознавание текста на картинке (RapidOCR, работает локально)."""
import threading
from dataclasses import dataclass, field

import numpy as np

from .settings import APP_DIR

MODELS_DIR = APP_DIR / "models"
RESCUE_SCRIPTS = ("korean", "eslav")  # чем «Авто» дораспознаёт строки, которые не прочитались


@dataclass
class Line:
    text: str
    box: tuple[int, int, int, int]  # x, y, w, h в пикселях картинки
    score: float


@dataclass
class Block:
    text: str
    box: tuple[int, int, int, int]
    lines: list[Line] = field(default_factory=list)


def _is_cjk(ch: str) -> bool:
    o = ord(ch)
    return 0x3000 <= o <= 0x9FFF or 0xAC00 <= o <= 0xD7AF or 0xF900 <= o <= 0xFAFF or 0xFF00 <= o <= 0xFFEF


def _join(a: str, b: str) -> str:
    if not a or not b:
        return a + b
    if _is_cjk(a[-1]) or _is_cjk(b[0]):
        return a + b
    if a.endswith("-") and len(a) > 1 and a[-2].isalpha():
        return a[:-1] + b  # перенос слова
    return a + " " + b


def group_lines(lines: list[Line]) -> list[Block]:
    """Склеивает строки одного абзаца в блок (переводить удобнее целыми фразами)."""
    blocks: list[Block] = []
    for ln in sorted(lines, key=lambda l: (l.box[1], l.box[0])):
        x, y, w, h = ln.box
        target = None
        for b in reversed(blocks):
            bx, by, bw, bh = b.box
            last = b.lines[-1].box
            gap = y - (by + bh)
            overlap = min(x + w, bx + bw) - max(x, bx)
            similar = 0.6 < h / max(1, last[3]) < 1.6
            if -0.5 * h < gap < 0.8 * h and overlap > 0 and similar:
                target = b
                break
        if target is None:
            blocks.append(Block(ln.text, ln.box, [ln]))
        else:
            bx, by, bw, bh = target.box
            nx, ny = min(bx, x), min(by, y)
            target.box = (nx, ny, max(bx + bw, x + w) - nx, max(by + bh, y + h) - ny)
            target.text = _join(target.text, ln.text)
            target.lines.append(ln)
    return blocks


def _looks_bad(line: Line) -> bool:
    x, y, w, h = line.box
    expected = w / (1.1 * max(h, 1))  # сколько символов примерно влезает в рамку
    return line.score < 0.9 or len(line.text.strip()) < 0.45 * expected


class Engine:
    """Ленивая загрузка моделей: модель письменности создаётся при первом использовании."""

    def __init__(self):
        self._engines = {}
        self._lock = threading.Lock()

    def _engine(self, script: str):
        if script not in self._engines:
            from rapidocr import RapidOCR
            from rapidocr.utils.typings import LangRec, ModelType, OCRVersion

            MODELS_DIR.mkdir(parents=True, exist_ok=True)
            params = {"Global.log_level": "error", "Global.use_cls": False,
                      "Global.model_root_dir": str(MODELS_DIR)}
            if script != "auto":
                params.update({"Rec.ocr_version": OCRVersion.PPOCRV5, "Rec.lang_type": LangRec(script),
                               "Rec.model_type": ModelType.MOBILE})
            self._engines[script] = RapidOCR(params=params)
        return self._engines[script]

    def preload(self, script: str = "auto") -> None:
        with self._lock:
            self._engine(script)

    def recognize(self, img: np.ndarray, script: str = "auto") -> list[Line]:
        with self._lock:
            if script == "auto":
                lines = self._recognize_auto(img)
            else:
                res = self._engine(script)(img, use_det=True, use_cls=False, use_rec=True)
                if res.boxes is None or res.txts is None:
                    return []
                lines = [Line(t.strip(), _rect(p), float(s)) for p, t, s in zip(res.boxes, res.txts, res.scores)]
                if script == "arabic":
                    for ln in lines:
                        ln.text = ln.text[::-1]  # модель отдаёт справа-налево в обратном порядке
            return [ln for ln in lines if ln.text and ln.score >= 0.5]

    def _recognize_auto(self, img: np.ndarray) -> list[Line]:
        # строки ищем один раз, читаем каждую отдельно: так видно и те, что модель не прочла
        # флаги передаём всегда все три: RapidOCR запоминает их с прошлого вызова
        det = self._engine("auto")(img, use_det=True, use_cls=False, use_rec=False)
        if det.boxes is None:
            return []
        lines = []
        for poly in det.boxes:
            box = _rect(poly)
            crop = _crop(img, box)
            line = self._read(crop, "auto", box) or Line("", box, 0.0)
            if _looks_bad(line):
                for alt in RESCUE_SCRIPTS:
                    cand = self._read(crop, alt, box)
                    if cand and cand.score > line.score + 0.05:
                        line = cand
            lines.append(line)
        return lines

    def _read(self, crop: np.ndarray, script: str, box) -> Line | None:
        r = self._engine(script)(crop, use_det=False, use_cls=False, use_rec=True)
        if not r.txts or not r.txts[0].strip():
            return None
        return Line(r.txts[0].strip(), box, float(r.scores[0]))


def _rect(poly) -> tuple[int, int, int, int]:
    xs, ys = poly[:, 0], poly[:, 1]
    x0, y0 = int(max(0, xs.min())), int(max(0, ys.min()))
    return x0, y0, int(xs.max()) - x0, int(ys.max()) - y0


def _crop(img: np.ndarray, box) -> np.ndarray:
    x, y, w, h = box
    pad = max(2, h // 10)
    return img[max(0, y - pad): y + h + pad, max(0, x - pad): x + w + pad]
