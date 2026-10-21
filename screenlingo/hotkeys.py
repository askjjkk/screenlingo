"""Глобальные горячие клавиши Windows (RegisterHotKey), работают из любой программы."""
import ctypes
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Signal

MODS = {"alt": 0x1, "ctrl": 0x2, "shift": 0x4, "win": 0x8}
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
NAMED_KEYS = {"space": 0x20, "tab": 0x09, "ins": 0x2D, "insert": 0x2D, "del": 0x2E, "delete": 0x2E,
              "home": 0x24, "end": 0x23, "pgup": 0x21, "pgdown": 0x22, "pause": 0x13, "`": 0xC0, "~": 0xC0}


def parse(seq: str) -> tuple[int, int] | None:
    """«Alt+Q» -> (модификаторы, код клавиши). None, если не поддерживается."""
    parts = [p.strip().lower() for p in seq.split("+") if p.strip()]
    if not parts:
        return None
    mods = 0
    for p in parts[:-1]:
        p = {"control": "ctrl", "meta": "win"}.get(p, p)
        if p not in MODS:
            return None
        mods |= MODS[p]
    key = parts[-1]
    if len(key) == 1 and key.isascii() and key.isalnum():
        vk = ord(key.upper())
    elif key[0] == "f" and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        vk = 0x6F + int(key[1:])
    elif key in NAMED_KEYS:
        vk = NAMED_KEYS[key]
    else:
        return None
    return mods, vk


class _Filter(QAbstractNativeEventFilter):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def nativeEventFilter(self, event_type, message):
        if bytes(event_type) in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY:
                self.callback(int(msg.wParam), int(msg.time))
                return True, 0
        return False, 0


class HotkeyManager(QObject):
    triggered = Signal(str)

    def __init__(self, app):
        super().__init__()
        self._ids: dict[str, int] = {}
        self._next = 1
        self._last = None
        self._filter = _Filter(self._on_hotkey)
        app.installNativeEventFilter(self._filter)

    def register(self, name: str, seq: str) -> bool:
        self.unregister(name)
        parsed = parse(seq)
        if not parsed:
            return False
        hid, self._next = self._next, self._next + 1
        if not ctypes.windll.user32.RegisterHotKey(None, hid, parsed[0] | MOD_NOREPEAT, parsed[1]):
            return False  # клавиша занята другой программой
        self._ids[name] = hid
        return True

    def unregister(self, name: str) -> None:
        hid = self._ids.pop(name, None)
        if hid:
            ctypes.windll.user32.UnregisterHotKey(None, hid)

    def _on_hotkey(self, hid: int, time: int) -> None:
        if (hid, time) == self._last:  # одно сообщение может прийти через оба фильтра
            return
        self._last = (hid, time)
        for name, i in self._ids.items():
            if i == hid:
                self.triggered.emit(name)
