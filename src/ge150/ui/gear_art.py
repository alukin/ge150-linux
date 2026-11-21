"""Vector drawings of the gear behind each model, used when there is no photo.

Each ``Gear.kind`` has its own silhouette (stompbox, BOSS-style, round fuzz, wah, amp
head, combo, cabinet, ...) painted with the gear's colours. Knobs show the current
parameter values of the preset.
"""

from __future__ import annotations

import math
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


@dataclass(frozen=True)
class KnobState:
    name: str
    fraction: float  # 0..1
    text: str = ""


SPEAKER_ASPECT = {"1x10": 1.05, "1x12": 1.12, "2x12": 1.5, "4x10": 1.0, "4x12": 1.0}
KIND_ASPECT = {"stomp": 0.62, "boss": 0.58, "round": 0.86, "bigbox": 0.8, "micro": 0.5,
               "wah": 0.46, "eq": 0.62, "head": 2.1, "acoustic": 0.72}


def preferred_aspect(gear: Gear) -> float:
    """Width / height of the drawing."""
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
    painter = _PAINTERS.get(gear.kind, _stomp)
    painter(p, r, gear, title, knobs, on, detail)
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


def _speaker(p: QPainter, centre: QPointF, radius: float, grille: QColor) -> None:
    dark = grille.lightness() < 80
    ring = grille.lighter(190) if dark else grille.darker(125)
    p.setBrush(QColor(0, 0, 0, 45) if dark else Qt.BrushStyle.NoBrush)
    p.setPen(QPen(ring, max(1.0, radius * 0.05)))
    p.drawEllipse(centre, radius, radius)
    p.setPen(QPen(grille.lighter(160) if dark else grille.darker(112), max(1.0, radius * 0.03)))
    p.drawEllipse(centre, radius * 0.45, radius * 0.45)


def _cloth(p: QPainter, r: QRectF, grille: QColor) -> None:
    p.setPen(Qt.PenStyle.NoPen)
    grad = QLinearGradient(r.topLeft(), r.bottomRight())
    grad.setColorAt(0, grille.lighter(112))
    grad.setColorAt(1, grille.darker(118))
    p.setBrush(QBrush(grad))
    p.drawRect(r)
    p.setPen(QPen(QColor(0, 0, 0, 28), 1))
    step = max(3.0, r.width() / 90)
    x = r.left() - r.height()
    while x < r.right():
        p.drawLine(QPointF(x, r.bottom()), QPointF(x + r.height(), r.top()))
        x += step


def _speakers(p: QPainter, r: QRectF, layout: str, grille: QColor) -> None:
    rows, cols = {"1x10": (1, 1), "1x12": (1, 1), "2x12": (1, 2), "4x10": (2, 2),
                  "4x12": (2, 2)}.get(layout, (1, 1))
    cw, ch = r.width() / cols, r.height() / rows
    radius = min(cw, ch) * 0.4
    for row in range(rows):
        for col in range(cols):
            _speaker(p, QPointF(r.left() + cw * (col + 0.5), r.top() + ch * (row + 0.5)),
                     radius, grille)


def _knob_colour(knob: str, body: QColor) -> QColor:
    """The gear's knob colour, or silver when it would vanish against the body."""
    colour = _c(knob, "#151515")
    if abs(colour.lightness() - body.lightness()) < 45:
        return QColor("#cfd3d6") if body.lightness() < 128 else QColor("#1a1a1a")
    return colour


def _contrast(colour: QColor) -> QColor:
    return QColor("#f2f2f2") if colour.lightness() < 140 else QColor("#161616")


# --- silhouettes ----------------------------------------------------------------------


def _stomp(p: QPainter, r: QRectF, g: Gear, title: str, knobs: list[KnobState], on: bool,
           detail: bool) -> None:
    body, text = _c(g.body), _c(g.text)
    knob = _knob_colour(g.knob, body)
    _gradient_body(p, r, body, r.width() * 0.07)
    w, h = r.width(), r.height()
    inner = r.adjusted(w * 0.08, 0, -w * 0.08, 0)
    shown = knobs[:4]
    _knob_row(p, inner, r.top() + h * 0.17, shown, knob, text, detail, w * 0.12)
    _led(p, QPointF(r.center().x(), r.top() + h * 0.4), w * 0.035, on)
    _text(p, QRectF(r.left(), r.top() + h * 0.46, w, h * 0.16), title, text, w * 0.13)
    _footswitch(p, QPointF(r.center().x(), r.top() + h * 0.79), w * 0.12)


def _bigbox(p: QPainter, r: QRectF, g: Gear, title: str, knobs: list[KnobState], on: bool,
            detail: bool) -> None:
    body, text = _c(g.body), _c(g.text)
    knob = _knob_colour(g.knob, body)
    _gradient_body(p, r, body, r.width() * 0.04)
    w, h = r.width(), r.height()
    _knob_row(p, r.adjusted(w * 0.1, 0, -w * 0.1, 0), r.top() + h * 0.18, knobs[:3], knob,
              _contrast(body), detail, w * 0.08, 3)
    _text(p, QRectF(r.left(), r.top() + h * 0.36, w, h * 0.2), title, text, h * 0.14)
    _led(p, QPointF(r.left() + w * 0.82, r.top() + h * 0.62), w * 0.025, on)
    _footswitch(p, QPointF(r.center().x(), r.top() + h * 0.78), w * 0.08)


def _boss(p: QPainter, r: QRectF, g: Gear, title: str, knobs: list[KnobState], on: bool,
          detail: bool) -> None:
    body, text = _c(g.body), _c(g.text)
    knob = _knob_colour(g.knob, body)
    _gradient_body(p, r, body, r.width() * 0.05)
    w, h = r.width(), r.height()
    _knob_row(p, r.adjusted(w * 0.06, 0, -w * 0.06, 0), r.top() + h * 0.13, knobs[:4], knob,
              _contrast(body), detail, w * 0.1)
    _led(p, QPointF(r.left() + w * 0.12, r.top() + h * 0.31), w * 0.03, on)
    plate = QRectF(r.left() + w * 0.05, r.top() + h * 0.36, w * 0.9, h * 0.47)
    _gradient_body(p, plate, body.darker(115), w * 0.04)
    p.setPen(QPen(body.darker(160), max(1.0, w * 0.006)))
    for i in range(1, 8):
        y = plate.top() + plate.height() * i / 8
        p.drawLine(QPointF(plate.left() + w * 0.06, y), QPointF(plate.right() - w * 0.06, y))
    strip = QRectF(r.left() + w * 0.05, r.top() + h * 0.86, w * 0.9, h * 0.1)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#111"))
    p.drawRect(strip)
    _text(p, strip, title, text, strip.height() * 0.7)


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
    _text(p, QRectF(r.left(), r.top() + h * 0.46, w, h * 0.14), title, text, h * 0.1)
    _footswitch(p, QPointF(r.center().x(), r.top() + h * 0.72), w * 0.09)
    _led(p, QPointF(r.left() + w * 0.72, r.top() + h * 0.62), w * 0.025, on)


def _micro(p: QPainter, r: QRectF, g: Gear, title: str, knobs: list[KnobState], on: bool,
           detail: bool) -> None:
    body, text = _c(g.body), _c(g.text)
    knob = _knob_colour(g.knob, body)
    _gradient_body(p, r, body, r.width() * 0.08)
    w, h = r.width(), r.height()
    shown = knobs[:6]
    first, second = shown[:3], shown[3:]
    inner = r.adjusted(w * 0.06, 0, -w * 0.06, 0)
    _knob_row(p, inner, r.top() + h * 0.12, first, knob, text, detail, w * 0.13, 3)
    if second:
        _knob_row(p, inner, r.top() + h * 0.29, second, knob, text, detail, w * 0.13)
    _led(p, QPointF(r.center().x(), r.top() + h * 0.43), w * 0.04, on)
    _text(p, QRectF(r.left(), r.top() + h * 0.48, w, h * 0.13), title, text, w * 0.15)
    _footswitch(p, QPointF(r.center().x(), r.top() + h * 0.8), w * 0.17)


def _wah(p: QPainter, r: QRectF, g: Gear, title: str, knobs: list[KnobState], on: bool,
         detail: bool) -> None:
    body, text = _c(g.body), _c(g.text)
    _gradient_body(p, r, body, r.width() * 0.12)
    w, h = r.width(), r.height()
    treadle = r.adjusted(w * 0.09, h * 0.05, -w * 0.09, -h * 0.12)
    path = QPainterPath()
    path.addRoundedRect(treadle, w * 0.08, w * 0.08)
    p.setPen(QPen(QColor("#c9ced3"), max(1.5, w * 0.025)))
    p.setBrush(QColor("#2a2a2a"))
    p.drawPath(path)
    p.setPen(QPen(QColor("#3c3c3c"), max(1.0, w * 0.012)))
    for i in range(1, 16):
        y = treadle.top() + treadle.height() * i / 16
        p.drawLine(QPointF(treadle.left() + w * 0.08, y), QPointF(treadle.right() - w * 0.08, y))
    _text(p, QRectF(treadle.left(), treadle.top() + treadle.height() * 0.42, treadle.width(),
                    treadle.height() * 0.14), title, text, w * 0.14)
    if g.knob.lower() not in ("#151515", ""):
        _knob(p, QPointF(r.right() - w * 0.03, r.top() + h * 0.5), w * 0.06, _c(g.knob), 0.5, "",
              text, False)
    _led(p, QPointF(r.center().x(), r.bottom() - h * 0.06), w * 0.04, on)


def _eq(p: QPainter, r: QRectF, g: Gear, title: str, knobs: list[KnobState], on: bool,
        detail: bool) -> None:
    body, text = _c(g.body), _c(g.text)
    _gradient_body(p, r, body, r.width() * 0.07)
    w, h = r.width(), r.height()
    bands = knobs[:8] or [KnobState("", 0.5)] * 5
    area = QRectF(r.left() + w * 0.1, r.top() + h * 0.07, w * 0.8, h * 0.42)
    step = area.width() / len(bands)
    for i, band in enumerate(bands):
        x = area.left() + step * (i + 0.5)
        p.setPen(QPen(QColor("#0d0d0d"), max(1.5, step * 0.12)))
        p.drawLine(QPointF(x, area.top()), QPointF(x, area.bottom()))
        y = area.bottom() - area.height() * band.fraction
        cap = QRectF(x - step * 0.32, y - h * 0.018, step * 0.64, h * 0.036)
        p.setPen(QPen(QColor("#111"), 1))
        p.setBrush(QColor("#e8e8e8"))
        p.drawRoundedRect(cap, 2, 2)
    _led(p, QPointF(r.center().x(), r.top() + h * 0.56), w * 0.035, on)
    _text(p, QRectF(r.left(), r.top() + h * 0.6, w, h * 0.12), title, text, w * 0.12)
    _footswitch(p, QPointF(r.center().x(), r.top() + h * 0.83), w * 0.11)


def _amp_panel(p: QPainter, panel: QRectF, g: Gear, knobs: list[KnobState], detail: bool) -> None:
    colour = _c(g.panel, g.body)
    p.setPen(QPen(colour.darker(150), 1))
    grad = QLinearGradient(panel.topLeft(), panel.bottomLeft())
    grad.setColorAt(0, colour.lighter(118))
    grad.setColorAt(1, colour.darker(115))
    p.setBrush(QBrush(grad))
    p.drawRect(panel)
    if g.diamond:
        p.setPen(QPen(QColor(255, 255, 255, 60), 1))
        step = max(4.0, panel.height() / 5)
        x = panel.left()
        while x < panel.right():
            p.drawLine(QPointF(x, panel.top()), QPointF(x + step, panel.bottom()))
            p.drawLine(QPointF(x + step, panel.top()), QPointF(x, panel.bottom()))
            x += step
    label = _contrast(colour)
    inner = panel.adjusted(panel.width() * 0.04, 0, -panel.width() * 0.1, 0)
    _knob_row(p, inner, panel.top() + panel.height() * (0.4 if detail else 0.5), knobs[:9],
              _knob_colour(g.knob, colour), label, detail, panel.height() * 0.24, 6)
    jewel = QPointF(panel.right() - panel.width() * 0.05, panel.center().y())
    _led(p, jewel, panel.height() * 0.09, True)


def _logo(p: QPainter, r: QRectF, title: str, background: QColor) -> None:
    _text(p, r, title, _contrast(background), r.height() * 0.62)


def _head(p: QPainter, r: QRectF, g: Gear, title: str, knobs: list[KnobState], on: bool,
          detail: bool) -> None:
    tolex, grille = _c(g.body), _c(g.grille, "#262626")
    _gradient_body(p, r, tolex, r.height() * 0.08)
    w, h = r.width(), r.height()
    if g.stripes:
        p.setPen(QPen(QColor("#e8e8e8"), max(1.0, h * 0.02)))
        for i in range(5):
            x = r.left() + w * (0.01 + i * 0.008)
            p.drawLine(QPointF(x, r.top() + h * 0.1), QPointF(x + w * 0.02, r.bottom() - h * 0.1))
    front = r.adjusted(w * 0.035, h * 0.1, -w * 0.035, -h * 0.08)
    cloth = QRectF(front.left(), front.top(), front.width(), front.height() * 0.48)
    _cloth(p, cloth, grille)
    _logo(p, cloth.adjusted(cloth.width() * 0.25, cloth.height() * 0.22,
                            -cloth.width() * 0.25, -cloth.height() * 0.22), title, grille)
    panel = QRectF(front.left(), cloth.bottom() + h * 0.02, front.width(),
                   front.bottom() - cloth.bottom() - h * 0.02)
    _amp_panel(p, panel, g, knobs, detail)


def _combo(p: QPainter, r: QRectF, g: Gear, title: str, knobs: list[KnobState], on: bool,
           detail: bool) -> None:
    tolex, grille = _c(g.body), _c(g.grille, "#262626")
    _gradient_body(p, r, tolex, r.width() * 0.04)
    w, h = r.width(), r.height()
    front = r.adjusted(w * 0.04, h * 0.05, -w * 0.04, -h * 0.05)
    panel = QRectF(front.left(), front.top(), front.width(), front.height() * 0.2)
    _amp_panel(p, panel, g, knobs, detail)
    cloth = QRectF(front.left(), panel.bottom() + h * 0.02, front.width(),
                   front.bottom() - panel.bottom() - h * 0.02)
    _cloth(p, cloth, grille)
    _speakers(p, cloth.adjusted(w * 0.04, h * 0.06, -w * 0.04, -h * 0.04), g.speakers, grille)
    _logo(p, QRectF(cloth.left() + cloth.width() * 0.3, cloth.top() + cloth.height() * 0.04,
                    cloth.width() * 0.4, cloth.height() * 0.12), title, grille)


def _cab(p: QPainter, r: QRectF, g: Gear, title: str, knobs: list[KnobState], on: bool,
         detail: bool) -> None:
    tolex, grille = _c(g.body), _c(g.grille, "#262626")
    _gradient_body(p, r, tolex, r.width() * 0.04)
    w, h = r.width(), r.height()
    cloth = r.adjusted(w * 0.05, h * 0.05, -w * 0.05, -h * 0.05)
    _cloth(p, cloth, grille)
    if g.slant:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 22))
        p.drawRect(QRectF(cloth.left(), cloth.top(), cloth.width(), cloth.height() * 0.5))
    if g.diamond:
        p.setPen(QPen(QColor("#b8bcc0"), max(1.5, h * 0.02)))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(cloth)
    _speakers(p, cloth.adjusted(w * 0.03, h * 0.08, -w * 0.03, -h * 0.03), g.speakers, grille)
    _logo(p, QRectF(cloth.left() + cloth.width() * 0.25, cloth.top() + cloth.height() * 0.01,
                    cloth.width() * 0.5, cloth.height() * 0.08), title, grille)


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


_PAINTERS = {
    "stomp": _stomp, "bigbox": _bigbox, "boss": _boss, "round": _round, "micro": _micro,
    "wah": _wah, "eq": _eq, "head": _head, "combo": _combo, "cab": _cab, "acoustic": _acoustic,
}
