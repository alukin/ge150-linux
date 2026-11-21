"""Microphone placement in front of the speaker, for the CAB models.

Two views side by side:

* **Front**: the speaker as seen from the microphone, with a target where it points.
  Dragging there changes CENTER (distance from the dust cap).
* **Side**: a cut of the cabinet (baffle, cone, dust cap, magnet, grille) and the
  microphone with its pickup cone. Horizontal = DISTANCE from the grille, vertical =
  CENTER. Dragging the microphone changes both.

Changes coming from the pedal are animated. Assumed meaning [?]: CENTER 0 = aimed at the
dust cap, 100 = at the edge of the cone; DISTANCE 0 = touching the grille. Flip
``CENTER_AT_CAP`` if the pedal does the opposite.
"""

from __future__ import annotations

from dataclasses import dataclass

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
    QRadialGradient,
)
from PySide6.QtWidgets import QSizePolicy, QWidget

ACCENT = QColor("#ff8a1f")
MUTED = QColor("#8b95a3")
TEXT = QColor("#e9edf2")
GRID = QColor("#2a3039")
CENTER_AT_CAP = True  # CENTER = 0 aims at the dust cap


@dataclass(frozen=True)
class _Geometry:
    front: QRectF  # square of the front view
    side: QRectF  # rectangle of the side view
    pad: QRectF  # where the microphone tip can go (side view)
    axis: float  # y of the cone axis (side view)
    radius: float  # cone radius (side view)
    grille: float  # x of the grille (side view)


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
        self._dragging: str | None = None  # "front" or "side"
        self._hover = False
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(260)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_anim)
        self.setMinimumSize(360, 240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip("Arrastra el micrófono (perfil) o el punto (frente)")

    def sizeHint(self) -> QSize:
        return QSize(560, 230)

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

    def _geometry(self) -> _Geometry:
        body = QRectF(self.rect()).adjusted(12, 30, -12, -10)
        size = min(body.height() - 20, body.width() * 0.3)
        front = QRectF(body.left(), body.top(), size, size)
        side = QRectF(front.right() + 24, body.top(), body.right() - front.right() - 24,
                      body.height() - 20)
        radius = side.height() * 0.38
        axis = side.top() + side.height() * 0.5
        grille = side.left() + side.width() * 0.2
        mic_len = radius * 1.5
        pad = QRectF(grille + 10, axis - radius, side.right() - grille - 10 - mic_len, radius)
        return _Geometry(front, side, pad, axis, radius, grille)

    @staticmethod
    def _offset(center: float) -> float:
        """0 = on the cone axis, 1 = at the edge, whatever CENTER's direction."""
        return center if CENTER_AT_CAP else 1 - center

    def _tip(self, g: _Geometry) -> QPointF:
        return QPointF(g.pad.left() + g.pad.width() * self.shown.x(),
                       g.axis - g.radius * self._offset(self.shown.y()))

    def _front_target(self, g: _Geometry) -> QPointF:
        c = g.front.center()
        return QPointF(c.x(), c.y() - g.front.width() * 0.36 * self._offset(self.shown.y()))

    # --- mouse ------------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        g = self._geometry()
        self._dragging = "front" if g.front.contains(event.position()) else "side"
        self._anim.stop()
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        self._drag_to(event.position())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging:
            self._drag_to(event.position())
            return
        g = self._geometry()
        tip = self._tip(g)
        near = (abs(event.position().x() - tip.x() - g.radius * 0.6) < g.radius * 0.9
                and abs(event.position().y() - tip.y()) < g.radius * 0.3)
        target = self._front_target(g)
        near = near or (event.position() - target).manhattanLength() < 24
        if near != self._hover:
            self._hover = near
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._dragging = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def leaveEvent(self, event: object) -> None:
        self._hover = False
        self.update()

    def _drag_to(self, pos: QPointF) -> None:
        g = self._geometry()
        if self._dragging == "front":
            c = g.front.center()
            reach = g.front.width() * 0.36
            offset = ((pos.x() - c.x()) ** 2 + (pos.y() - c.y()) ** 2) ** 0.5 / reach
            distance = self.distance
        else:
            offset = (g.axis - pos.y()) / g.radius
            distance = (pos.x() - g.pad.left()) / g.pad.width()
        offset = max(0.0, min(1.0, offset))
        center = offset if CENTER_AT_CAP else 1 - offset
        distance = max(0.0, min(1.0, distance))
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
        g = self._geometry()
        self._paint_header(p)
        self._paint_front(p, g)
        self._paint_rulers(p, g)
        self._paint_cabinet(p, g)
        tip = self._tip(g)
        p.save()
        p.setClipRect(g.side.adjusted(0, -4, 0, 2))  # lobe and cable stay in the view
        self._paint_pickup(p, g, tip)
        self._paint_mic(p, g, tip)
        p.restore()
        p.end()

    def _font(self, p: QPainter, size: int, bold: bool = False) -> None:
        font = QFont(self.font())
        font.setPixelSize(size)
        font.setBold(bold)
        p.setFont(font)

    def _paint_header(self, p: QPainter) -> None:
        top = QRectF(14, 6, self.width() - 28, 20)
        self._font(p, 12, bold=True)
        p.setPen(TEXT)
        p.drawText(top, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                   f"MIC {self.mic_name}".strip())
        center, distance = self.labels
        p.setPen(ACCENT)
        p.drawText(top, int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                   f"CENTER {center}   ·   DISTANCE {distance}")

    def _caption(self, p: QPainter, rect: QRectF, text: str) -> None:
        self._font(p, 10, bold=True)
        p.setPen(MUTED)
        p.drawText(rect, int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop), text)

    def _paint_front(self, p: QPainter, g: _Geometry) -> None:
        f, c = g.front, g.front.center()
        r = f.width() / 2
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#22262d"))
        p.drawRoundedRect(f, 10, 10)
        p.setBrush(QColor("#0f1114"))
        p.drawEllipse(c, r * 0.92, r * 0.92)  # basket
        cone = QRadialGradient(c, r * 0.8)
        cone.setColorAt(0, QColor("#3a3f47"))
        cone.setColorAt(0.85, QColor("#23272d"))
        cone.setColorAt(1, QColor("#16191d"))
        p.setBrush(QBrush(cone))
        p.setPen(QPen(QColor("#4a515b"), 2))
        p.drawEllipse(c, r * 0.8, r * 0.8)  # surround
        p.setPen(QPen(QColor("#2f343c"), 1))
        for ring in (0.62, 0.46):
            p.drawEllipse(c, r * ring, r * ring)
        cap = QRadialGradient(c - QPointF(r * 0.05, r * 0.05), r * 0.2)
        cap.setColorAt(0, QColor("#5b636e"))
        cap.setColorAt(1, QColor("#2b3038"))
        p.setBrush(QBrush(cap))
        p.drawEllipse(c, r * 0.18, r * 0.18)  # dust cap
        p.setPen(QPen(GRID, 1, Qt.PenStyle.DashLine))
        p.drawLine(QPointF(c.x(), f.top() + 6), QPointF(c.x(), f.bottom() - 6))
        p.drawLine(QPointF(f.left() + 6, c.y()), QPointF(f.right() - 6, c.y()))
        target = self._front_target(g)
        closeness = 1 - self.shown.x()
        halo = QRadialGradient(target, 10 + 14 * closeness)
        glow = QColor(ACCENT)
        glow.setAlpha(150 if self._hover else 110)
        halo.setColorAt(0, glow)
        halo.setColorAt(1, QColor(255, 138, 31, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(halo))
        p.drawEllipse(target, 10 + 14 * closeness, 10 + 14 * closeness)
        p.setBrush(ACCENT)
        p.setPen(QPen(QColor("#1a1208"), 1.5))
        p.drawEllipse(target, 5, 5)
        self._caption(p, QRectF(f.left(), f.bottom() + 4, f.width(), 16), "FRENTE")

    def _paint_rulers(self, p: QPainter, g: _Geometry) -> None:
        self._font(p, 9)
        y = g.side.bottom() + 4
        for value in (0, 25, 50, 75, 100):
            x = g.pad.left() + g.pad.width() * value / 100
            p.setPen(QPen(GRID, 1))
            p.drawLine(QPointF(x, g.axis - g.radius * 1.05), QPointF(x, g.side.bottom()))
            p.setPen(MUTED)
            p.drawText(QRectF(x - 20, y, 40, 14), int(Qt.AlignmentFlag.AlignCenter), str(value))
        p.setPen(QPen(GRID, 1, Qt.PenStyle.DashLine))
        p.drawLine(QPointF(g.grille, g.axis), QPointF(g.side.right(), g.axis))
        p.drawLine(QPointF(g.grille, g.axis - g.radius), QPointF(g.side.right(), g.axis - g.radius))
        p.setPen(MUTED)
        left = QRectF(g.grille + 12, 0, 60, 14)
        axis_label, edge_label = ("centro", "borde") if CENTER_AT_CAP else ("borde", "centro")
        p.drawText(left.translated(0, g.axis + g.radius * 0.16), int(Qt.AlignmentFlag.AlignLeft),
                   axis_label)
        p.drawText(left.translated(0, g.axis - g.radius - 15), int(Qt.AlignmentFlag.AlignLeft),
                   edge_label)
        caption = QRectF(g.side.left(), y, g.grille - g.side.left(), 16)
        self._caption(p, caption, "PERFIL")
        p.drawText(QRectF(g.side.right() - 90, y, 90, 14), int(Qt.AlignmentFlag.AlignRight),
                   "DISTANCE →")

    def _paint_cabinet(self, p: QPainter, g: _Geometry) -> None:
        r, axis, grille = g.radius, g.axis, g.grille
        top, bottom = axis - r * 1.25, axis + r * 1.25
        wall = QRectF(g.side.left(), top, grille - g.side.left(), bottom - top)
        wood = QLinearGradient(wall.topLeft(), wall.topRight())
        wood.setColorAt(0, QColor("#1b1e23"))
        wood.setColorAt(1, QColor("#2a2f37"))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(wood))
        p.drawRoundedRect(wall, 4, 4)
        depth = r * 0.62
        magnet = QRectF(grille - depth - r * 0.22, axis - r * 0.2, r * 0.24, r * 0.4)
        p.setBrush(QColor("#3c424b"))
        p.drawRoundedRect(magnet, 3, 3)
        cone = QPainterPath()
        cone.moveTo(grille, axis - r)
        cone.cubicTo(QPointF(grille - depth * 0.45, axis - r * 0.8),
                     QPointF(grille - depth * 0.85, axis - r * 0.35),
                     QPointF(grille - depth, axis - r * 0.22))
        cone.lineTo(grille - depth, axis + r * 0.22)
        cone.cubicTo(QPointF(grille - depth * 0.85, axis + r * 0.35),
                     QPointF(grille - depth * 0.45, axis + r * 0.8),
                     QPointF(grille, axis + r))
        cone.closeSubpath()
        shade = QLinearGradient(QPointF(grille - depth, axis), QPointF(grille, axis))
        shade.setColorAt(0, QColor("#15181c"))
        shade.setColorAt(1, QColor("#2b3038"))
        p.setBrush(QBrush(shade))
        p.setPen(QPen(QColor("#6b7380"), 1.5))
        p.drawPath(cone)
        cap = QRectF(grille - depth - r * 0.02, axis - r * 0.24, r * 0.34, r * 0.48)
        p.setBrush(QColor("#3a404a"))
        p.drawChord(cap, -90 * 16, 180 * 16)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#c9ced3"))
        p.drawRect(QRectF(grille - 2, top + 2, 3, bottom - top - 4))  # baffle edge
        cloth = QRectF(grille + 1, top, 6, bottom - top)
        p.setBrush(QColor("#4b525c"))
        p.drawRect(cloth)
        p.setPen(QPen(QColor("#2b3038"), 1))
        y = cloth.top()
        while y < cloth.bottom():
            p.drawLine(QPointF(cloth.left(), y), QPointF(cloth.right(), y + 3))
            y += 4

    def _paint_pickup(self, p: QPainter, g: _Geometry, tip: QPointF) -> None:
        spread = g.radius * (0.15 + 0.3 * self.shown.x())
        lobe = QPainterPath()
        lobe.moveTo(tip)
        lobe.lineTo(QPointF(g.grille + 8, tip.y() - spread))
        lobe.lineTo(QPointF(g.grille + 8, tip.y() + spread))
        lobe.closeSubpath()
        grad = QLinearGradient(tip, QPointF(g.grille, tip.y()))
        grad.setColorAt(0, QColor(255, 138, 31, 90 if self._hover else 60))
        grad.setColorAt(1, QColor(255, 138, 31, 8))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawPath(lobe)
        p.setPen(QPen(QColor(255, 138, 31, 160), 1.5, Qt.PenStyle.DotLine))
        p.drawLine(tip, QPointF(g.grille + 8, tip.y()))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(ACCENT)
        p.drawEllipse(QPointF(g.grille + 8, tip.y()), 3, 3)

    def _paint_mic(self, p: QPainter, g: _Geometry, tip: QPointF) -> None:
        r = g.radius
        head = QRectF(tip.x(), tip.y() - r * 0.13, r * 0.3, r * 0.26)
        body = QPainterPath()
        body.moveTo(head.right(), tip.y() - r * 0.11)
        body.lineTo(head.right() + r * 0.5, tip.y() - r * 0.08)
        body.lineTo(head.right() + r * 1.05, tip.y() - r * 0.08)
        body.lineTo(head.right() + r * 1.05, tip.y() + r * 0.08)
        body.lineTo(head.right() + r * 0.5, tip.y() + r * 0.08)
        body.lineTo(head.right(), tip.y() + r * 0.11)
        body.closeSubpath()
        end = head.right() + r * 1.05
        cable = QPainterPath()
        cable.moveTo(end + r * 0.12, tip.y())
        cable.cubicTo(QPointF(end + r * 0.4, tip.y()), QPointF(end + r * 0.3, g.side.bottom()),
                      QPointF(end + r * 0.6, g.side.bottom()))
        p.setPen(QPen(QColor("#0d0f12"), max(2.0, r * 0.05)))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(cable)
        metal = QLinearGradient(QPointF(0, tip.y() - r * 0.1), QPointF(0, tip.y() + r * 0.1))
        metal.setColorAt(0, QColor("#5d636b"))
        metal.setColorAt(0.45, QColor("#2a2e34"))
        metal.setColorAt(1, QColor("#121417"))
        p.setPen(QPen(ACCENT if self._hover or self._dragging else QColor("#0d0f12"), 1.2))
        p.setBrush(QBrush(metal))
        p.drawPath(body)
        p.setBrush(QColor("#8f969e"))
        p.drawRoundedRect(QRectF(end, tip.y() - r * 0.06, r * 0.12, r * 0.12), 2, 2)  # XLR
        mesh = QLinearGradient(head.topLeft(), head.bottomLeft())
        mesh.setColorAt(0, QColor("#d3d7db"))
        mesh.setColorAt(1, QColor("#7d838a"))
        p.setBrush(QBrush(mesh))
        p.drawRoundedRect(head, r * 0.08, r * 0.08)
        p.setPen(QPen(QColor("#5a6067"), 1))
        for i in range(1, 5):
            x = head.left() + head.width() * i / 5
            p.drawLine(QPointF(x, head.top() + 2), QPointF(x, head.bottom() - 2))
        for i in range(1, 3):
            y = head.top() + head.height() * i / 3
            p.drawLine(QPointF(head.left() + 2, y), QPointF(head.right() - 2, y))
