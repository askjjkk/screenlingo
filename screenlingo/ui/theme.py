"""Цвета и стили интерфейса."""
from PySide6.QtGui import QColor

INK = QColor("#1A1F33")
INK_2 = QColor("#252B45")
PAPER = QColor("#EEF1F8")
MUTED = QColor("#8D95B0")
MARKER = QColor("#FFD24A")  # акцент «маркер-выделитель»: рамка выделения и живой зоны
ERROR = QColor("#FF7A6B")
FONT = "Segoe UI Variable Text"

PANEL_QSS = f"""
QWidget#card {{ background: {INK.name()}; border: 1px solid {INK_2.name()}; border-radius: 12px; }}
QLabel {{ color: {PAPER.name()}; font-family: '{FONT}'; font-size: 13px; }}
QLabel#muted {{ color: {MUTED.name()}; font-size: 12px; }}
QLabel#error {{ color: {ERROR.name()}; font-size: 12px; }}
QTextEdit {{ background: transparent; border: none; color: {PAPER.name()};
             font-family: '{FONT}'; font-size: 15px; selection-background-color: {MARKER.name()};
             selection-color: {INK.name()}; }}
QPushButton {{ background: {INK_2.name()}; color: {PAPER.name()}; border: none; border-radius: 7px;
               padding: 6px 12px; font-family: '{FONT}'; font-size: 13px; }}
QPushButton:hover {{ background: #323A5C; }}
QPushButton:checked {{ background: {MARKER.name()}; color: {INK.name()}; }}
QPushButton:focus {{ outline: none; border: 1px solid {MARKER.name()}; }}
QPushButton#close {{ background: transparent; color: {MUTED.name()}; padding: 4px 8px; font-size: 15px; }}
QPushButton#close:hover {{ color: {PAPER.name()}; }}
QComboBox {{ background: {INK_2.name()}; color: {PAPER.name()}; border: none; border-radius: 7px;
             padding: 5px 10px; font-family: '{FONT}'; font-size: 13px; min-width: 150px; }}
QComboBox QAbstractItemView {{ background: {INK_2.name()}; color: {PAPER.name()};
             selection-background-color: {MARKER.name()}; selection-color: {INK.name()}; }}
"""
