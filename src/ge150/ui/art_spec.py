"""Pedals drawn from a per-unit recipe (``art`` in ``gear.json``), laid out like the original.

Coordinates are fractions of the drawing (0..1, origin top left). A recipe has:

* ``aspect`` (width / height) and ``shape``: ``box`` (default), ``round`` or ``wedge``;
* ``parts``: ``{"rect"|"ellipse"|"poly"|"line": ..., "fill", "stroke", "width", "radius"}``
  painted in order (panels, stripes, treadles, windows...);
* ``knobs``: ``{"param", "label", "at", "r", "style", "label_at", "label_colour"}``; ``param``
  is the GE150 parameter the knob shows (``GAIN``, ``TONE``...), ``style`` black, cream,
  chrome, chicken, skirt, gold or knurled;
* ``switches`` (``round``, ``rect``, ``treadle``), ``leds``, ``toggles``, ``jacks`` (``y``);
* ``texts``: ``{"text", "box", "colour", "style", "stretch"}``; ``$MODEL`` is the model name.

No brand or product name is drawn: the model name of the GE150 takes the place of the
original's name, in the same style.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)

from ge150.model.gear import Gear
from ge150.ui import amp_art


class _Frame:
    """Maps recipe fractions to the drawing rectangle."""

    def __init__(self, r: QRectF) -> None:
        self.r = r

    def pt(self, xy: list[float]) -> QPointF:
        return QPointF(self.r.left() + xy[0] * self.r.width(),
                       self.r.top() + xy[1] * self.r.height())

    def rect(self, box: list[float]) -> QRectF:
        x, y, w, h = box
        return QRectF(self.r.left() + x * self.r.width(), self.r.top() + y * self.r.height(),
                      w * self.r.width(), h * self.r.height())

    def len(self, value: float) -> float:
        return value * self.r.width()


def paint_spec(p: QPainter, r: QRectF, g: Gear, title: str, knobs: list[Any], on: bool,
               detail: bool) -> None:
    from ge150.ui import gear_art as ga  # the primitives (gear_art imports this module lazily)

    spec: dict[str, Any] = g.art
    f = _Frame(r)
    body = amp_art.colour(g.body)
    jack_y = spec.get("jacks")
    if jack_y is not None:
        ga._jacks(p, r, f.pt([0, jack_y]).y(), f.len(0.12))
    shape = spec.get("shape", "box")
    if shape == "round":
        grad = QLinearGradient(r.topLeft(), r.bottomLeft())
        grad.setColorAt(0, body.lighter(135))
        grad.setColorAt(1, body.darker(140))
        p.setPen(QPen(body.darker(190), max(1.0, f.len(0.01))))
        p.setBrush(QBrush(grad))
        p.drawEllipse(r)
    else:
        ga._gradient_body(p, r, body, f.len(spec.get("radius", 0.06)))
    for part in spec.get("parts", []):
        _part(p, f, part, body)
    for text in spec.get("texts", []):
        _text(p, f, text, title)
    values = {k.name.upper(): k for k in knobs}
    for knob in spec.get("knobs", []):
        _knob(p, f, knob, values, detail, ga)
    for toggle in spec.get("toggles", []):
        _toggle(p, f, toggle)
    for led in spec.get("leds", []):
        _led(p, f.pt(led["at"]), f.len(led.get("r", 0.025)), on, led.get("colour", "red"), ga)
    for switch in spec.get("switches", []):
        _switch(p, f, switch, ga)


# --- parts --------------------------------------------------------------------------------


METALS = ("chrome", "gold", "copper", "steel")


def _brush(value: str, area: QRectF) -> QBrush:
    if value in METALS:
        return amp_art.metal_brush(area, value)
    return QBrush(QColor(value))


def _part(p: QPainter, f: _Frame, part: dict[str, Any], body: QColor) -> None:
    fill = part.get("fill", "")
    stroke = part.get("stroke", "")
    width = f.len(part.get("width", 0.006))
    if stroke in METALS:
        p.setPen(QPen(amp_art.metal_brush(f.r, stroke), max(0.6, width), Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    else:
        p.setPen(QPen(QColor(stroke), max(0.6, width)) if stroke else Qt.PenStyle.NoPen)
    if "rect" in part:
        area = f.rect(part["rect"])
        p.setBrush(_brush(fill, area) if fill else Qt.BrushStyle.NoBrush)
        radius = f.len(part.get("radius", 0))
        if part.get("shade"):  # slight gradient, for raised plates
            grad = QLinearGradient(area.topLeft(), area.bottomLeft())
            base = QColor(fill)
            grad.setColorAt(0, base.lighter(118))
            grad.setColorAt(1, base.darker(118))
            p.setBrush(QBrush(grad))
        p.drawRoundedRect(area, radius, radius)
    elif "ellipse" in part:
        cx, cy, rx, ry = part["ellipse"]
        centre = f.pt([cx, cy])
        area = QRectF(centre.x() - f.len(rx), centre.y() - f.len(ry), f.len(rx) * 2,
                      f.len(ry) * 2)
        p.setBrush(_brush(fill, area) if fill else Qt.BrushStyle.NoBrush)
        p.drawEllipse(area)
    elif "poly" in part:
        path = QPainterPath(f.pt(part["poly"][0]))
        for xy in part["poly"][1:]:
            path.lineTo(f.pt(xy))
        path.closeSubpath()
        p.setBrush(_brush(fill, path.boundingRect()) if fill else Qt.BrushStyle.NoBrush)
        p.drawPath(path)
    elif "line" in part:
        x1, y1, x2, y2 = part["line"]
        if stroke not in METALS:
            p.setPen(QPen(QColor(stroke or "#000"), max(0.6, width), Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap))
        p.drawLine(f.pt([x1, y1]), f.pt([x2, y2]))
    elif "polyline" in part:  # open path (steel rails, U bars)
        path = QPainterPath(f.pt(part["polyline"][0]))
        for xy in part["polyline"][1:]:
            path.lineTo(f.pt(xy))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
    if part.get("brushed") and "rect" in part:  # brushed metal: fine horizontal streaks
        area = f.rect(part["rect"])
        p.save()
        clip = QPainterPath()
        clip.addRoundedRect(area, f.len(part.get("radius", 0)), f.len(part.get("radius", 0)))
        p.setClipPath(clip)
        p.setPen(QPen(QColor(255, 255, 255, 22), 1))
        y = area.top()
        step = max(1.5, area.height() / 90)
        while y < area.bottom():
            p.drawLine(QPointF(area.left(), y), QPointF(area.right(), y))
            y += step
        p.restore()


def _text(p: QPainter, f: _Frame, spec: dict[str, Any], title: str) -> None:
    text = str(spec.get("text", "$MODEL")).replace("$MODEL", title)
    if not text:
        return
    area = f.rect(spec["box"])
    style = spec.get("style", "block")
    font = QFont()
    if style in ("script", "serif"):
        font.setFamilies(amp_art.SCRIPT_FONTS)
        font.setItalic(style == "script")
        font.setWeight(QFont.Weight.Bold)
    else:
        font.setFamilies(amp_art.BLOCK_FONTS)
        font.setWeight(QFont.Weight.Light if style == "light" else QFont.Weight.Black)
        font.setItalic(style == "italic")
    if spec.get("upper", True) and style not in ("script", "light"):
        text = text.upper()
    font.setPixelSize(100)
    path = QPainterPath()
    path.addText(0, 0, font, text)
    box = path.boundingRect()
    if box.isEmpty():
        return
    stretch = spec.get("stretch", 1.0)  # < 1 narrows the letters (condensed faces)
    sx = area.width() * 0.96 / (box.width() * stretch)
    sy = area.height() * 0.9 / box.height()
    scale = min(sx, sy)
    p.save()
    p.translate(area.center())
    p.scale(scale * stretch, scale)
    p.translate(-box.center())
    outline = spec.get("outline")
    p.setPen(QPen(QColor(outline), 6) if outline else Qt.PenStyle.NoPen)
    p.setBrush(_brush(spec.get("colour", "#f2f2f2"), box))
    p.drawPath(path)
    p.restore()


def _knob(p: QPainter, f: _Frame, spec: dict[str, Any], values: dict[str, Any], detail: bool,
          ga: Any) -> None:
    centre = f.pt(spec["at"])
    radius = f.len(spec.get("r", 0.1))
    state = None
    param = str(spec.get("param", "")).upper()
    if param:
        state = values.get(param) or next((v for k, v in values.items() if k.startswith(param)),
                                          None)
    fraction = state.fraction if state is not None else spec.get("value", 0.5)
    style = spec.get("style", "black")
    if style in ("black", "cream", "red", "silver", "yellow"):
        colour = {"black": "#141414", "cream": "#efe6cf", "red": "#b3201e",
                  "silver": "#cfd3d6", "yellow": "#f1d23a"}[style]
        ga._knob(p, centre, radius, QColor(colour), fraction, "", QColor("#fff"), False)
    else:
        amp_art.amp_knob(p, centre, radius, style, QColor("#151515"), fraction)
    label = spec.get("label", "")
    if detail and label:
        colour = QColor(spec.get("label_colour", "#f2f2f2"))
        size = min(max(radius * 0.3, 5.0), 11.0)
        above = spec.get("label_at") == "above"
        y = centre.y() - radius * 1.25 - size if above else centre.y() + radius * 1.12
        box = QRectF(centre.x() - radius * 2.4, y, radius * 4.8, size * 1.3)
        _label(p, box, label, colour, size)


def _label(p: QPainter, box: QRectF, text: str, colour: QColor, size: float) -> None:
    font = QFont()
    font.setFamilies(amp_art.BLOCK_FONTS)
    font.setBold(True)
    font.setPixelSize(max(4, int(size)))
    while font.pixelSize() > 4:
        p.setFont(font)
        if p.fontMetrics().horizontalAdvance(text) <= box.width():
            break
        font.setPixelSize(font.pixelSize() - 1)
    p.setPen(colour)
    p.drawText(box, int(Qt.AlignmentFlag.AlignCenter), text)


def _led(p: QPainter, centre: QPointF, radius: float, on: bool, colour: str, ga: Any) -> None:
    if colour == "red":
        ga._led(p, centre, radius, on)
        return
    lit = {"green": "#39d353", "white": "#e8f4ff", "blue": "#4aa3ff"}.get(colour, "#ff2d2d")
    tone = QColor(lit) if on else QColor(lit).darker(300)
    if on:
        glow = QRadialGradient(centre, radius * 3)
        glow.setColorAt(0, QColor(tone.red(), tone.green(), tone.blue(), 150))
        glow.setColorAt(1, QColor(tone.red(), tone.green(), tone.blue(), 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(glow))
        p.drawEllipse(centre, radius * 3, radius * 3)
    p.setBrush(tone)
    p.setPen(QPen(QColor("#1a1a1a"), radius * 0.3))
    p.drawEllipse(centre, radius, radius)


def _toggle(p: QPainter, f: _Frame, spec: dict[str, Any]) -> None:
    centre = f.pt(spec["at"])
    size = f.len(spec.get("r", 0.035))
    p.setPen(QPen(QColor("#111"), max(0.6, size * 0.1)))
    p.setBrush(amp_art.metal_brush(QRectF(centre.x() - size, centre.y() - size, size * 2,
                                          size * 2), "chrome"))
    p.drawEllipse(centre, size, size)
    p.setPen(QPen(QColor("#e8eaec"), max(1.0, size * 0.45), Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap))
    p.drawLine(centre, centre + QPointF(0, -size * 1.6))


def _switch(p: QPainter, f: _Frame, spec: dict[str, Any], ga: Any) -> None:
    kind = spec.get("type", "round")
    centre = f.pt(spec["at"])
    if kind == "round":
        ga._footswitch(p, centre, f.len(spec.get("r", 0.1)))
        return
    w, h = spec.get("size", [0.2, 0.08])
    area = QRectF(centre.x() - f.len(w) / 2, centre.y() - f.len(h) / 2, f.len(w), f.len(h))
    if kind == "rect":  # metal push button (Ibanez, DigiTech...)
        p.setPen(QPen(QColor("#3a3d40"), max(0.8, f.len(0.006))))
        p.setBrush(amp_art.metal_brush(area, "chrome"))
        p.drawRoundedRect(area, f.len(0.012), f.len(0.012))
        p.setPen(QPen(QColor(0, 0, 0, 60), max(0.6, f.len(0.004))))
        inner = area.adjusted(area.width() * 0.12, area.height() * 0.22, -area.width() * 0.12,
                              -area.height() * 0.22)
        p.drawRoundedRect(inner, f.len(0.008), f.len(0.008))
    elif kind == "treadle":  # rubber pad with ribs
        p.setPen(QPen(QColor("#050505"), max(0.8, f.len(0.006))))
        p.setBrush(QColor("#1d1d1d"))
        p.drawRoundedRect(area, f.len(0.03), f.len(0.03))
        p.setPen(QPen(QColor("#333"), max(0.6, f.len(0.004))))
        for i in range(1, 9):
            y = area.top() + area.height() * i / 9
            p.drawLine(QPointF(area.left() + area.width() * 0.08, y),
                       QPointF(area.right() - area.width() * 0.08, y))
