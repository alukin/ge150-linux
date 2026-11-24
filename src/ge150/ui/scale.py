"""Size of the interface on large screens.

The editor is laid out for about 1920 x 1080 logical pixels. On a 4K screen at 100 % (or a
1440p one) everything would look tiny, so ``ge150`` scales the whole interface with Qt's
``QT_SCALE_FACTOR``: automatically from the screen size, or by the user's choice (*Ver →
Tamaño de la interfaz*). Qt reads that variable only when the application starts, so the
process restarts itself once with it set. A desktop that already scales (4K at 200 %)
reports 1920 x 1080 logical pixels and gets no extra scaling.
"""

from __future__ import annotations

import math
import os
import sys

from PySide6.QtCore import QSettings
from PySide6.QtGui import QGuiApplication

KEY = "ui/scale"
AUTO = "auto"
CHOICES = (AUTO, "1", "1.25", "1.5", "1.75", "2", "2.5")
BASE = (1920, 1080)
MAX = 2.5
#: Set when ``ge150`` itself chose QT_SCALE_FACTOR (so a restart can change it again).
MARK = "GE150_UI_SCALE"
RESTART = 64  # exit code of the event loop that asks main() to restart


def auto_factor(width: int, height: int) -> float:
    """Scale for a screen of ``width`` x ``height`` logical pixels, in 0.25 steps."""
    ratio = min(width / BASE[0], height / BASE[1])
    steps = math.floor(ratio * 4 + 1e-6) / 4
    return 1.0 if steps < 1.25 else min(steps, MAX)


def preference() -> str:
    value = str(QSettings("ge150", "editor").value(KEY, AUTO))
    return value if value in CHOICES else AUTO


def set_preference(value: str) -> None:
    QSettings("ge150", "editor").setValue(KEY, value if value in CHOICES else AUTO)


def wanted(app: QGuiApplication) -> float:
    """The factor to use given the preference and the primary screen."""
    choice = preference()
    if choice != AUTO:
        return float(choice)
    screen = app.primaryScreen()
    if screen is None:
        return 1.0
    size = screen.availableGeometry()
    return auto_factor(size.width(), size.height())


def apply(app: QGuiApplication) -> None:
    """Restart with QT_SCALE_FACTOR when the wanted scale is not the current one.

    Does nothing when the user set QT_SCALE_FACTOR themselves, or once ``ge150`` has set
    it (no restart loop)."""
    if MARK in os.environ or "QT_SCALE_FACTOR" in os.environ:
        return
    factor = wanted(app)
    if abs(factor - 1.0) < 0.01:
        return
    _exec(factor)


def restart() -> None:
    """Start the editor again (after the user changed the interface size)."""
    if os.environ.get(MARK):
        os.environ.pop("QT_SCALE_FACTOR", None)
        os.environ.pop(MARK, None)
    os.execv(sys.executable, [sys.executable, *sys.orig_argv[1:]])


def _exec(factor: float) -> None:
    os.environ["QT_SCALE_FACTOR"] = f"{factor:g}"
    os.environ[MARK] = f"{factor:g}"
    os.execv(sys.executable, [sys.executable, *sys.orig_argv[1:]])
