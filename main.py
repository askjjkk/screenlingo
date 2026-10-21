import sys


def selftest(out_path: str) -> int:
    """Проверка собранной программы: распознать и перевести картинку, записать результат в файл."""
    import numpy as np
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QFont, QImage, QPainter
    from PySide6.QtWidgets import QApplication

    from screenlingo.capture import qimage_to_numpy
    from screenlingo.ocr import Engine, group_lines
    from screenlingo.translate import default_translator

    QApplication(sys.argv)
    img = QImage(700, 90, QImage.Format.Format_RGB888)
    img.fill(QColor("#1A1F33"))
    p = QPainter(img)
    p.setPen(QColor("white"))
    p.setFont(QFont("Arial", 26))
    p.drawText(img.rect(), int(Qt.AlignmentFlag.AlignCenter), "Press any key to continue")
    p.end()
    try:
        blocks = group_lines(Engine().recognize(qimage_to_numpy(img)))
        tr, src = default_translator().translate_detect([b.text for b in blocks], "auto", "ru")
        text = f"OK\n{[b.text for b in blocks]}\n{tr}\n{src}\n"
        code = 0 if blocks else 1
    except Exception as e:  # noqa: BLE001
        text, code = f"FAIL\n{e!r}\n", 1
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)
    return code


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--selftest":
        sys.exit(selftest(sys.argv[2]))
    from screenlingo.app import main

    sys.exit(main())
