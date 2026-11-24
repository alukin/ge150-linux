"""Vector drawings of the gear behind each model, used when there is no photo.

Each ``Gear.kind`` has its own silhouette (stompbox, BOSS-style, round fuzz, wah, amp
head, combo, cabinet, ...) painted with the gear's colours. Knobs show the current
parameter values of the preset.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)

from ge150.model.gear import Gear
from ge150.ui import amp_art


@dataclass(frozen=True)
class KnobState:
    name: str
    fraction: float  # 0..1
    text: str = ""


SPEAKER_ASPECT = {"1x10": 1.05, "1x12": 1.12, "2x12": 1.5, "4x10": 1.0, "4x12": 1.0}
KIND_ASPECT = {"stomp": 0.6, "boss": 0.58, "round": 0.86, "bigbox": 0.8, "micro": 0.5,
               "wah": 0.62, "eq": 0.5, "head": 2.2, "acoustic": 0.72}


def preferred_aspect(gear: Gear) -> float:
    """Width / height of the drawing."""
    if gear.art.get("aspect"):
        return float(gear.art["aspect"])  # type: ignore[arg-type]
    if gear.kind in ("combo", "cab"):
        base = SPEAKER_ASPECT.get(gear.speakers, 1.2)
        return base * (0.92 if gear.kind == "combo" else 1.0)
    return KIND_ASPECT.get(gear.kind, 0.6)


def render_pixmap(gear: Gear, size: QSize, title: str, knobs: list[KnobState], on: bool,
                  ratio: float = 1.0) -> QPixmap:
    pixmap = QPixmap(QSize(int(size.width() * ratio), int(size.height() * ratio)))
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    paint_gear(painter, QRectF(0, 0, size.width(), size.height()), gear, title, knobs, on)
    painter.end()
    return pixmap


def fit(rect: QRectF, aspect: float) -> QRectF:
    """Largest rectangle of ``aspect`` centred in ``rect``."""
    w = min(rect.width(), rect.height() * aspect)
    h = w / aspect
    return QRectF(rect.center().x() - w / 2, rect.center().y() - h / 2, w, h)


def paint_gear(p: QPainter, area: QRectF, gear: Gear, title: str, knobs: list[KnobState],
               on: bool) -> None:
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    r = fit(area.adjusted(2, 2, -2, -2), preferred_aspect(gear))
    detail = r.width() >= 150 and r.height() >= 120
    if gear.art:  # a recipe laid out like the original unit
        from ge150.ui.art_spec import paint_spec

        paint_spec(p, r, gear, title, knobs, on, detail)
    else:
        _PAINTERS.get(gear.kind, _stomp)(p, r, gear, title, knobs, on, detail)
    if not on:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(10, 12, 16, 120))
        p.drawRoundedRect(r, r.width() * 0.05, r.width() * 0.05)
    p.restore()


# --- primitives -------------------------------------------------------------------------


def _c(value: str, fallback: str = "#444") -> QColor:
    colour = QColor(value or fallback)
    return colour if colour.isValid() else QColor(fallback)


def _gradient_body(p: QPainter, r: QRectF, colour: QColor, radius: float) -> None:
    grad = QLinearGradient(r.topLeft(), r.bottomLeft())
    grad.setColorAt(0, colour.lighter(125))
    grad.setColorAt(0.5, colour)
    grad.setColorAt(1, colour.darker(135))
    p.setPen(QPen(colour.darker(170), max(1.0, r.width() * 0.008)))
    p.setBrush(QBrush(grad))
    p.drawRoundedRect(r, radius, radius)


def _text(p: QPainter, r: QRectF, text: str, colour: QColor, size: float, bold: bool = True,
          align: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignCenter) -> None:
    if not text or size < 4:
        return
    font = QFont(p.font())
    font.setBold(bold)
    font.setPixelSize(max(5, int(size)))
    metrics_width = r.width() * 0.96
    while font.pixelSize() > 5:
        p.setFont(font)
        if p.fontMetrics().horizontalAdvance(text) <= metrics_width:
            break
        font.setPixelSize(font.pixelSize() - 1)
    p.setFont(font)
    p.setPen(colour)
    p.drawText(r, int(align), text)


def _knob(p: QPainter, centre: QPointF, radius: float, colour: QColor, fraction: float,
          label: str, label_colour: QColor, detail: bool) -> None:
    shadow = QColor(0, 0, 0, 90)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(shadow)
    p.drawEllipse(centre + QPointF(radius * 0.08, radius * 0.12), radius, radius)
    grad = QRadialGradient(centre - QPointF(radius * 0.35, radius * 0.4), radius * 1.6)
    grad.setColorAt(0, colour.lighter(175))
    grad.setColorAt(0.45, colour)
    grad.setColorAt(1, colour.darker(160))
    p.setBrush(QBrush(grad))
    p.setPen(QPen(colour.darker(200), max(0.8, radius * 0.06)))
    p.drawEllipse(centre, radius, radius)
    angle = math.radians(225 - 270 * max(0.0, min(1.0, fraction)))
    tip = centre + QPointF(math.cos(angle) * radius * 0.82, -math.sin(angle) * radius * 0.82)
    pointer = QColor("#f5f5f5") if colour.lightness() < 140 else QColor("#141414")
    p.setPen(QPen(pointer, max(1.2, radius * 0.16), Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap))
    p.drawLine(centre + (tip - centre) * 0.25, tip)
    if detail and label:
        box = QRectF(centre.x() - radius * 2.2, centre.y() + radius * 1.12, radius * 4.4,
                     radius * 0.9)
        _text(p, box, label, label_colour, radius * 0.62, bold=True)


def _knob_row(p: QPainter, r: QRectF, y: float, knobs: list[KnobState], colour: QColor,
              label: QColor, detail: bool, max_radius: float, count: int | None = None) -> None:
    states = knobs or [KnobState("", 0.5)] * (count or 2)
    n = len(states)
    step = r.width() / n
    radius = min(step * 0.32, max_radius)
    for i, state in enumerate(states):
        centre = QPointF(r.left() + step * (i + 0.5), y)
        _knob(p, centre, radius, colour, state.fraction, state.name, label, detail)


def _led(p: QPainter, centre: QPointF, radius: float, on: bool) -> None:
    colour = QColor("#ff2d2d") if on else QColor("#4a1414")
    if on:
        glow = QRadialGradient(centre, radius * 3)
        glow.setColorAt(0, QColor(255, 60, 60, 160))
        glow.setColorAt(1, QColor(255, 60, 60, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(glow))
        p.drawEllipse(centre, radius * 3, radius * 3)
    p.setBrush(colour)
    p.setPen(QPen(QColor("#1a1a1a"), radius * 0.3))
    p.drawEllipse(centre, radius, radius)


def _footswitch(p: QPainter, centre: QPointF, radius: float) -> None:
    grad = QRadialGradient(centre - QPointF(radius * 0.3, radius * 0.3), radius * 1.4)
    grad.setColorAt(0, QColor("#ffffff"))
    grad.setColorAt(0.5, QColor("#b9bec4"))
    grad.setColorAt(1, QColor("#5f656b"))
    p.setPen(QPen(QColor("#3a3d40"), radius * 0.08))
    p.setBrush(QBrush(grad))
    p.drawEllipse(centre, radius, radius)
    p.setBrush(QColor(0, 0, 0, 40))
    p.drawEllipse(centre, radius * 0.62, radius * 0.62)


def _knob_colour(knob: str, body: QColor) -> QColor:
    """The gear's knob colour, or silver when it would vanish against the body."""
    colour = _c(knob, "#151515")
    if abs(colour.lightness() - body.lightness()) < 45:
        return QColor("#cfd3d6") if body.lightness() < 128 else QColor("#1a1a1a")
    return colour


def _contrast(colour: QColor) -> QColor:
    return QColor("#f2f2f2") if colour.lightness() < 140 else QColor("#161616")


# --- silhouettes ----------------------------------------------------------------------


def _bigbox(p: QPainter, r: QRectF, g: Gear, title: str, knobs: list[KnobState], on: bool,
            detail: bool) -> None:
    body, text = _c(g.body), _c(g.text)
    knob = _knob_colour(g.knob, body)
    _gradient_body(p, r, body, r.width() * 0.04)
    w, h = r.width(), r.height()
    _knob_row(p, r.adjusted(w * 0.1, 0, -w * 0.1, 0), r.top() + h * 0.18, knobs[:3], knob,
              _contrast(body), detail, w * 0.08, 3)
    _text(p, QRectF(r.left(), r.top() + h * 0.36, w, h * 0.2), g.logo_text or title, text, h * 0.14)
    _led(p, QPointF(r.left() + w * 0.82, r.top() + h * 0.62), w * 0.025, on)
    _footswitch(p, QPointF(r.center().x(), r.top() + h * 0.78), w * 0.08)


def _boss(p: QPainter, r: QRectF, g: Gear, title: str, knobs: list[KnobState], on: bool,
          detail: bool) -> None:
    """BOSS compact: knobs and check LED on top, the name, then the big pedal plate with
    the BOSS logo at its foot."""
    body, text = _c(g.body), _c(g.text)
    knob = _knob_colour(g.knob, body)
    w, h = r.width(), r.height()
    _jacks(p, r, r.top() + h * 0.5, w * 0.12)
    _gradient_body(p, r, body, w * 0.05)
    top = QRectF(r.left() + w * 0.04, r.top() + h * 0.03, w * 0.92, h * 0.3)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#0e0e0e"))
    p.drawRoundedRect(top, w * 0.03, w * 0.03)
    _knob_row(p, top.adjusted(w * 0.02, 0, -w * 0.02, 0), r.top() + h * 0.14, knobs[:4], knob,
              QColor("#e8e8e8"), detail, w * 0.1)
    _led(p, QPointF(r.center().x(), r.top() + h * 0.045), w * 0.025, on)
    _name(p, QRectF(r.left() + w * 0.12, r.top() + h * 0.35, w * 0.76, h * 0.09),
          g.logo_text or title, text)
    plate = QRectF(r.left() + w * 0.05, r.top() + h * 0.47, w * 0.9, h * 0.5)
    _gradient_body(p, plate, body.darker(112), w * 0.04)
    p.setPen(QPen(body.darker(160), max(1.0, w * 0.006)))
    for k in range(1, 6):
        y = plate.top() + plate.height() * k / 9
        p.drawLine(QPointF(plate.left() + w * 0.06, y), QPointF(plate.right() - w * 0.06, y))
    p.setPen(QPen(body.lighter(140), max(0.8, w * 0.006)))  # the logo plate, left blank
    p.setBrush(body.darker(125))
    p.drawRoundedRect(QRectF(plate.left() + w * 0.2, plate.bottom() - h * 0.13, w * 0.5, h * 0.07),
                      w * 0.01, w * 0.01)

def _round(p: QPainter, r: QRectF, g: Gear, title: str, knobs: list[KnobState], on: bool,
           detail: bool) -> None:
    body, text = _c(g.body), _c(g.text)
    knob = _knob_colour(g.knob, body)
    w, h = r.width(), r.height()
    disc = QRectF(r.left(), r.top(), w, h)
    grad = QRadialGradient(disc.center() - QPointF(w * 0.2, h * 0.25), w * 0.8)
    grad.setColorAt(0, body.lighter(140))
    grad.setColorAt(1, body.darker(140))
    p.setPen(QPen(body.darker(180), max(1.0, w * 0.01)))
    p.setBrush(QBrush(grad))
    p.drawEllipse(disc)
    _knob_row(p, r.adjusted(w * 0.25, 0, -w * 0.25, 0), r.top() + h * 0.28, knobs[:2], knob,
              text, detail, w * 0.09, 2)
    _text(p, QRectF(r.left(), r.top() + h * 0.46, w, h * 0.14), g.logo_text or title, text, h * 0.1)
    _footswitch(p, QPointF(r.center().x(), r.top() + h * 0.72), w * 0.09)
    _led(p, QPointF(r.left() + w * 0.72, r.top() + h * 0.62), w * 0.025, on)


def _acoustic(p: QPainter, r: QRectF, g: Gear, title: str, knobs: list[KnobState], on: bool,
              detail: bool) -> None:
    wood, text = _c(g.body), _c(g.text)
    w, h = r.width(), r.height()
    neck = QRectF(r.center().x() - w * 0.06, r.top(), w * 0.12, h * 0.32)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#3a2412"))
    p.drawRect(neck)
    p.setPen(QPen(QColor("#d8d8d8"), max(1.0, w * 0.006)))
    for i in range(1, 6):
        y = neck.top() + neck.height() * i / 6
        p.drawLine(QPointF(neck.left(), y), QPointF(neck.right(), y))
    body = QPainterPath()
    upper = QRectF(r.left() + w * 0.16, r.top() + h * 0.26, w * 0.68, h * 0.36)
    lower = QRectF(r.left() + w * 0.04, r.top() + h * 0.44, w * 0.92, h * 0.54)
    body.addEllipse(upper)
    body.addEllipse(lower)
    body.setFillRule(Qt.FillRule.WindingFill)
    grad = QRadialGradient(lower.center() - QPointF(w * 0.1, h * 0.1), w * 0.7)
    grad.setColorAt(0, wood.lighter(135))
    grad.setColorAt(1, wood.darker(135))
    p.setPen(QPen(wood.darker(200), max(1.5, w * 0.012)))
    p.setBrush(QBrush(grad))
    p.drawPath(body.simplified())
    hole = QPointF(r.center().x(), upper.bottom() - upper.height() * 0.12)
    p.setPen(QPen(QColor("#e6d3a8"), max(1.0, w * 0.01)))
    p.setBrush(QColor("#140c06"))
    p.drawEllipse(hole, w * 0.11, w * 0.11)
    bridge = QRectF(r.center().x() - w * 0.16, lower.center().y() + h * 0.08, w * 0.32, h * 0.04)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#1d1209"))
    p.drawRoundedRect(bridge, 3, 3)
    _text(p, QRectF(r.left(), lower.bottom() - h * 0.16, w, h * 0.08), title, text, w * 0.08)


def _jacks(p: QPainter, r: QRectF, y: float, size: float, top: bool = False) -> None:
    """Input/output jacks sticking out of the sides (and DC jack on top)."""
    p.setPen(QPen(QColor("#111"), max(0.6, size * 0.08)))
    p.setBrush(QColor("#2b2b2b"))
    for x in (r.left() - size * 0.55, r.right() - size * 0.45):
        p.drawRoundedRect(QRectF(x, y - size * 0.5, size, size), size * 0.15, size * 0.15)
    if top:
        p.drawRoundedRect(QRectF(r.center().x() - size * 0.45, r.top() - size * 0.5, size * 0.9,
                                 size * 0.8), size * 0.15, size * 0.15)


def _name(p: QPainter, r: QRectF, title: str, colour: QColor, italic: bool = False) -> None:
    """Pedal name in a heavy face (italic like Mooer's micro labels)."""
    if not title:
        return
    font = QFont(p.font())
    font.setWeight(QFont.Weight.Black)
    font.setItalic(italic)
    font.setPixelSize(100)
    path = QPainterPath()
    path.addText(0, 0, font, title)
    box = path.boundingRect()
    scale = min(r.width() * 0.92 / box.width(), r.height() * 0.85 / box.height())
    if scale <= 0:
        return
    p.save()
    p.translate(r.center())
    p.scale(scale, scale)
    p.translate(-box.center())
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(colour)
    p.drawPath(path)
    p.restore()


_MAIN = ("TIME", "RATE", "SPEED", "DECAY", "DRIVE", "GAIN", "THRES", "THRESHOLD", "SENS", "MIX",
         "LEVEL")


def _main_first(knobs: list[KnobState]) -> list[KnobState]:
    """The control a micro pedal puts on its big knob, then the others."""
    for word in _MAIN:
        for i, k in enumerate(knobs):
            if k.name.upper().startswith(word):
                return [k, *knobs[:i], *knobs[i + 1:]]
    return list(knobs)


def _micro(p: QPainter, r: QRectF, g: Gear, title: str, knobs: list[KnobState], on: bool,
           detail: bool) -> None:
    """Mooer micro pedal: DC IN on top, two small knobs, one big knob, LED, italic name, big
    footswitch and the MOOER wordmark, jacks on the sides."""
    w, h = r.width(), r.height()
    body = r.adjusted(w * 0.07, h * 0.02, -w * 0.07, 0)
    bw = body.width()
    colour, text = _c(g.body), _c(g.text)
    _jacks(p, body, body.top() + h * 0.42, bw * 0.16, top=True)
    _gradient_body(p, body, colour, bw * 0.09)
    label = text
    if g.panel:  # two-tone micros (E-Lady): dark panel behind the knobs
        top = QRectF(body.left(), body.top(), bw, h * 0.47)
        path = QPainterPath()
        path.addRoundedRect(body, bw * 0.09, bw * 0.09)
        p.save()
        p.setClipPath(path)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_c(g.panel))
        p.drawRect(top)
        p.restore()
        label = _contrast(_c(g.panel))
    knob = _knob_colour(g.knob, _c(g.panel) if g.panel else colour)
    if detail:
        _text(p, QRectF(body.left(), body.top() + h * 0.015, bw, h * 0.04), "DC IN", label,
              bw * 0.07)
    ordered = _main_first(knobs) or [KnobState("", 0.5)] * 3
    big, small = ordered[0], ordered[1:3]
    for i, state in enumerate(small):
        x = body.left() + bw * (0.22 if i == 0 else 0.78)
        _knob(p, QPointF(x, body.top() + h * 0.12), bw * 0.1, knob, state.fraction, state.name,
              label, detail)
    big_colour = _c(g.big_knob) if g.big_knob else knob
    _knob(p, QPointF(body.center().x(), body.top() + h * 0.33), bw * 0.2, big_colour,
          big.fraction, big.name, label, detail)
    _led(p, QPointF(body.center().x(), body.top() + h * 0.515), bw * 0.045, on)
    _name(p, QRectF(body.left() + bw * 0.1, body.top() + h * 0.56, bw * 0.8, h * 0.08),
          g.logo_text or title, text, italic=True)
    _footswitch(p, QPointF(body.center().x(), body.top() + h * 0.78), bw * 0.2)


def _eq(p: QPainter, r: QRectF, g: Gear, title: str, knobs: list[KnobState], on: bool,
        detail: bool) -> None:
    """Mooer Graphic micro: LEVEL knob, sliders, italic name, footswitch, MOOER."""
    w, h = r.width(), r.height()
    body = r.adjusted(w * 0.07, h * 0.02, -w * 0.07, 0)
    bw = body.width()
    colour, text = _c(g.body), _c(g.text)
    _jacks(p, body, body.top() + h * 0.42, bw * 0.16, top=True)
    _gradient_body(p, body, colour, bw * 0.09)
    _knob(p, QPointF(body.center().x(), body.top() + h * 0.1), bw * 0.08,
          _knob_colour(g.knob, colour), 0.5, "LEVEL" if detail else "", text, detail)
    bands = knobs[:8] or [KnobState("", 0.5)] * 5
    area = QRectF(body.left() + bw * 0.14, body.top() + h * 0.2, bw * 0.72, h * 0.3)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(0, 0, 0, 60))
    p.drawRoundedRect(area.adjusted(-bw * 0.04, -h * 0.01, bw * 0.04, h * 0.01), 3, 3)
    step = area.width() / len(bands)
    for i, band in enumerate(bands):
        x = area.left() + step * (i + 0.5)
        p.setPen(QPen(QColor("#050505"), max(1.5, step * 0.2)))
        p.drawLine(QPointF(x, area.top()), QPointF(x, area.bottom()))
        y = area.bottom() - area.height() * band.fraction
        cap = QRectF(x - step * 0.36, y - h * 0.014, step * 0.72, h * 0.028)
        p.setPen(QPen(QColor("#111"), 1))
        p.setBrush(QColor("#f0f0f0"))
        p.drawRoundedRect(cap, 2, 2)
    _led(p, QPointF(body.center().x(), body.top() + h * 0.545), bw * 0.045, on)
    _name(p, QRectF(body.left() + bw * 0.12, body.top() + h * 0.58, bw * 0.76, h * 0.07),
          g.logo_text or title, text, italic=True)
    _footswitch(p, QPointF(body.center().x(), body.top() + h * 0.78), bw * 0.2)


def _stomp(p: QPainter, r: QRectF, g: Gear, title: str, knobs: list[KnobState], on: bool,
           detail: bool) -> None:
    """Standard die-cast pedal: knobs on top, LED, name (on an accent band if the pedal has
    one), footswitch and side jacks. ``shape: slope`` gives the Marshall slanted top."""
    w, h = r.width(), r.height()
    body = r.adjusted(w * 0.05, 0, -w * 0.05, 0)
    bw = body.width()
    colour, text = _c(g.body), _c(g.text)
    _jacks(p, body, body.top() + h * 0.36, bw * 0.12)
    _gradient_body(p, body, colour, bw * 0.06)
    knob = _knob_colour(g.knob, colour)
    if g.knob_style == "chrome":
        knob = QColor("#d7dbdf")
    elif g.shape == "slope":  # black knobs along the top edge, like the real one
        knob = _c(g.knob, "#151515")
    shown = knobs[:5] if g.shape == "slope" else knobs[:4]
    if g.shape == "slope":  # slanted top face holding the knobs and the gold name
        face = QRectF(body.left(), body.top(), bw, h * 0.34)
        grad = QLinearGradient(face.topLeft(), face.bottomLeft())
        grad.setColorAt(0, colour.lighter(170))
        grad.setColorAt(1, colour.lighter(115))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawRoundedRect(face, bw * 0.06, bw * 0.06)
        _knob_row(p, body.adjusted(bw * 0.04, 0, -bw * 0.04, 0), body.top() + h * 0.09, shown,
                  knob, _contrast(colour), detail, bw * 0.085)
        _name(p, QRectF(body.left() + bw * 0.08, body.top() + h * 0.22, bw * 0.84, h * 0.09),
              g.logo_text or title, text, italic=True)
        _led(p, QPointF(body.center().x(), body.top() + h * 0.45), bw * 0.025, on)
        _footswitch(p, QPointF(body.center().x(), body.top() + h * 0.6), bw * 0.1)
        return
    _knob_row(p, body.adjusted(bw * 0.08, 0, -bw * 0.08, 0), body.top() + h * 0.15, shown, knob,
              text, detail, bw * 0.13)
    _led(p, QPointF(body.center().x(), body.top() + h * 0.36), bw * 0.035, on)
    band = QRectF(body.left(), body.top() + h * 0.42, bw, h * 0.2)
    if g.accent:
        path = QPainterPath()
        path.moveTo(band.left(), band.bottom())
        path.lineTo(band.left(), band.top() + band.height() * 0.35)
        path.lineTo(band.right(), band.top() - band.height() * 0.15)
        path.lineTo(band.right(), band.bottom() - band.height() * 0.4)
        path.closeSubpath()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_c(g.accent))
        p.drawPath(path)
    _name(p, band.adjusted(bw * 0.08, 0, -bw * 0.08, 0), g.logo_text or title, text,
          italic=bool(g.accent))
    _footswitch(p, QPointF(body.center().x(), body.top() + h * 0.8), bw * 0.12)


def _wah(p: QPainter, r: QRectF, g: Gear, title: str, knobs: list[KnobState], on: bool,
         detail: bool) -> None:
    """Wah seen from the front: wider cast base, rubber treadle with ridges, logo plate."""
    w, h = r.width(), r.height()
    colour, text = _c(g.body), _c(g.text)
    base = QPainterPath()
    base.moveTo(r.left() + w * 0.1, r.top() + h * 0.1)
    base.lineTo(r.right() - w * 0.1, r.top() + h * 0.1)
    base.lineTo(r.right(), r.bottom() - h * 0.04)
    base.quadTo(r.right(), r.bottom(), r.right() - w * 0.05, r.bottom())
    base.lineTo(r.left() + w * 0.05, r.bottom())
    base.quadTo(r.left(), r.bottom(), r.left(), r.bottom() - h * 0.04)
    base.closeSubpath()
    grad = QLinearGradient(r.topLeft(), r.bottomLeft())
    grad.setColorAt(0, colour.lighter(150))
    grad.setColorAt(1, colour.darker(130))
    p.setPen(QPen(colour.darker(200), max(1.0, w * 0.01)))
    p.setBrush(QBrush(grad))
    p.drawPath(base)
    treadle = QRectF(r.left() + w * 0.06, r.top(), w * 0.88, h * 0.56)
    p.setBrush(QColor("#1b1b1b"))
    p.setPen(QPen(QColor("#050505"), max(1.0, w * 0.012)))
    p.drawRoundedRect(treadle, w * 0.1, w * 0.1)
    p.setPen(QPen(QColor("#303030"), max(1.0, h * 0.006)))
    for i in range(1, 14):
        y = treadle.top() + treadle.height() * i / 14
        p.drawLine(QPointF(treadle.left() + w * 0.08, y), QPointF(treadle.right() - w * 0.08, y))
    plate = QRectF(r.left() + w * 0.16, r.top() + h * 0.62, w * 0.68, h * 0.24)
    p.setPen(QPen(QColor("#3a3a3a"), max(1.0, w * 0.01)))
    p.setBrush(QColor("#0c0c0c"))
    p.drawRoundedRect(plate, w * 0.03, w * 0.03)
    _name(p, plate.adjusted(w * 0.04, h * 0.02, -w * 0.04, -h * 0.02), g.logo_text or title,
          text)
    if g.knob.lower() not in ("#151515", ""):  # the 535Q's red side knobs
        _knob(p, QPointF(r.right() - w * 0.05, r.top() + h * 0.74), w * 0.06, _c(g.knob), 0.5,
              "", text, False)
    _led(p, QPointF(r.center().x(), r.bottom() - h * 0.05), w * 0.03, on)


Painter = Callable[[QPainter, QRectF, Gear, str, list[KnobState], bool, bool], None]

_PAINTERS: dict[str, Painter] = {
    "stomp": _stomp, "bigbox": _bigbox, "boss": _boss, "round": _round, "micro": _micro,
    "wah": _wah, "eq": _eq, "head": amp_art.head, "combo": amp_art.combo, "cab": amp_art.cab,
    "acoustic": _acoustic,
}
