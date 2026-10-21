"""Сохраняет иконку программы в assets/icon.ico и assets/icon.png (для сборки .exe и README)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PySide6.QtWidgets import QApplication  # noqa: E402

from screenlingo.ui.icon import make_pixmap  # noqa: E402

app = QApplication(sys.argv)
assets = Path(__file__).resolve().parent.parent / "assets"
assets.mkdir(exist_ok=True)
make_pixmap(256).save(str(assets / "icon.png"))
make_pixmap(256).save(str(assets / "icon.ico"))
print("saved", assets)
