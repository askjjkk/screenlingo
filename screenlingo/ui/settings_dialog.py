"""Окно настроек."""
from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QKeySequenceEdit,
                               QLabel, QSlider, QSpinBox)

from ..settings import Settings
from .icon import make_icon
from .panel import language_combo


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings):
        super().__init__(None, Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("ScreenLingo: настройки")
        self.setWindowIcon(make_icon())
        self.setMinimumWidth(460)
        self.base = settings
        form = QFormLayout(self)
        form.setVerticalSpacing(10)

        self.target = language_combo(settings.target_lang)
        self.source = language_combo(settings.source_lang, with_auto=True)
        form.addRow("Переводить на", self.target)
        form.addRow("Язык текста на экране", self.source)
        note = QLabel("Оставьте «Определить автоматически»: программа сама поймёт язык и переведёт "
                      "на выбранный. Указывайте язык явно, только если он распознаётся с ошибками.")
        note.setWordWrap(True)
        note.setStyleSheet("color: gray; font-size: 11px;")
        form.addRow(note)

        self.snap = QKeySequenceEdit(QKeySequence(settings.hotkey_snap))
        self.live = QKeySequenceEdit(QKeySequence(settings.hotkey_live))
        form.addRow("Перевести область", self.snap)
        form.addRow("Живая зона вкл/выкл", self.live)

        self.position = QComboBox()
        for code, name in (("over", "Поверх текста"), ("below", "Субтитрами под зоной"), ("above", "Субтитрами над зоной")):
            self.position.addItem(name, code)
        self.position.setCurrentIndex(max(0, self.position.findData(settings.live_position)))
        form.addRow("Перевод в живой зоне", self.position)

        self.font = QSpinBox(minimum=0, maximum=48, suffix=" px", specialValueText="Под размер оригинала")
        self.font.setValue(settings.font_size)
        form.addRow("Размер шрифта", self.font)

        self.opacity = QSlider(Qt.Orientation.Horizontal, minimum=50, maximum=100)
        self.opacity.setValue(int(settings.opacity * 100))
        form.addRow("Непрозрачность плашек", self.opacity)

        self.autostart = QCheckBox("Запускать вместе с Windows")
        self.autostart.setChecked(settings.autostart)
        form.addRow(self.autostart)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Сохранить")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Отмена")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def result_settings(self) -> Settings:
        def seq(edit, fallback):
            text = edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText).split(",")[0].strip()
            return text or fallback
        return replace(
            self.base,
            target_lang=self.target.currentData(), source_lang=self.source.currentData(),
            hotkey_snap=seq(self.snap, self.base.hotkey_snap), hotkey_live=seq(self.live, self.base.hotkey_live),
            live_position=self.position.currentData(), font_size=self.font.value(),
            opacity=self.opacity.value() / 100, autostart=self.autostart.isChecked(),
        )
