# Сборка: .venv\Scripts\pyinstaller.exe --noconfirm ScreenLingo.spec
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# из rapidocr берём только конфиги: модели программа скачивает сама при первом запуске
datas = [d for d in collect_data_files("rapidocr") if not d[0].lower().endswith(".onnx")]

SKIP = ("opencv_videoio_ffmpeg", "opengl32sw", "qt6pdf", "qt6quick", "qt6qml", "qt6webengine",
        "qt6virtualkeyboard", "qt6network")

a = Analysis(
    ["main.py"],
    datas=datas,
    hiddenimports=collect_submodules("rapidocr"),
    excludes=["tkinter", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtPdf",
              "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtNetwork", "matplotlib", "scipy"],
)
a.binaries = [b for b in a.binaries if not any(s in b[0].lower() for s in SKIP)]
a.datas = [d for d in a.datas if "translations" not in d[0].lower() or "qtbase_ru" in d[0].lower()]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="ScreenLingo", icon="assets/icon.ico",
          console=False, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name="ScreenLingo", upx=False)
