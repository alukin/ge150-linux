"""Picture of the gear behind a model: its photo if one is available, else a drawing."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QSizePolicy, QWidget

from ge150.model.gear import FALLBACK, MODULE_TAGS, Gear, gear_for, photo_path
from ge150.services.editor import Editor
from ge150.ui.gear_art import KnobState, paint_gear

_photos: dict[str, QPixmap | None] = {}
#: ``gid`` prefix of a user cabinet slot pictured with its TONE3000 image (then the path).
T3K = "t3k:"
FIRST_USER_CAB, LAST_USER_CAB = 27, 36


def user_cab_gear(editor: Editor, number: int, gear: Gear) -> Gear:
    """For a user CAB slot holding a TONE3000 IR whose image is cached: that image."""
    names = editor.state.user_names
    if names is None or not FIRST_USER_CAB <= number <= LAST_USER_CAB:
        return gear
    from ge150.services.tone3000 import IrSources, cached_image

    source = IrSources().matching(names.ir).get(str(number - FIRST_USER_CAB + 1))
    image = cached_image(str(source.get("image_url") or "")) if source else None
    return replace(gear, gid=f"{T3K}{image}") if image else gear


def load_photo(gid: str) -> QPixmap | None:
    if gid not in _photos:
        path: Path | None = Path(gid[len(T3K):]) if gid.startswith(T3K) else photo_path(gid)
        pixmap = QPixmap(str(path)) if path else None
        _photos[gid] = pixmap if pixmap is not None and not pixmap.isNull() else None
    return _photos[gid]


def clear_photo_cache() -> None:
    _photos.clear()


def module_look(editor: Editor, index: int) -> tuple[Gear, str, list[KnobState], bool]:
    """Gear, short title, knob positions and on/off of a module of the edit buffer."""
    if editor.state.edit is None:
        return FALLBACK, "", [], False
    block = editor.module(index)
    model = editor.catalog[index].model_for_type(block.type)
    if model is None:
        return FALLBACK, f"?{block.type}", [], bool(block.switch)
    knobs = []
    for param in model.params:
        if param.kind != "number":
            continue
        raw = block.words[param.word]
        low, high = param.to_raw(param.min), param.raw_max
        fraction = (raw - low) / (high - low) if high > low else 0.0
        knobs.append(KnobState(param.name, fraction, param.format(raw)))
    title = model.name
    if model.user_slot:
        title = editor.model_label(index, block.type).split(":", 1)[-1].strip() or model.name
    gear = gear_for(index, model.number)
    if model.user_slot and MODULE_TAGS[index] == "CAB":
        gear = user_cab_gear(editor, model.number, gear)
    return gear, title, knobs, bool(block.switch)


class GearView(QWidget):
    """Shows one piece of gear; ``set_gear`` updates it."""

    def __init__(self, compact: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.compact = compact
        self.gear: Gear = FALLBACK
        self.title = ""
        self.knobs: list[KnobState] = []
        self.on = True
        self.prefer_photo = True
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, compact)

    def sizeHint(self) -> QSize:
        return QSize(96, 78) if self.compact else QSize(360, 360)

    def set_gear(self, gear: Gear, title: str, knobs: list[KnobState], on: bool) -> None:
        self.gear, self.title, self.knobs, self.on = gear, title, knobs, on
        self.update()

    @property
    def photo(self) -> QPixmap | None:
        return load_photo(self.gear.gid) if self.prefer_photo else None

    def paintEvent(self, event: object) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        area = QRectF(self.rect()).adjusted(4, 4, -4, -4)
        photo = self.photo
        if photo is None:
            paint_gear(p, area, self.gear, self.title, self.knobs, self.on)
        else:
            self._paint_photo(p, area, photo)
        p.end()

    def _paint_photo(self, p: QPainter, area: QRectF, photo: QPixmap) -> None:
        scaled = photo.size().scaled(area.size().toSize(), Qt.AspectRatioMode.KeepAspectRatio)
        target = QRectF(0, 0, scaled.width(), scaled.height())
        target.moveCenter(area.center())
        clip = QPainterPath()
        radius = 6 if self.compact else 12
        clip.addRoundedRect(target, radius, radius)
        p.setClipPath(clip)
        p.drawPixmap(target, photo, QRectF(photo.rect()))
        if not self.on:
            p.fillRect(target, QColor(10, 12, 16, 150))
        p.setClipping(False)
