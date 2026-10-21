"""Настройки программы в JSON-файле."""
import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path

APP_DIR = Path(os.environ.get("APPDATA", Path.home())) / "ScreenLingo"
SETTINGS_PATH = APP_DIR / "settings.json"


@dataclass
class Settings:
    target_lang: str = "ru"
    source_lang: str = "auto"
    hotkey_snap: str = "Alt+Q"
    hotkey_live: str = "Alt+W"
    font_size: int = 0  # 0 = подбирать под размер оригинала
    opacity: float = 1.0
    live_position: str = "over"  # over / below / above
    autostart: bool = False


def load(path: Path = SETTINGS_PATH) -> Settings:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        known = {f.name for f in fields(Settings)}
        return Settings(**{k: v for k, v in data.items() if k in known})
    except (OSError, ValueError, TypeError):
        return Settings()


def save(settings: Settings, path: Path = SETTINGS_PATH) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2), encoding="utf-8")
