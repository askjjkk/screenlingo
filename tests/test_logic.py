import json

import numpy as np
import pytest

from screenlingo import change, languages, settings, translate
from screenlingo.ocr import Line, group_lines


# --- languages ---

def test_languages_has_many_and_main_ones():
    assert len(languages.LANGUAGES) >= 100
    assert languages.LANGUAGES["ru"] == "Русский"
    assert "ja" in languages.LANGUAGES and "ko" in languages.LANGUAGES


def test_script_for():
    assert languages.script_for("ko") == "korean"
    assert languages.script_for("uk") == "eslav"
    assert languages.script_for("ar") == "arabic"
    assert languages.script_for("en") == "auto"
    assert languages.script_for("auto") == "auto"


# --- settings ---

def test_settings_roundtrip(tmp_path):
    p = tmp_path / "s.json"
    s = settings.Settings(target_lang="de", hotkey_snap="Ctrl+Shift+T")
    settings.save(s, p)
    assert settings.load(p) == s


def test_settings_broken_file_gives_defaults(tmp_path):
    p = tmp_path / "s.json"
    p.write_text("{oops", encoding="utf-8")
    assert settings.load(p) == settings.Settings()


def test_settings_unknown_keys_ignored(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"target_lang": "fr", "junk": 1}), encoding="utf-8")
    assert settings.load(p).target_lang == "fr"


# --- change detector ---

def _frame(v):
    return np.full((60, 200, 3), v, dtype=np.uint8)


def test_change_detector_first_frame_then_quiet():
    d = change.ChangeDetector()
    assert d.feed(_frame(10)) is True
    assert d.feed(_frame(10)) is False
    assert d.feed(_frame(10)) is False


def test_change_detector_waits_until_stable():
    d = change.ChangeDetector(stable_frames=1)
    d.feed(_frame(10))
    assert d.feed(_frame(200)) is False  # изменилось, ждём стабилизации
    assert d.feed(_frame(200)) is True   # стабильно -> обрабатываем
    assert d.feed(_frame(200)) is False


def test_change_detector_ignores_tiny_noise():
    d = change.ChangeDetector()
    d.feed(_frame(10))
    noisy = _frame(10)
    noisy[0, 0] = 255  # мигающий пиксель курсора
    assert d.feed(noisy) is False
    assert d.feed(noisy) is False


# --- translate ---

class FakeTranslator:
    def __init__(self, fail=False):
        self.calls = 0
        self.fail = fail

    def translate(self, texts, src, dst):
        self.calls += 1
        if self.fail:
            raise translate.TranslateError("boom")
        return [f"{dst}:{t}" for t in texts]


def test_cache_avoids_second_call():
    inner = FakeTranslator()
    c = translate.CachedTranslator(inner)
    assert c.translate(["a", "b"], "auto", "ru") == ["ru:a", "ru:b"]
    assert c.translate(["b", "a"], "auto", "ru") == ["ru:b", "ru:a"]
    assert inner.calls == 1


def test_cache_only_sends_missing():
    inner = FakeTranslator()
    c = translate.CachedTranslator(inner)
    c.translate(["a"], "auto", "ru")
    assert c.translate(["a", "z"], "auto", "ru") == ["ru:a", "ru:z"]
    assert inner.calls == 2


def test_fallback_uses_second():
    t = translate.FallbackTranslator([FakeTranslator(fail=True), FakeTranslator()])
    assert t.translate(["x"], "auto", "en") == ["en:x"]


def test_fallback_all_fail_raises():
    t = translate.FallbackTranslator([FakeTranslator(fail=True), FakeTranslator(fail=True)])
    with pytest.raises(translate.TranslateError):
        t.translate(["x"], "auto", "en")


def test_google_parse_joins_segments():
    data = [[["Привет. ", "Hello. ", None], ["Мир\n", "World\n", None], ["Да", "Yes", None]], None, "en"]
    assert translate.GoogleTranslator.parse(data) == "Привет. Мир\nДа"


def test_google_batches_and_splits(monkeypatch):
    g = translate.GoogleTranslator()
    sent = []

    def fake_request(text, src, dst):
        sent.append(text)
        return text.upper()

    monkeypatch.setattr(g, "_request", fake_request)
    assert g.translate(["a b", "c"], "auto", "ru") == ["A B", "C"]
    assert len(sent) == 1


def test_google_falls_back_per_item_when_lines_mismatch(monkeypatch):
    g = translate.GoogleTranslator()
    monkeypatch.setattr(g, "_request", lambda text, src, dst: "one line" if "\n" in text else text + "!")
    assert g.translate(["a", "b"], "auto", "ru") == ["a!", "b!"]


def test_google_parse_detected():
    assert translate.GoogleTranslator.parse_detected([[["a", "b"]], None, "ja"]) == "ja"
    assert translate.GoogleTranslator.parse_detected([[["a", "b"]]]) is None


def test_cache_returns_detected_language():
    class Detecting(FakeTranslator):
        last_detected = "ja"

    c = translate.CachedTranslator(Detecting())
    assert c.translate_detect(["x", "y"], "auto", "ru") == (["ru:x", "ru:y"], "ja")
    assert c.translate_detect(["x"], "auto", "ru") == (["ru:x"], "ja")  # из кэша язык тоже помнится


def test_empty_input():
    assert translate.CachedTranslator(FakeTranslator()).translate([], "auto", "ru") == []


# --- group_lines ---

def test_group_lines_merges_paragraph_and_splits_far_lines():
    lines = [
        Line("Hello there,", (10, 10, 200, 20), 0.99),
        Line("general Kenobi", (10, 34, 180, 20), 0.99),
        Line("Settings", (10, 200, 100, 20), 0.99),
    ]
    blocks = group_lines(lines)
    assert [b.text for b in blocks] == ["Hello there, general Kenobi", "Settings"]
    assert blocks[0].box == (10, 10, 200, 44)


def test_group_lines_cjk_no_space():
    lines = [Line("冒険を", (0, 0, 90, 30), 1.0), Line("始めよう", (0, 34, 120, 30), 1.0)]
    assert group_lines(lines)[0].text == "冒険を始めよう"


def test_group_lines_side_by_side_not_merged():
    lines = [Line("Left", (0, 0, 80, 20), 1.0), Line("Right", (400, 24, 80, 20), 1.0)]
    assert len(group_lines(lines)) == 2


def test_group_lines_empty():
    assert group_lines([]) == []
