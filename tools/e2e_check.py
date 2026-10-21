"""Сквозная проверка без мыши: окно «игры» на экране -> снимок и живая зона -> картинки результата.
Запуск: python tools/e2e_check.py out_dir"""
import os
import sys
import time
from pathlib import Path

os.environ["SCREENLINGO_SHOW_IN_CAPTURE"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL.ImageQt import ImageQt  # noqa: E402
from PySide6.QtCore import QRect, Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

from render_demo import scene  # noqa: E402
from screenlingo.app import App  # noqa: E402
from screenlingo.capture import grab_rect  # noqa: E402

out = Path(sys.argv[1] if len(sys.argv) > 1 else "e2e")
out.mkdir(parents=True, exist_ok=True)
qapp = QApplication(sys.argv)
qapp.setQuitOnLastWindowClosed(False)


def pump(seconds):
    end = time.time() + seconds
    while time.time() < end:
        qapp.processEvents()
        time.sleep(0.02)


def wait_for(cond, timeout=60):
    end = time.time() + timeout
    while time.time() < end and not cond():
        pump(0.1)
    return cond()


app = App(qapp)
print("hotkeys registered:", dict(app.hotkeys._ids))

# окно «игры»
game = QLabel(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
img = scene()
game.setPixmap(QPixmap.fromImage(ImageQt(img)))
game.move(100, 100)
game.show()
pump(1.0)
geo = game.geometry()

# 1) снимок: как будто пользователь выделил диалог внизу
rect = QRect(geo.x() + 30, geo.y() + 320, 940, 220)
arr, scale = grab_rect(rect)
app._on_snap_selected(rect, arr, scale)
overlay, panel = app.snap_views
ok = wait_for(lambda: bool(overlay.translations), 90)
pump(0.5)
print("snap ok:", ok, overlay.translations, "| panel:", panel.status.text())
QGuiApplication.primaryScreen().grabWindow(0, geo.x() - 20, geo.y() - 20, geo.width() + 460, geo.height() + 320) \
    .save(str(out / "snap_screen.png"))
panel.grab().save(str(out / "snap_panel.png"))
app._close_snap()
pump(0.5)

# 2) живая зона над правым верхним окошком квеста, потом текст меняется.
# Здесь окна перевода скрыты от снимков, как у пользователя, иначе зона переводила бы сама себя.
os.environ["SCREENLINGO_SHOW_IN_CAPTURE"] = "0"
zone = QRect(geo.x() + 630, geo.y() + 50, 340, 160)
app._start_live(zone)
ok = wait_for(lambda: bool(getattr(app.live.view, "translations", None)), 60)
first = list(app.live.view.translations)
print("live 1:", ok, first, "| tab:", app.live.frame.status)

from PIL import ImageDraw, ImageFont  # noqa: E402
d = ImageDraw.Draw(img)
d.rounded_rectangle((640, 60, 960, 200), 12, fill=(20, 24, 40))
f = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 26)
d.text((665, 80), "새로운 임무: 등대로 가라", font=f, fill=(255, 220, 120))
d.text((665, 130), "보상: 금화 500개", font=f, fill=(230, 230, 240))
game.setPixmap(QPixmap.fromImage(ImageQt(img)))
ok = wait_for(lambda: app.live.view.translations != first, 60)
pump(0.5)
print("live 2:", ok, app.live.view.translations, "| tab:", app.live.frame.status)
shot = QGuiApplication.primaryScreen().grabWindow(0, geo.x() + 560, geo.y() + 10, 440, 260)
from PySide6.QtGui import QPainter  # noqa: E402
p = QPainter(shot)
for w in (app.live.frame, app.live.view):  # дорисовываем наши окна поверх снимка экрана
    p.drawPixmap(w.x() - (geo.x() + 560), w.y() - (geo.y() + 10), w.grab())
p.end()
shot.save(str(out / "live_screen.png"))

started = []
real_start = app.live.pool.start
app.live.pool = type("P", (), {"start": lambda self, job: (started.append(job), real_start(job))})()
pump(3)  # текст не меняется -> новых распознаваний быть не должно
print("idle jobs started:", len(started))
app.live.stop()
app.quit()
