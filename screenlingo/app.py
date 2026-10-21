"""Сборка программы: трей, горячие клавиши, режимы «Снимок» и «Живая зона»."""
import sys
import winreg
from pathlib import Path

from PySide6.QtCore import QLockFile, QObject, QRunnable, QThreadPool
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from . import __version__, settings as settings_mod
from .hotkeys import HotkeyManager
from .languages import LANGUAGES
from .ocr import MODELS_DIR, Engine
from .translate import default_translator
from .ui.icon import make_icon
from .ui.live import LiveZone
from .ui.overlay import TranslationOverlay
from .ui.panel import ResultPanel
from .ui.selector import Selector
from .ui.settings_dialog import SettingsDialog
from .worker import Job

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
QUICK_LANGS = ["ru", "en", "uk", "de", "fr", "es", "ja", "zh-CN", "ko"]


def set_autostart(on: bool) -> None:
    if getattr(sys, "frozen", False):
        cmd = f'"{sys.executable}"'
    else:
        pyw = Path(sys.executable).with_name("pythonw.exe")
        cmd = f'"{pyw}" "{Path(__file__).resolve().parent.parent / "main.py"}"'
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if on:
            winreg.SetValueEx(key, "ScreenLingo", 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(key, "ScreenLingo")
            except FileNotFoundError:
                pass


class _Call(QRunnable):
    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    def run(self):
        try:
            self.fn()
        except Exception:  # noqa: BLE001 — предзагрузка моделей не должна ронять программу
            pass


class App(QObject):
    def __init__(self, qapp: QApplication):
        super().__init__()
        self.qapp = qapp
        self.settings = settings_mod.load()
        self.ocr = Engine()
        self.translator = default_translator()
        self.pool = QThreadPool.globalInstance()
        self.selector = None
        self.snap_views = None  # (overlay, panel)
        self.snap_jobs = []
        self.live = None

        self.tray = QSystemTrayIcon(make_icon(), self)
        self.tray.setToolTip("ScreenLingo")
        self.tray.activated.connect(self._on_tray)
        self._build_menu()
        self.tray.show()

        self.hotkeys = HotkeyManager(qapp)
        self.hotkeys.triggered.connect(lambda name: self.snap() if name == "snap" else self.toggle_live())
        self._register_hotkeys()

        first_run = not any(MODELS_DIR.glob("**/*.onnx")) if MODELS_DIR.exists() else True
        self.tray.showMessage(
            "ScreenLingo запущен",
            f"{self.settings.hotkey_snap}: перевести область\n{self.settings.hotkey_live}: живая зона"
            + ("\nПри первом запуске скачиваются модели распознавания (около 30 МБ)." if first_run else ""),
            make_icon(), 6000)
        self.pool.start(_Call(lambda: self.ocr.preload(self._script())))

    # --- меню и настройки ---

    def _script(self) -> str:
        from .languages import script_for
        return script_for(self.settings.source_lang)

    def _build_menu(self) -> None:
        menu = QMenu()
        menu.addAction(f"Перевести область\t{self.settings.hotkey_snap}", self.snap)
        self.live_action = menu.addAction(f"Живая зона\t{self.settings.hotkey_live}", self.toggle_live)
        self.live_action.setCheckable(True)
        self.live_action.setChecked(self.live is not None)
        langs = menu.addMenu("Переводить на")
        for code in QUICK_LANGS:
            a = langs.addAction(LANGUAGES[code], lambda c=code: self._set_target(c))
            a.setCheckable(True)
            a.setChecked(code == self.settings.target_lang)
        langs.addSeparator()
        langs.addAction("Другой язык…", self.open_settings)
        menu.addSeparator()
        menu.addAction("Настройки", self.open_settings)
        menu.addAction("О программе", self.about)
        menu.addSeparator()
        menu.addAction("Выход", self.quit)
        self.menu = menu
        self.tray.setContextMenu(menu)

    def _on_tray(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.snap()

    def _register_hotkeys(self) -> None:
        failed = [seq for name, seq in (("snap", self.settings.hotkey_snap), ("live", self.settings.hotkey_live))
                  if not self.hotkeys.register(name, seq)]
        if failed:
            self.tray.showMessage("Горячая клавиша занята",
                                  f"{', '.join(failed)} уже использует другая программа. Выберите другую в настройках.",
                                  QSystemTrayIcon.MessageIcon.Warning, 8000)

    def _apply(self, new) -> None:
        old = self.settings
        self.settings = new
        settings_mod.save(new)
        if (old.hotkey_snap, old.hotkey_live) != (new.hotkey_snap, new.hotkey_live):
            self._register_hotkeys()
        if old.autostart != new.autostart:
            try:
                set_autostart(new.autostart)
            except OSError:
                pass
        self._build_menu()
        if self.live and (old.target_lang, old.source_lang) != (new.target_lang, new.source_lang):
            self.live.retranslate()
        if self.live and (old.live_position, old.opacity, old.font_size) != (new.live_position, new.opacity, new.font_size):
            rect = self.live.rect
            self.live.stop()
            self._start_live(rect)

    def _set_target(self, code: str) -> None:
        from dataclasses import replace
        self._apply(replace(self.settings, target_lang=code))

    def open_settings(self) -> None:
        dlg = SettingsDialog(self.settings)
        if dlg.exec():
            self._apply(dlg.result_settings())

    def about(self) -> None:
        box = QMessageBox()
        box.setWindowIcon(make_icon())
        box.setIconPixmap(make_icon().pixmap(64, 64))
        box.setWindowTitle("О программе")
        box.setText(f"<b>ScreenLingo {__version__}</b><br>Перевод текста поверх экрана: игры, программы, видео."
                    "<br><br>Текст распознаётся на вашем компьютере, в интернет уходит только сам текст для перевода."
                    "<br><br><a href='https://github.com/askjjkk/screenlingo'>github.com/askjjkk/screenlingo</a>")
        box.exec()

    def quit(self) -> None:
        if self.live:
            self.live.stop()
        self._close_snap()
        self.tray.hide()
        self.qapp.quit()

    # --- режим «Снимок» ---

    def snap(self) -> None:
        if self.selector:
            return
        self._close_snap()
        self.selector = Selector("Выделите область с текстом. Esc: отмена")
        self.selector.selected.connect(self._on_snap_selected)
        self.selector.cancelled.connect(self._selector_done)

    def _selector_done(self) -> None:
        self.selector = None

    def _close_snap(self) -> None:
        if self.snap_views:
            views, self.snap_views = self.snap_views, None
            for w in views:
                w.close()
                w.deleteLater()

    def _on_snap_selected(self, rect, img, scale) -> None:
        self.selector = None
        overlay = TranslationOverlay()
        overlay.opacity = self.settings.opacity
        overlay.font_px = self.settings.font_size
        overlay.place(rect)
        panel = ResultPanel(self.settings.target_lang)
        panel.place_near(rect)
        panel.closed.connect(self._close_snap)
        panel.original_toggled.connect(overlay.set_original)
        self.snap_views = (overlay, panel)
        overlay.show()
        panel.show()
        panel.activateWindow()
        state = {"blocks": None}

        def run(target, blocks=None):
            panel.set_loading("Распознаю и перевожу…" if blocks is None else "Перевожу…")
            job = Job(self.ocr, self.translator, self.settings.source_lang, target,
                      img=img if blocks is None else None, blocks=blocks)
            job.signals.done.connect(on_done)
            self.snap_jobs = (self.snap_jobs + [job])[-4:]
            self.pool.start(job)

        def on_done(res):
            if not self.snap_views or self.snap_views[0] is not overlay:
                return  # окно уже закрыли
            state["blocks"] = res.blocks or state["blocks"]
            panel.set_result(res)
            overlay.set_result(img, scale, res.blocks, res.translations)
            panel.place_near(rect)

        def on_target(code):
            self._set_target(code)
            if state["blocks"]:
                run(code, state["blocks"])

        panel.target_changed.connect(on_target)
        run(self.settings.target_lang)

    # --- «Живая зона» ---

    def toggle_live(self) -> None:
        if self.live:
            self.live.stop()
            return
        if self.selector:
            return
        self.selector = Selector("Выделите область, которую нужно переводить постоянно (например, субтитры). Esc: отмена")
        self.selector.selected.connect(lambda rect, img, scale: (self._selector_done(), self._start_live(rect)))
        self.selector.cancelled.connect(self._selector_done)

    def _start_live(self, rect) -> None:
        self.live = LiveZone(rect, self.ocr, self.translator, lambda: self.settings, self.pool)
        self.live.stopped.connect(self._on_live_stopped)
        self.live_action.setChecked(True)
        self.tray.setIcon(make_icon(live=True))

    def _on_live_stopped(self) -> None:
        self.live = None
        self.live_action.setChecked(False)
        self.tray.setIcon(make_icon())


def main() -> int:
    qapp = QApplication(sys.argv)
    qapp.setQuitOnLastWindowClosed(False)
    qapp.setApplicationName("ScreenLingo")
    qapp.setWindowIcon(make_icon())
    settings_mod.APP_DIR.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(settings_mod.APP_DIR / "screenlingo.lock"))
    if not lock.tryLock(100):
        QMessageBox.information(None, "ScreenLingo", "ScreenLingo уже запущен: значок рядом с часами.")
        return 0
    app = App(qapp)  # noqa: F841 — держим ссылку до выхода
    return qapp.exec()
