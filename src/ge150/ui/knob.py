"""Rotary knob for numeric parameters, and the per-parameter control factory.

Drag up/down (Shift = fine), scroll, arrow keys or Page Up/Down change the value;
double-click types an exact value. Enumerations use a combo box instead.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QKeyEvent, QMouseEvent, QPainter, QPen, QWheelEvent
from PySide6.QtWidgets import (
    QComboBox,
    QInputDialog,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ge150.model.catalog import Param

ACCENT = QColor("#ff8a1f")
TRACK = QColor("#3a3f47")


class Knob(QWidget):
    """Edits one raw word. ``raw_changed(word, raw)`` is emitted on user changes only."""

    raw_changed = Signal(int, int)

    def __init__(self, param: Param, raw: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.param = param
        numeric = param.kind == "number"
        self.minimum = param.to_raw(param.min) if numeric else 0
        self.maximum = param.raw_max if numeric else 0xFFFF
        self.raw = raw
        self._drag: tuple[float, int] | None = None
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.SizeVerCursor)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setToolTip(f"{param.name}: arrastra, usa la rueda o doble clic para escribir")
        self.set_raw(raw)

    @property
    def word(self) -> int:
        return self.param.word

    def sizeHint(self) -> QSize:
        return QSize(92, 112)

    def minimumSizeHint(self) -> QSize:
        return QSize(78, 104)

    # --- value ------------------------------------------------------------------

    def text(self) -> str:
        if self.param.kind != "number":
            return str(self.raw)
        value = self.param.from_raw(self.raw)
        unit = f" {self.param.unit}" if self.param.unit else ""
        return f"{value:.{self.param.decimals}f}{unit}"

    def fraction(self) -> float:
        span = self.maximum - self.minimum
        return (self.raw - self.minimum) / span if span else 0.0

    def set_raw(self, raw: int) -> None:
        """Update the display without emitting ``raw_changed``."""
        self.raw = max(self.minimum, min(self.maximum, raw))
        self.update()

    def setValue(self, raw: int) -> None:
        """Change the value as the user would (emits ``raw_changed``)."""
        raw = max(self.minimum, min(self.maximum, raw))
        if raw != self.raw:
            self.raw = raw
            self.update()
            self.raw_changed.emit(self.param.word, raw)

    def _step(self, steps: int) -> None:
        self.setValue(self.raw + steps)

    # --- events -----------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag = (event.position().y(), self.raw)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag is None:
            return
        start_y, start_raw = self._drag
        span = self.maximum - self.minimum
        fine = event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        pixels = 600.0 if fine else 160.0  # pixels for the whole range
        delta = (start_y - event.position().y()) / pixels * span
        self.setValue(start_raw + round(delta))

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag = None

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        p = self.param
        if p.kind != "number":
            return
        value, ok = QInputDialog.getDouble(self, p.name, f"{p.name} ({p.min} … {p.max})",
                                           p.from_raw(self.raw), p.min, p.max, p.decimals)
        if ok:
            self.setValue(p.to_raw(value))

    def wheelEvent(self, event: QWheelEvent) -> None:
        notches = event.angleDelta().y() // 120
        if notches:
            big = event.modifiers() & Qt.KeyboardModifier.ShiftModifier
            self._step(notches * (10 if big else 1))
        event.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        keys = {Qt.Key.Key_Up: 1, Qt.Key.Key_Right: 1, Qt.Key.Key_Down: -1, Qt.Key.Key_Left: -1,
                Qt.Key.Key_PageUp: 10, Qt.Key.Key_PageDown: -10}
        step = keys.get(Qt.Key(event.key()))
        if step is None:
            super().keyPressEvent(event)
        else:
            self._step(step)

    # --- painting ---------------------------------------------------------------

    def paintEvent(self, event: object) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        size = min(w - 8, h - 30)
        dial = QRectF((w - size) / 2, 4, size, size)
        pen_w = max(4.0, size * 0.08)
        arc = dial.adjusted(pen_w, pen_w, -pen_w, -pen_w)
        p.setPen(QPen(TRACK, pen_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(arc, -45 * 16, 270 * 16)
        accent = ACCENT if self.isEnabled() else TRACK.lighter(130)
        p.setPen(QPen(accent, pen_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(arc, 225 * 16, int(-270 * 16 * self.fraction()))
        centre = arc.center()
        cap = arc.width() * 0.34
        p.setPen(QPen(QColor("#0f1115"), 1))
        p.setBrush(QColor("#262a31"))
        p.drawEllipse(centre, cap, cap)
        angle = math.radians(225 - 270 * self.fraction())
        tip = centre + QPointF(math.cos(angle), -math.sin(angle)) * cap * 0.8
        p.setPen(QPen(QColor("#e8e8e8"), max(2.0, size * 0.03), Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap))
        p.drawLine(centre + (tip - centre) * 0.3, tip)
        font = QFont(self.font())
        font.setPixelSize(max(10, int(size * 0.15)))
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor("#f2f2f2"))
        value_box = QRectF(0, dial.bottom() - size * 0.22, w, size * 0.24)
        p.drawText(value_box, int(Qt.AlignmentFlag.AlignCenter), self.text())
        font.setPixelSize(11)
        font.setBold(False)
        p.setFont(font)
        p.setPen(QColor("#aab2bd") if not self.hasFocus() else ACCENT)
        p.drawText(QRectF(0, dial.bottom() + 4, w, 18), int(Qt.AlignmentFlag.AlignCenter),
                   self.param.name)
        p.end()


class EnumControl(QWidget):
    """Combo box for enumerations, with the same interface as :class:`Knob`."""

    raw_changed = Signal(int, int)

    def __init__(self, param: Param, raw: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.param = param
        self._updating = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 8, 4, 4)
        self.combo = QComboBox()
        self.combo.addItems(list(param.options))
        self.combo.currentIndexChanged.connect(self._changed)
        label = QLabel(param.name)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setObjectName("paramName")
        layout.addStretch(1)
        layout.addWidget(self.combo)
        layout.addWidget(label)
        self.set_raw(raw)

    @property
    def word(self) -> int:
        return self.param.word

    def set_raw(self, raw: int) -> None:
        self._updating = True
        self.combo.setCurrentIndex(raw if 0 <= raw < self.combo.count() else -1)
        self._updating = False

    def setValue(self, raw: int) -> None:
        self.combo.setCurrentIndex(raw)

    def _changed(self, index: int) -> None:
        if not self._updating and index >= 0:
            self.raw_changed.emit(self.param.word, index)


def make_control(param: Param, raw: int) -> Knob | EnumControl:
    return EnumControl(param, raw) if param.kind == "enum" else Knob(param, raw)
