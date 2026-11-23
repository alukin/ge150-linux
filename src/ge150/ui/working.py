"""«Claude está trabajando...» under the AI chat while an agent works (like the AgentHub
plugin for Obsidian): a spinning arc, dots that appear one by one, the step it is on and the
time it has taken."""

from __future__ import annotations

import html
import time

from PySide6.QtCore import QRectF, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from ge150.ui.theme import ACCENT, BORDER, MUTED

DOT_MS = 400  # one more dot every 400 ms: . .. ... then start over
SHOW_SECONDS_AFTER = 3


class Spinner(QWidget):
    """A ring with an orange arc that turns."""

    def __init__(self, size: int = 14, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.angle = 0.0
        self.anim = QVariantAnimation(self)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(360.0)
        self.anim.setDuration(900)
        self.anim.setLoopCount(-1)
        self.anim.valueChanged.connect(self._turn)

    def _turn(self, value: object) -> None:
        self.angle = float(value)  # type: ignore[arg-type]
        self.update()

    def start(self) -> None:
        self.anim.start()

    def stop(self) -> None:
        self.anim.stop()

    def paintEvent(self, _: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        box = QRectF(1.5, 1.5, self.width() - 3, self.height() - 3)
        pen = QPen(QColor(BORDER), 2)
        painter.setPen(pen)
        painter.drawEllipse(box)
        pen.setColor(QColor(ACCENT))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        # Qt angles: 1/16 degree, counter-clockwise from 3 o'clock.
        painter.drawArc(box, int(-self.angle * 16), 100 * 16)


class WorkingIndicator(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(8)
        self.spinner = Spinner()
        self.label = QLabel()
        self.label.setObjectName("workingText")
        self.label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(self.spinner)
        layout.addWidget(self.label, 1)
        self.text, self.step = "", ""
        self.dots = 0
        self.started = 0.0
        self.timer = QTimer(self)
        self.timer.setInterval(DOT_MS)
        self.timer.timeout.connect(self._tick)
        self.hide()

    @property
    def running(self) -> bool:
        return self.timer.isActive()

    def start(self, text: str) -> None:
        self.text, self.step = text.rstrip(".… "), ""
        self.dots, self.started = 0, time.monotonic()
        self.spinner.start()
        self.timer.start()
        self.show()
        self._render()

    def set_text(self, text: str) -> None:
        self.text = text.rstrip(".… ")
        self._render()

    def set_step(self, step: str) -> None:
        self.step = step
        self._render()

    def stop(self) -> None:
        self.timer.stop()
        self.spinner.stop()
        self.hide()

    def _tick(self) -> None:
        self.dots = (self.dots + 1) % 4
        self._render()

    def _render(self) -> None:
        # Hidden dots keep their place, so the text after them does not jump.
        dots = "." * self.dots + f"<span style='color:transparent'>{'.' * (3 - self.dots)}</span>"
        extra = []
        if self.step:
            extra.append(html.escape(self.step))
        seconds = int(time.monotonic() - self.started)
        if seconds >= SHOW_SECONDS_AFTER:
            extra.append(f"{seconds} s")
        tail = "".join(f"<span style='color:{MUTED}'>  ·  {e}</span>" for e in extra)
        self.label.setText(f"{html.escape(self.text)}{dots}{tail}")
