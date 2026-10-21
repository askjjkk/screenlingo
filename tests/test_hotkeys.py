from screenlingo.hotkeys import parse


def test_parse_basic():
    assert parse("Alt+Q") == (0x1, ord("Q"))
    assert parse("Ctrl+Shift+T") == (0x2 | 0x4, ord("T"))
    assert parse("Meta+F2") == (0x8, 0x71)
    assert parse("Alt+1") == (0x1, ord("1"))


def test_parse_rejects_unknown():
    assert parse("") is None
    assert parse("Hyper+Q") is None
    assert parse("Alt+Ё") is None
