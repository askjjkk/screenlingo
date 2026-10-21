# ScreenLingo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (выбрано: Native, пользователь сказал «делай всё до конца»). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Windows-программа, которая распознаёт текст в области экрана и рисует перевод поверх оригинала (режимы «Снимок» и «Живая зона»).

**Architecture:** Пакет `screenlingo/`: чистая логика (ocr, translate, change, settings, languages) без Qt и тестируется pytest; UI на PySide6 в `screenlingo/ui/`; распознавание и перевод в QThreadPool; горячие клавиши через Win32 RegisterHotKey.

**Tech Stack:** Python 3.14, PySide6 6.12, rapidocr 3.10 + onnxruntime, mss, requests, python-bidi, pytest, PyInstaller.

**Spec:** `docs/superpowers/specs/2026-10-22-screenlingo-design.md`

## Global Constraints
- Только Windows 10/11. Перевод только онлайн: Google gtx → запасной MyMemory.
- OCR: `Global.use_cls = False` (иначе ломается корейский). «Авто» = PP-OCRv6 multi small; письменности = PP-OCRv5 mobile rec (eslav, cyrillic, korean, arabic, devanagari, th, el, ta, te).
- Арабский: результат OCR приходит в визуальном порядке, разворачивать строку.
- Настройки: `%APPDATA%\ScreenLingo\settings.json`. Горячие клавиши по умолчанию Alt+Q (снимок), Alt+W (живая зона).
- Скриншоты не уходят в сеть.

## Review Focus
- Пустая область / нет текста → подсказка «Текст не найден», без падения.
- Нет сети → оригинал с пометкой «нет сети».
- Масштаб экрана 125–150 % и второй монитор → область снимка совпадает с выделением.
- Живая зона: мигающий курсор/анимация не должны вызывать постоянные запросы (порог изменения + стабильность + кэш).
- Горячая клавиша занята → уведомление, программа не падает.

---

### Task 1: Логика без UI
**Files:** `screenlingo/languages.py`, `settings.py`, `change.py`, `translate.py`, `ocr.py`; тесты `tests/test_*.py`.
**Produces:**
- `languages.LANGUAGES: dict[str, str]` (код Google → русское название), `languages.SCRIPTS: dict[str, str]` (письменность → название), `languages.script_for(lang_code) -> str` (`"auto"` если нет особой).
- `settings.Settings` (dataclass: target_lang="ru", source_lang="auto", hotkey_snap="Alt+Q", hotkey_live="Alt+W", font_size=0 (авто), opacity=0.92, live_position="over", autostart=False), `load(path) -> Settings`, `save(settings, path)`; битый JSON → значения по умолчанию.
- `change.ChangeDetector(threshold=6.0, stable_frames=1)`, метод `feed(img: np.ndarray) -> bool` (True один раз, когда картинка изменилась и затем стабилизировалась; первый кадр → True).
- `translate.TranslateError`, `GoogleTranslator`, `MyMemoryTranslator`, `CachedTranslator(inner, maxsize=512)`, `FallbackTranslator(list)`; у всех `translate(texts: list[str], src: str, dst: str) -> list[str]` (длина ответа = длине входа).
- `ocr.Line(text, box: tuple[x,y,w,h], score)`, `ocr.Engine().recognize(img, script="auto") -> list[Line]`, `ocr.group_lines(lines) -> list[Block]` где `Block(text, box, lines)` склеивает строки абзаца (вертикальный зазор < 0.8 высоты строки и перекрытие по x).
Тесты: change (одинаковые кадры → False, изменение → True после стабилизации), кэш (второй вызов без HTTP), fallback (первый падает → второй), Google-парсер на образце ответа, settings (битый файл), group_lines, интеграционный OCR на сгенерированной картинке (en, ja).

### Task 2: Захват экрана и горячие клавиши
**Files:** `screenlingo/capture.py` (`grab(rect: tuple[x,y,w,h] в физических пикселях) -> np.ndarray RGB`), `screenlingo/hotkeys.py` (`HotkeyManager(QObject)`, `register(name, "Alt+Q") -> bool`, сигнал `triggered(str)`, через RegisterHotKey + nativeEventFilter). Процесс DPI-aware (Qt по умолчанию per-monitor v2), перевод логических координат в физические через `screen.devicePixelRatio()`.

### Task 3: Интерфейс
**Files:** `screenlingo/ui/selector.py` (полноэкранное затемнение на все мониторы, сигнал `selected(QRect глобальный логический)`), `ui/overlay.py` (рисует блоки перевода поверх оригинала: фон = медианный цвет вокруг блока, текст контрастный, шрифт подгоняется под рамку), `ui/panel.py` (оригинал/перевод, «Копировать», выбор языка, ✕), `ui/live.py` (рамка зоны + прозрачное для кликов окно перевода, QTimer 500 мс, ChangeDetector, задачи в пул), `ui/settings_dialog.py`, `ui/tray.py`, `screenlingo/worker.py` (QRunnable: OCR+перевод → сигнал результата/ошибки), `screenlingo/app.py` + `main.py`.

### Task 4: Сборка и публикация
PyInstaller spec → `dist/ScreenLingo/ScreenLingo.exe`, модели OCR скачиваются при первом запуске в `%APPDATA%\ScreenLingo\models`. README с гифкой/скриншотами, LICENSE MIT, .gitignore. Проверка: запуск .exe, снимок на реальном окне. GitHub askjjkk/screenlingo + Release; Авито, Kwork, пост в ТГ.
