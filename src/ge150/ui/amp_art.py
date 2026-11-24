"""Amps and cabinets for :mod:`ge150.ui.gear_art`: heads, combos and cabinets drawn after the
real units (handle, corners, piping, grille material, brand logo and front panel).

The look comes from ``gear.json``: ``grille_style`` (cloth, basket, mesh, bars, sparkle,
wicker), ``logo`` (block, script, oval, rounded, lower, badge, z) with ``logo_text``,
``logo_colour`` (a colour, ``chrome`` or ``gold``) and ``logo_pos``, ``piping`` (colour of
the welt around the grille), ``knob_style`` (skirt, chrome, gold, chicken) and the older
``diamond`` (Mesa diamond plate), ``stripes`` (EVH stripes) and ``slant`` flags.
"""

from __future__ import annotations

import math
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
    QTransform,
)

from ge150.model.gear import Gear

SCRIPT_FONTS = ["Z003", "URW Chancery L", "Brush Script MT", "Noto Serif", "Liberation Serif",
                "DejaVu Serif", "serif"]
BLOCK_FONTS = ["Noto Sans", "Liberation Sans", "DejaVu Sans", "sans-serif"]


def colour(value: str, fallback: str = "#444") -> QColor:
    c = QColor(value or fallback)
    return c if c.isValid() else QColor(fallback)


def contrast(c: QColor) -> QColor:
    return QColor("#f2f2f2") if c.lightness() < 140 else QColor("#161616")


# --- materials -----------------------------------------------------------------------------


def metal_brush(r: QRectF, tone: str) -> QBrush:
    """Chrome or gold gradient (logos, plates, corners)."""
    grad = QLinearGradient(r.topLeft(), r.bottomLeft())
    stops = {"gold": ("#fff1b8", "#c9a14a", "#8a6a22", "#e8cf7d"),
             "chrome": ("#ffffff", "#c3c8ce", "#6f767e", "#e3e6ea"),
             "copper": ("#f0b9a0", "#c47d62", "#8f4f3b", "#d99a7f"),
             "steel": ("#f4f5f6", "#a9aeb3", "#6b7076", "#d0d3d6")}[tone]
    for pos, stop in zip((0.0, 0.45, 0.55, 1.0), stops, strict=True):
        grad.setColorAt(pos, QColor(stop))
    return QBrush(grad)


def paint_brush(value: str, r: QRectF) -> QBrush:
    if value in ("chrome", "gold"):
        return metal_brush(r, value)
    return QBrush(colour(value, "#f2f2f2"))


def tolex(p: QPainter, r: QRectF, c: QColor, radius: float) -> None:
    """Covered wooden box: base colour, soft light from the top and a fine grain."""
    grad = QLinearGradient(r.topLeft(), r.bottomLeft())
    grad.setColorAt(0, c.lighter(135))
    grad.setColorAt(0.12, c)
    grad.setColorAt(1, c.darker(140))
    p.setPen(QPen(c.darker(220), max(1.0, r.width() * 0.004)))
    p.setBrush(QBrush(grad))
    p.drawRoundedRect(r, radius, radius)
    p.save()
    path = QPainterPath()
    path.addRoundedRect(r, radius, radius)
    p.setClipPath(path)
    p.setPen(QPen(QColor(255, 255, 255, 10) if c.lightness() < 90 else QColor(0, 0, 0, 14), 1))
    step = max(2.0, r.height() / 60)
    y = r.top()
    while y < r.bottom():
        p.drawLine(QPointF(r.left(), y), QPointF(r.right(), y + step * 0.6))
        y += step
    p.restore()


def grille(p: QPainter, r: QRectF, g: Gear, base: QColor) -> None:
    style = g.grille_style or "cloth"
    p.save()
    p.setClipRect(r)
    p.setPen(Qt.PenStyle.NoPen)
    grad = QLinearGradient(r.topLeft(), r.bottomRight())
    grad.setColorAt(0, base.lighter(118))
    grad.setColorAt(1, base.darker(125))
    p.setBrush(QBrush(grad))
    p.drawRect(r)
    unit = max(2.5, min(r.width(), r.height()) / 45)
    if style == "mesh":  # perforated metal: rows of holes
        p.setBrush(QColor(0, 0, 0, 150) if base.lightness() > 60 else QColor(255, 255, 255, 26))
        y, row = r.top() + unit / 2, 0
        while y < r.bottom():
            x = r.left() + (unit / 2 if row % 2 else unit)
            while x < r.right():
                p.drawEllipse(QPointF(x, y), unit * 0.3, unit * 0.3)
                x += unit
            y += unit * 0.87
            row += 1
    elif style == "bars":  # horizontal slats with dark gaps
        bar = r.height() / 9
        for i in range(9):
            slat = QRectF(r.left(), r.top() + bar * i + bar * 0.18, r.width(), bar * 0.64)
            g2 = QLinearGradient(slat.topLeft(), slat.bottomLeft())
            g2.setColorAt(0, base.lighter(170))
            g2.setColorAt(1, base.darker(110))
            p.setBrush(QBrush(g2))
            p.drawRect(slat)
    elif style in ("basket", "wicker", "sparkle", "cloth"):
        light = QColor(255, 255, 255, 34 if style != "sparkle" else 70)
        dark = QColor(0, 0, 0, 40 if style != "basket" else 70)
        step = unit * (0.9 if style == "basket" else 0.6)
        p.setPen(QPen(dark, max(0.6, unit * 0.18)))
        x = r.left() - r.height()
        while x < r.right():
            p.drawLine(QPointF(x, r.bottom()), QPointF(x + r.height(), r.top()))
            x += step
        if style in ("basket", "wicker"):
            p.setPen(QPen(light, max(0.6, unit * 0.14)))
            x = r.left()
            while x < r.right() + r.height():
                p.drawLine(QPointF(x, r.bottom()), QPointF(x - r.height(), r.top()))
                x += step
        if style == "sparkle":
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, 120))
            seed = 7
            for _ in range(int(r.width() * r.height() / (unit * unit * 3))):
                seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
                px = r.left() + (seed % 1000) / 1000 * r.width()
                seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
                py = r.top() + (seed % 1000) / 1000 * r.height()
                p.drawEllipse(QPointF(px, py), unit * 0.12, unit * 0.12)
    if g.diamond:  # Mesa diamond plate across the grille
        p.setPen(QPen(QColor(255, 255, 255, 55), max(0.8, unit * 0.2)))
        step = unit * 2.2
        x = r.left() - r.height()
        while x < r.right() + r.height():
            p.drawLine(QPointF(x, r.bottom()), QPointF(x + r.height(), r.top()))
            p.drawLine(QPointF(x, r.top()), QPointF(x + r.height(), r.bottom()))
            x += step
    if g.stripes:  # EVH: white stripes crossing the black grille
        p.setPen(QPen(QColor("#f2f2f2"), max(1.5, r.height() * 0.035)))
        for x0, x1 in ((0.04, 0.42), (0.22, 0.02), (0.55, 0.96), (0.78, 0.6), (0.9, 0.7)):
            p.drawLine(QPointF(r.left() + r.width() * x0, r.top()),
                       QPointF(r.left() + r.width() * x1, r.bottom()))
    if g.slant:  # the angled upper half of a slant cabinet catches more light
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 16))
        p.drawRect(QRectF(r.left(), r.top(), r.width(), r.height() * 0.5))
    shade = QRadialGradient(r.center(), max(r.width(), r.height()) * 0.75)
    shade.setColorAt(0, QColor(0, 0, 0, 0))
    shade.setColorAt(1, QColor(0, 0, 0, 70))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(shade))
    p.drawRect(r)
    p.restore()
    if g.piping:
        p.setPen(QPen(paint_brush(g.piping, r), max(1.2, min(r.width(), r.height()) * 0.012)))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(r)


def speaker_shadows(p: QPainter, r: QRectF, layout: str) -> None:
    """Cones barely showing through the cloth (only a darker round shade)."""
    rows, cols = {"1x10": (1, 1), "1x12": (1, 1), "2x12": (1, 2), "4x10": (2, 2),
                  "4x12": (2, 2)}.get(layout, (1, 1))
    cw, ch = r.width() / cols, r.height() / rows
    radius = min(cw, ch) * 0.42
    p.setPen(Qt.PenStyle.NoPen)
    for row in range(rows):
        for col in range(cols):
            centre = QPointF(r.left() + cw * (col + 0.5), r.top() + ch * (row + 0.5))
            shade = QRadialGradient(centre, radius)
            shade.setColorAt(0, QColor(0, 0, 0, 22))
            shade.setColorAt(0.75, QColor(0, 0, 0, 12))
            shade.setColorAt(1, QColor(0, 0, 0, 0))
            p.setBrush(QBrush(shade))
            p.drawEllipse(centre, radius, radius)


def corners(p: QPainter, r: QRectF, size: float, tone: str = "dark") -> None:
    brush = metal_brush(r, "chrome") if tone == "chrome" else QBrush(QColor("#0c0c0c"))
    p.setPen(QPen(QColor(0, 0, 0, 160), max(0.6, size * 0.06)))
    p.setBrush(brush)
    for cx, cy, sx, sy in ((r.left(), r.top(), 1, 1), (r.right(), r.top(), -1, 1),
                           (r.left(), r.bottom(), 1, -1), (r.right(), r.bottom(), -1, -1)):
        path = QPainterPath(QPointF(cx, cy))
        path.lineTo(cx + sx * size, cy)
        path.quadTo(cx + sx * size * 0.35, cy + sy * size * 0.35, cx, cy + sy * size)
        path.closeSubpath()
        p.drawPath(path)


def handle(p: QPainter, r: QRectF, top: float, width: float) -> None:
    """Leather strap handle on top of the box."""
    h = max(4.0, width * 0.16)
    strap = QRectF(r.center().x() - width / 2, top - h * 0.85, width, h)
    grad = QLinearGradient(strap.topLeft(), strap.bottomLeft())
    grad.setColorAt(0, QColor("#3a3a3a"))
    grad.setColorAt(1, QColor("#0d0d0d"))
    p.setPen(QPen(QColor("#050505"), 1))
    p.setBrush(QBrush(grad))
    p.drawRoundedRect(strap, h * 0.45, h * 0.45)
    p.setBrush(metal_brush(strap, "chrome"))
    for x in (strap.left() - h * 0.2, strap.right() - h * 0.5):
        p.drawRect(QRectF(x, strap.bottom() - h * 0.55, h * 0.7, h * 0.7))


# --- logos ---------------------------------------------------------------------------------


def logo(p: QPainter, area: QRectF, text: str, style: str, tone: str, background: QColor) -> None:
    """Brand logo fitted into ``area``; ``tone`` is a colour, ``chrome`` or ``gold``."""
    if not text or area.width() < 6 or area.height() < 4:
        return
    style = style or "block"
    tone = tone or ("chrome" if background.lightness() < 90 else "#161616")
    if style == "oval":  # EVH-style badge: white oval, dark letters
        p.setPen(QPen(QColor("#0b0b0b"), max(1.0, area.height() * 0.06)))
        p.setBrush(QColor("#f4f4f4"))
        badge = _fit_box(area, 2.4)
        p.drawEllipse(badge)
        _logo_text(p, badge.adjusted(badge.width() * 0.16, badge.height() * 0.2,
                                     -badge.width() * 0.16, -badge.height() * 0.2),
                   text, "block", "#111111")
        return
    if style == "badge":  # metal name plate
        plate = _fit_box(area, 3.2)
        p.setPen(QPen(QColor("#222"), max(1.0, plate.height() * 0.05)))
        p.setBrush(metal_brush(plate, "chrome"))
        p.drawRoundedRect(plate, plate.height() * 0.12, plate.height() * 0.12)
        _logo_text(p, plate.adjusted(plate.width() * 0.08, plate.height() * 0.18,
                                     -plate.width() * 0.08, -plate.height() * 0.18),
                   text, "block", "#151515")
        return
    outline = style == "rounded" or (tone in ("chrome", "gold") and background.lightness() > 130)
    _logo_text(p, area, text, style, tone, outline)


def _fit_box(area: QRectF, aspect: float) -> QRectF:
    w = min(area.width(), area.height() * aspect)
    h = w / aspect
    return QRectF(area.center().x() - w / 2, area.center().y() - h / 2, w, h)


def _logo_text(p: QPainter, area: QRectF, text: str, style: str, tone: str,
               outline: bool = False) -> None:
    font = QFont()
    if style == "script":
        font.setFamilies(SCRIPT_FONTS)
        font.setItalic(True)
        font.setWeight(QFont.Weight.Bold)
    elif style == "lower":
        font.setFamilies(BLOCK_FONTS)
        font.setWeight(QFont.Weight.Light)
        text = text.lower()
    elif style == "z":
        font.setFamilies(SCRIPT_FONTS)
        font.setWeight(QFont.Weight.Black)
    else:  # block / rounded
        font.setFamilies(BLOCK_FONTS)
        font.setWeight(QFont.Weight.Black)
        font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 104)
    font.setPixelSize(100)
    path = QPainterPath()
    path.addText(0, 0, font, text)
    if style == "script":  # a little extra slant reads as handwriting
        path = QTransform().shear(-0.18, 0).map(path)
    box = path.boundingRect()
    if box.isEmpty():
        return
    scale = min(area.width() * 0.94 / box.width(), area.height() * 0.9 / box.height())
    t = QTransform()
    t.translate(area.center().x(), area.center().y())
    t.scale(scale, scale)
    t.translate(-box.center().x(), -box.center().y())
    path = t.map(path)
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    shadow = QTransform.fromTranslate(0, max(0.6, area.height() * 0.03)).map(path)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(0, 0, 0, 110))
    p.drawPath(shadow)
    p.setPen(QPen(QColor("#1a1a1a"), max(0.8, area.height() * 0.05)) if outline
             else Qt.PenStyle.NoPen)
    p.setBrush(paint_brush(tone, path.boundingRect()))
    p.drawPath(path)
    p.restore()


# --- front panel ---------------------------------------------------------------------------


def amp_knob(p: QPainter, centre: QPointF, radius: float, style: str, base: QColor,
             fraction: float) -> None:
    """Amp knob: skirted (Fender/Marshall), chrome, gold cap or chicken head."""
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(0, 0, 0, 100))
    p.drawEllipse(centre + QPointF(radius * 0.1, radius * 0.15), radius, radius)
    angle = math.radians(225 - 270 * max(0.0, min(1.0, fraction)))
    direction = QPointF(math.cos(angle), -math.sin(angle))
    if style == "chicken":
        body = QPainterPath()
        body.addEllipse(centre, radius * 0.62, radius * 0.62)
        tip = centre + direction * radius
        side = QPointF(-direction.y(), direction.x()) * radius * 0.42
        arrow = QPainterPath(tip)
        arrow.lineTo(centre + side)
        arrow.lineTo(centre - direction * radius * 0.55)
        arrow.lineTo(centre - side)
        arrow.closeSubpath()
        p.setBrush(QColor("#1a1a1a"))
        p.setPen(QPen(QColor("#000"), max(0.6, radius * 0.06)))
        p.drawPath(body.united(arrow))
        p.setPen(QPen(QColor("#f2f2f2"), max(0.8, radius * 0.1)))
        p.drawLine(centre, tip)
        return
    if style in ("skirt", "gold"):  # metal skirt with numbers ring
        p.setBrush(metal_brush(QRectF(centre.x() - radius, centre.y() - radius, radius * 2,
                                      radius * 2), "chrome" if style == "skirt" else "gold"))
        p.setPen(QPen(QColor("#2a2a2a"), max(0.6, radius * 0.05)))
        p.drawEllipse(centre, radius, radius)
        cap = radius * 0.66
    else:
        cap = radius
    face = QRadialGradient(centre - QPointF(cap * 0.35, cap * 0.4), cap * 1.6)
    if style == "chrome":
        face.setColorAt(0, QColor("#ffffff"))
        face.setColorAt(0.5, QColor("#b9bec4"))
        face.setColorAt(1, QColor("#5e646a"))
    else:
        top = base if style != "gold" else QColor("#151515")
        face.setColorAt(0, top.lighter(190))
        face.setColorAt(0.5, top)
        face.setColorAt(1, top.darker(170))
    p.setBrush(QBrush(face))
    p.setPen(QPen(QColor("#050505"), max(0.6, cap * 0.07)))
    p.drawEllipse(centre, cap, cap)
    pointer = QColor("#111") if style == "chrome" or base.lightness() > 150 else QColor("#f2f2f2")
    p.setPen(QPen(pointer, max(1.0, cap * 0.14), Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap))
    p.drawLine(centre + direction * cap * 0.2, centre + direction * cap * 0.85)


def panel(p: QPainter, r: QRectF, g: Gear, knobs: list[Any], detail: bool, label: str) -> None:
    """Control panel: input jack, a row of knobs, model name, switches and the jewel lamp."""
    base = colour(g.panel, g.body)
    grad = QLinearGradient(r.topLeft(), r.bottomLeft())
    grad.setColorAt(0, base.lighter(125))
    grad.setColorAt(0.5, base)
    grad.setColorAt(1, base.darker(125))
    p.setPen(QPen(base.darker(170), max(0.8, r.height() * 0.02)))
    p.setBrush(QBrush(grad))
    p.drawRect(r)
    ink = contrast(base)
    knob_base = colour(g.knob, "#151515")
    h = r.height()
    jack = QPointF(r.left() + h * 0.45, r.center().y())
    p.setPen(QPen(QColor("#111"), max(0.6, h * 0.03)))
    p.setBrush(metal_brush(QRectF(jack.x() - h * 0.14, jack.y() - h * 0.14, h * 0.28, h * 0.28),
                           "chrome"))
    p.drawEllipse(jack, h * 0.14, h * 0.14)
    p.setBrush(QColor("#050505"))
    p.drawEllipse(jack, h * 0.06, h * 0.06)
    states = knobs[:9] or [None] * 6
    controls = QRectF(r.left() + h * 0.9, r.top(),
                      r.width() - h * (3.8 if g.eq_sliders else 2.6), h)
    step = controls.width() / len(states)
    radius = min(step * 0.34, h * 0.2)
    y = r.top() + h * (0.4 if detail else 0.5)
    for i, state in enumerate(states):
        centre = QPointF(controls.left() + step * (i + 0.5), y)
        amp_knob(p, centre, radius, g.knob_style, knob_base,
                 state.fraction if state is not None else 0.5)
        if detail and state is not None and state.name and step >= 30 and h >= 24:
            _small_text(p, QRectF(centre.x() - step / 2, y + radius * 1.15, step, h * 0.2),
                        state.name, ink, h * 0.11)
    if detail and label:
        _small_text(p, QRectF(r.left(), r.bottom() - h * 0.2, r.width() * 0.4, h * 0.18), label,
                    ink, h * 0.1)
    if g.eq_sliders:  # Mesa graphic EQ: a window of vertical sliders
        box = QRectF(r.right() - h * 2.5, r.top() + h * 0.18, h * 1.0, h * 0.64)
        p.setPen(QPen(QColor("#888"), max(0.6, h * 0.02)))
        p.setBrush(QColor("#0b0b0b"))
        p.drawRect(box)
        for i in range(g.eq_sliders):
            x = box.left() + box.width() * (i + 0.5) / g.eq_sliders
            p.setPen(QPen(QColor("#3a3a3a"), max(0.8, h * 0.03)))
            p.drawLine(QPointF(x, box.top() + h * 0.06), QPointF(x, box.bottom() - h * 0.06))
            y = box.top() + box.height() * (0.3 + 0.4 * ((i * 37) % 5) / 4)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#e8e8e8"))
            p.drawRect(QRectF(x - h * 0.06, y - h * 0.03, h * 0.12, h * 0.06))
    for i in range(2):  # standby and power toggles
        sx = r.right() - h * (1.35 - i * 0.42)
        p.setPen(QPen(QColor("#111"), max(0.6, h * 0.03)))
        p.setBrush(metal_brush(QRectF(sx - h * 0.08, y - h * 0.18, h * 0.16, h * 0.36), "chrome"))
        p.drawRoundedRect(QRectF(sx - h * 0.05, y - h * 0.2, h * 0.1, h * 0.28), 2, 2)
    lamp = QPointF(r.right() - h * 0.42, y)
    glow = QRadialGradient(lamp, h * 0.3)
    glow.setColorAt(0, QColor(255, 70, 50, 200))
    glow.setColorAt(1, QColor(255, 70, 50, 0))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(glow))
    p.drawEllipse(lamp, h * 0.3, h * 0.3)
    jewel = QRadialGradient(lamp - QPointF(h * 0.04, h * 0.04), h * 0.14)
    jewel.setColorAt(0, QColor("#ffd2c8"))
    jewel.setColorAt(1, QColor("#c0180c"))
    p.setBrush(QBrush(jewel))
    p.setPen(QPen(metal_brush(QRectF(lamp.x() - 9, lamp.y() - 9, 18, 18), "chrome"),
                  max(1.0, h * 0.04)))
    p.drawEllipse(lamp, h * 0.12, h * 0.12)


def side_panel(p: QPainter, r: QRectF, g: Gear, knobs: list[Any]) -> None:
    """Vertical control strip: knobs one under the other, jewel lamp at the bottom."""
    base = colour(g.panel, g.body)
    grad = QLinearGradient(r.topLeft(), r.topRight())
    grad.setColorAt(0, base.darker(110))
    grad.setColorAt(0.5, base.lighter(108))
    grad.setColorAt(1, base.darker(110))
    p.setPen(QPen(base.darker(170), max(0.8, r.width() * 0.03)))
    p.setBrush(QBrush(grad))
    p.drawRect(r)
    states = knobs[:6] or [None] * 5
    step = r.height() * 0.8 / len(states)
    radius = min(r.width() * 0.26, step * 0.34)
    for i, state in enumerate(states):
        centre = QPointF(r.center().x(), r.top() + r.height() * 0.06 + step * (i + 0.5))
        amp_knob(p, centre, radius, g.knob_style, colour(g.knob, "#151515"),
                 state.fraction if state is not None else 0.5)
    lamp = QPointF(r.center().x(), r.bottom() - r.height() * 0.08)
    p.setPen(QPen(QColor("#222"), 1))
    p.setBrush(QColor("#e33a2a"))
    p.drawEllipse(lamp, radius * 0.4, radius * 0.4)


def _small_text(p: QPainter, r: QRectF, text: str, ink: QColor, size: float) -> None:
    if size < 4:
        return
    font = QFont()
    font.setFamilies(BLOCK_FONTS)
    font.setBold(True)
    font.setPixelSize(max(4, int(size)))
    while font.pixelSize() > 4:
        p.setFont(font)
        if p.fontMetrics().horizontalAdvance(text) <= r.width() * 0.96:
            break
        font.setPixelSize(font.pixelSize() - 1)
    p.setPen(ink)
    p.drawText(r, int(Qt.AlignmentFlag.AlignCenter), text)


# --- silhouettes ---------------------------------------------------------------------------


def _brand(g: Gear, title: str) -> str:
    return g.logo_text or title


def head(p: QPainter, r: QRectF, g: Gear, title: str, knobs: list[Any], on: bool,
         detail: bool) -> None:
    w, h = r.width(), r.height()
    box = r.adjusted(0, h * 0.1, 0, 0)
    handle(p, box, box.top(), w * 0.22)
    tolex(p, box, colour(g.body), h * 0.06)
    bh = box.height()
    front = box.adjusted(w * 0.03, bh * 0.08, -w * 0.03, -bh * 0.08)
    upper = g.logo_pos != "panel"
    if g.panel_side == "top":  # controls above the grille (Mesa Mark)
        face = QRectF(front.left(), front.top(), front.width(), front.height() * 0.4)
        cloth = QRectF(front.left(), face.bottom() + bh * 0.03, front.width(),
                       front.bottom() - face.bottom() - bh * 0.03)
    else:
        cloth = QRectF(front.left(), front.top(), front.width(), front.height() * 0.56)
        face = QRectF(front.left(), cloth.bottom() + bh * 0.03, front.width(),
                      front.bottom() - cloth.bottom() - bh * 0.03)
    grille(p, cloth, g, colour(g.grille, "#262626"))
    panel(p, face, g, knobs, detail, title if g.logo_text else "")
    if g.logo_pos and g.logo_pos != "panel":
        _cloth_logo(p, cloth, g, title, "center")
    elif upper:
        logo(p, cloth.adjusted(cloth.width() * 0.26, cloth.height() * 0.2, -cloth.width() * 0.26,
                               -cloth.height() * 0.2), _brand(g, title), g.logo, g.logo_colour,
             colour(g.grille, "#262626"))
    corners(p, box, min(w, h) * 0.07, "chrome" if g.corners == "chrome" else "dark")


def combo(p: QPainter, r: QRectF, g: Gear, title: str, knobs: list[Any], on: bool,
          detail: bool) -> None:
    w, h = r.width(), r.height()
    box = r.adjusted(0, h * 0.05, 0, 0)
    handle(p, box, box.top(), w * 0.26)
    tolex(p, box, colour(g.body), w * 0.03)
    bh = box.height()
    front = box.adjusted(w * 0.035, bh * 0.04, -w * 0.035, -bh * 0.05)
    if g.panel_side == "right":  # controls in a vertical strip beside the grille
        strip = QRectF(front.right() - front.width() * 0.17, front.top(), front.width() * 0.17,
                       front.height())
        side_panel(p, strip, g, knobs)
        cloth = QRectF(front.left(), front.top(), front.width() * 0.8, front.height())
    else:
        face = QRectF(front.left(), front.top(), front.width(), front.height() * 0.17)
        panel(p, face, g, knobs, detail, title if g.logo_text else "")
        cloth = QRectF(front.left(), face.bottom() + bh * 0.02, front.width(),
                       front.bottom() - face.bottom() - bh * 0.02)
    grille(p, cloth, g, colour(g.grille, "#262626"))
    speaker_shadows(p, cloth.adjusted(w * 0.05, bh * 0.06, -w * 0.05, -bh * 0.04), g.speakers)
    _cloth_logo(p, cloth, g, title, "topleft")
    corners(p, box, min(w, h) * 0.06, "chrome" if g.corners == "chrome" else "dark")


def cab(p: QPainter, r: QRectF, g: Gear, title: str, knobs: list[Any], on: bool,
        detail: bool) -> None:
    w, h = r.width(), r.height()
    tolex(p, r, colour(g.body), w * 0.03)
    cloth = r.adjusted(w * 0.055, h * 0.055, -w * 0.055, -h * 0.055)
    grille(p, cloth, g, colour(g.grille, "#262626"))
    speaker_shadows(p, cloth.adjusted(w * 0.03, h * 0.06, -w * 0.03, -h * 0.03), g.speakers)
    _cloth_logo(p, cloth, g, title, "center")
    corners(p, r, min(w, h) * 0.065, "chrome" if g.corners == "chrome" else "dark")


def _cloth_logo(p: QPainter, cloth: QRectF, g: Gear, title: str, default: str) -> None:
    where = g.logo_pos or default
    cw, ch = cloth.width(), cloth.height()
    boxes = {
        "topleft": QRectF(cloth.left() + cw * 0.05, cloth.top() + ch * 0.05, cw * 0.32, ch * 0.16),
        "top": QRectF(cloth.left() + cw * 0.3, cloth.top() + ch * 0.05, cw * 0.4, ch * 0.14),
        "center": QRectF(cloth.left() + cw * 0.28, cloth.top() + ch * 0.42, cw * 0.44, ch * 0.16),
        "bottomright": QRectF(cloth.right() - cw * 0.3, cloth.bottom() - ch * 0.15, cw * 0.26,
                              ch * 0.11),
        "topright": QRectF(cloth.right() - cw * 0.34, cloth.top() + ch * 0.05, cw * 0.3,
                           ch * 0.13),
        "bottomleft": QRectF(cloth.left() + cw * 0.03, cloth.bottom() - ch * 0.46, cw * 0.2,
                             ch * 0.38),
    }
    logo(p, boxes.get(where, boxes["center"]), _brand(g, title), g.logo, g.logo_colour,
         colour(g.grille, "#262626"))
