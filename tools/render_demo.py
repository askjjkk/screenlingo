"""Рисует «до/после» на сгенерированной картинке игры: для проверки оверлея и для README.
Запуск: python tools/render_demo.py out_dir"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from PySide6.QtCore import QRect
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from screenlingo.ocr import Engine, group_lines  # noqa: E402
from screenlingo.translate import default_translator  # noqa: E402
from screenlingo.ui.overlay import MARGIN, TranslationOverlay  # noqa: E402
from screenlingo.ui.panel import ResultPanel  # noqa: E402
from screenlingo.worker import Result  # noqa: E402


def scene() -> Image.Image:
    W, H = 1000, 560
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):  # «небо» игры
        c = int(40 + 60 * y / H)
        d.line([(0, y), (W, y)], fill=(c // 2, c // 2 + 10, c + 40))
    d.rounded_rectangle((40, 330, 960, 520), 18, fill=(236, 226, 200), outline=(120, 90, 60), width=4)
    f = ImageFont.truetype("C:/Windows/Fonts/georgia.ttf", 30)
    fb = ImageFont.truetype("C:/Windows/Fonts/georgiab.ttf", 28)
    d.text((70, 345), "Old Captain", font=fb, fill=(120, 60, 30))
    d.text((70, 395), "The storm is coming. We must reach the harbor", font=f, fill=(40, 30, 20))
    d.text((70, 437), "before nightfall, or the ship will be lost.", font=f, fill=(40, 30, 20))
    d.rounded_rectangle((640, 60, 960, 200), 12, fill=(20, 24, 40))
    fj = ImageFont.truetype("C:/Windows/Fonts/msgothic.ttc", 26)
    d.text((665, 80), "クエスト：灯台へ行け", font=fj, fill=(255, 220, 120))
    d.text((665, 130), "報酬：金貨 300枚", font=fj, fill=(230, 230, 240))
    return img


def main(out: Path):
    app = QApplication.instance() or QApplication(sys.argv)
    out.mkdir(parents=True, exist_ok=True)
    base = scene()
    base.save(out / "before.png")
    arr = np.array(base)
    blocks = group_lines(Engine().recognize(arr))
    tr = default_translator().translate([b.text for b in blocks], "auto", "ru")
    for b, t in zip(blocks, tr):
        print(repr(b.text), "->", repr(t))

    ov = TranslationOverlay()
    ov.place(QRect(0, 0, base.width, base.height))
    ov.set_result(arr, 1.0, blocks, tr)
    layer = ov.grab()
    qimg = QImage(str(out / "before.png"))
    p = QPainter(qimg)
    p.drawPixmap(-MARGIN, -MARGIN, layer)
    p.end()
    qimg.save(str(out / "after.png"))

    panel = ResultPanel("ru")
    panel.show()  # размеры панели считаются только у показанного окна
    panel.set_result(Result(blocks, tr, source="en"))
    app.processEvents()
    panel.grab().save(str(out / "panel.png"))
    panel.hide()

    # анимация для README: оригинал -> перевод -> оригинал
    before = Image.open(out / "before.png").convert("RGB")
    after = Image.open(out / "after.png").convert("RGB")
    frames, durations = [], []
    for k in range(0, 11):
        frames.append(Image.blend(before, after, k / 10))
        durations.append(1400 if k in (0, 10) else 60)
    for k in range(9, 0, -1):
        frames.append(Image.blend(before, after, k / 10))
        durations.append(60)
    small = [f.resize((800, 448), Image.LANCZOS) for f in frames]
    small[0].save(out / "demo.gif", save_all=True, append_images=small[1:], duration=durations, loop=0,
                  optimize=True)


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "demo"))
