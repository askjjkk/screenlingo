"""Проверка настоящего распознавания на сгенерированной картинке (скачивает модели при первом запуске)."""
import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from screenlingo.ocr import Engine

FONTS = "C:/Windows/Fonts/"


def _render(text, font, size=36):
    img = Image.new("RGB", (800, 80), (25, 25, 30))
    ImageDraw.Draw(img).text((20, 18), text, font=ImageFont.truetype(FONTS + font, size), fill=(235, 235, 235))
    return np.array(img)


@pytest.fixture(scope="module")
def engine():
    return Engine()


@pytest.mark.parametrize("text,font,script", [
    ("Press any key to continue", "arial.ttf", "auto"),
    ("冒険を始めましょう", "msgothic.ttc", "auto"),
    ("Привет, как дела?", "arial.ttf", "eslav"),
    ("새로운 게임 시작", "malgun.ttf", "korean"),
])
def test_recognize(engine, text, font, script):
    lines = engine.recognize(_render(text, font), script)
    got = "".join(l.text for l in lines).replace(" ", "")
    assert got == text.replace(" ", "")


def test_blank_image_gives_nothing(engine):
    assert engine.recognize(np.full((80, 300, 3), 30, np.uint8)) == []


@pytest.mark.parametrize("text,font", [("새로운 게임 시작", "malgun.ttf"), ("Привет, как дела?", "arial.ttf"),
                                       ("Καλημέρα κόσμε", "arial.ttf"), ("สวัสดีชาวโลก", "tahoma.ttf")])
def test_auto_rescues_other_scripts(engine, text, font):
    # в «Авто» корейский и русский тоже должны распознаваться (дораспознавание слабых строк)
    lines = engine.recognize(_render(text, font), "auto")
    assert "".join(l.text for l in lines).replace(" ", "") == text.replace(" ", "")
