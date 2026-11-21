"""Microphone placement in front of the speaker, for the CAB models.

Side view: the speaker cone on the left, the microphone in front of it. Horizontal axis
= DISTANCE from the grille, vertical axis = CENTER (offset from the dust cap towards
the edge of the cone). Dragging the microphone changes both parameters; changes coming
from the pedal are animated.

Assumed meaning [?]: CENTER 0 = aimed at the dust cap, 100 = at the edge of the cone;
DISTANCE 0 = touching the grille. Flip ``CENTER_AT_CAP`` if the pedal does the opposite.
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, QSize, Qt, QVariantAnimation, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import QSizePolicy, QWidget

ACCENT = QColor("#ff8a1f")
CENTER_AT_CAP = True  # CENTER = 0 aims at the dust cap


class MicPlacement(QWidget):
    """``moved(center, distance)`` (0..1 each) is emitted while the user drags."""

    moved = Signal(float, float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.center = 0.0  # target values, 0..1
        self.distance = 0.0
        self.shown = QPointF(0.0, 0.0)  # animated (distance, center)
        self.mic_name = ""
        self.labels = ("", "")
        self._dragging = False
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_anim)
        self.setMinimumSize(260, 170)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip("Arrastra el micrófono: horizontal = DISTANCE, vertical = CENTER")

    def sizeHint(self) -> QSize:
        return QSize(420, 200)

    # --- values -----------------------------------------------------------------

    def set_values(self, center: float, distance: float, animate: bool = True) -> None:
        self.center = max(0.0, min(1.0, center))
        self.distance = max(0.0, min(1.0, distance))
        target = QPointF(self.distance, self.center)
        if animate and not self._dragging and self.isVisible():
            self._anim.stop()
            self._anim.setStartValue(self.shown)
            self._anim.setEndValue(target)
            self._anim.start()
        else:
            self.shown = target
            self.update()

    def set_labels(self, mic: str, center: str, distance: str) -> None:
        self.mic_name, self.labels = mic, (center, distance)
        self.update()

    def _on_anim(self, value: object) -> None:
        if isinstance(value, QPointF):
            self.shown = value
            self.update()

    # --- geometry ---------------------------------------------------------------

    def _layout(self) -> tuple[QRectF, float, float, float]:
        """Pad rectangle, cone axis y, cone radius and the x of the grille."""
        r = QRectF(self.rect()).adjusted(10, 26, -10, -12)
        radius = r.height() * 0.42
        axis = r.center().y()
        grille = r.left() + r.width() * 0.2
        pad = QRectF(grille + 14, axis - radius, r.right() - grille - 30, radius * 2)
        return pad, axis, radius, grille

    def _mic_point(self) -> QPointF:
        pad, axis, radius, _ = self._layout()
        offset = self.shown.y() if CENTER_AT_CAP else 1 - self.shown.y()
        return QPointF(pad.left() + pad.width() * self.shown.x(), axis - radius * offset)

    def _values_at(self, pos: QPointF) -> tuple[float, float]:
        pad, axis, radius, _ = self._layout()
        distance = (pos.x() - pad.left()) / pad.width()
        offset = (axis - pos.y()) / radius
        offset = max(0.0, min(1.0, offset))
        center = offset if CENTER_AT_CAP else 1 - offset
        return center, max(0.0, min(1.0, distance))

    # --- mouse ------------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._anim.stop()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self._drag_to(event.position())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging:
            self._drag_to(event.position())

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._dragging = False
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def _drag_to(self, pos: QPointF) -> None:
        center, distance = self._values_at(pos)
        self.center, self.distance = center, distance
        self.shown = QPointF(distance, center)
        self.update()
        self.moved.emit(center, distance)

    # --- painting ---------------------------------------------------------------

    def paintEvent(self, event: object) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#15181d"))
        p.drawRoundedRect(QRectF(self.rect()), 12, 12)
        pad, axis, radius, grille = self._layout()
        self._paint_speaker(p, axis, radius, grille)
        self._paint_guides(p, pad, axis, radius)
        self._paint_mic(p, self._mic_point(), axis)
        self._paint_labels(p)
        p.end()

    def _paint_speaker(self, p: QPainter, axis: float, radius: float, grille: float) -> None:
        cab = QRectF(grille - radius * 0.9, axis - radius * 1.25, radius * 0.9, radius * 2.5)
        grad = QLinearGradient(cab.topLeft(), cab.topRight())
        grad.setColorAt(0, QColor("#2a2f37"))
        grad.setColorAt(1, QColor("#3a404a"))
        p.setBrush(QBrush(grad))
        p.drawRect(cab)
        cone = QPainterPath()
        back = grille - radius * 0.62
        cone.moveTo(grille, axis - radius)
        cone.lineTo(back, axis - radius * 0.28)
        cone.lineTo(back, axis + radius * 0.28)
        cone.lineTo(grille, axis + radius)
        cone.closeSubpath()
        p.setBrush(QColor("#1b1e23"))
        p.setPen(QPen(QColor("#8b95a3"), 1.5))
        p.drawPath(cone)
        cap = QRectF(back + radius * 0.02, axis - radius * 0.26, radius * 0.3, radius * 0.52)
        p.setBrush(QColor("#2b3038"))
        p.drawChord(cap, -90 * 16, 180 * 16)
        p.setPen(QPen(QColor("#c9ced3"), 3))
        p.drawLine(QPointF(grille, axis - radius * 1.2), QPointF(grille, axis + radius * 1.2))

    def _paint_guides(self, p: QPainter, pad: QRectF, axis: float, radius: float) -> None:
        p.setPen(QPen(QColor("#323843"), 1, Qt.PenStyle.DashLine))
        p.drawLine(QPointF(pad.left() - 14, axis), QPointF(pad.right(), axis))
        p.drawLine(QPointF(pad.left() - 14, axis - radius), QPointF(pad.right(), axis - radius))

    def _paint_mic(self, p: QPainter, tip: QPointF, axis: float) -> None:
        _, _, radius, grille = self._layout()
        p.setPen(QPen(QColor(255, 138, 31, 120), 1.5, Qt.PenStyle.DotLine))
        p.drawLine(tip, QPointF(grille, tip.y()))
        length, body = radius * 1.1, radius * 0.16
        head = QRectF(tip.x(), tip.y() - body * 0.75, body * 1.4, body * 1.5)
        p.setPen(QPen(QColor("#0d0f12"), 1))
        p.setBrush(QColor("#a7adb4"))
        p.drawRoundedRect(head, body * 0.4, body * 0.4)
        p.setPen(QPen(QColor("#6b7178"), 1))
        for i in range(1, 4):
            x = head.left() + head.width() * i / 4
            p.drawLine(QPointF(x, head.top() + 2), QPointF(x, head.bottom() - 2))
        shaft = QRectF(head.right(), tip.y() - body * 0.45, length, body * 0.9)
        grad = QLinearGradient(shaft.topLeft(), shaft.bottomLeft())
        grad.setColorAt(0, QColor("#4a4f57"))
        grad.setColorAt(0.5, QColor("#22262c"))
        grad.setColorAt(1, QColor("#121417"))
        p.setPen(QPen(QColor("#0d0f12"), 1))
        p.setBrush(QBrush(grad))
        p.drawRoundedRect(shaft, body * 0.3, body * 0.3)
        p.setBrush(ACCENT)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(head.left() - 3, tip.y()), 3.5, 3.5)

    def _paint_labels(self, p: QPainter) -> None:
        font = QFont(self.font())
        font.setPixelSize(12)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor("#e9edf2"))
        top = QRectF(12, 4, self.width() - 24, 20)
        p.drawText(top, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                   f"MIC {self.mic_name}".strip())
        center, distance = self.labels
        p.setPen(QColor("#8b95a3"))
        p.drawText(top, int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                   f"CENTER {center}   ·   DISTANCE {distance}")
