"""The real gear behind every model (``data/gear.json``) and where its photo is.

A photo is looked up first in the user folder (``$XDG_DATA_HOME/ge150/photos`` or
``~/.local/share/ge150/photos``), then among the photos shipped in ``ge150/data/photos``.
File name: ``<gear id>.jpg`` / ``.png`` / ``.webp``. Without a photo the GUI draws the gear.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from functools import cache
from importlib import resources
from pathlib import Path

PHOTO_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp")
#: module index (preset layout order) -> tag used by gear.json / effects.json
MODULE_TAGS = ("FX", "DS", "AMP", "CAB", "NS", "EQ", "MOD", "DELAY", "REVERB")


@dataclass(frozen=True)
class Gear:
    gid: str
    name: str
    kind: str
    body: str
    text: str = "#f2f2f2"
    knob: str = "#151515"
    panel: str = ""
    grille: str = ""
    speakers: str = ""
    slant: bool = False
    diamond: bool = False
    stripes: bool = False
    reference: str = ""  # classic unit shown in the photo when the model has no real origin
    generic: bool = False  # Mooer algorithm not based on a named unit
    extra: dict[str, object] = field(default_factory=dict)


FALLBACK = Gear("generic", "", "micro", "#3a3f47")


def describe(gear: Gear, has_photo: bool) -> str:
    """Caption under the picture: what the model is based on and what the photo shows."""
    if not gear.name:
        return ""
    text = gear.name if gear.generic else f"Basado en {gear.name}"
    if gear.reference and has_photo:
        text += f"  ·  foto de referencia: {gear.reference}"
    return text


def user_photo_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "ge150" / "photos"


@cache
def _table() -> tuple[dict[str, Gear], dict[str, dict[str, str]]]:
    raw = json.loads(resources.files("ge150.data").joinpath("gear.json").read_text())
    known = set(Gear.__dataclass_fields__) - {"gid", "extra"}
    gear: dict[str, Gear] = {}
    for gid, entry in raw["gear"].items():
        fields = {k: v for k, v in entry.items() if k in known}
        rest = {k: v for k, v in entry.items() if k not in known}
        gear[gid] = Gear(gid, **fields, extra=rest)
    return gear, raw["models"]


def gear_for(module_index: int, model_number: int) -> Gear:
    """Gear of a model (``model_number`` as shown by the pedal, 1-based)."""
    gear, models = _table()
    if not 0 <= module_index < len(MODULE_TAGS):
        return FALLBACK
    gid = models.get(MODULE_TAGS[module_index], {}).get(str(model_number))
    return gear.get(gid or "", FALLBACK)


def all_gear() -> dict[str, Gear]:
    return dict(_table()[0])


def photo_path(gid: str, extra_dirs: tuple[Path, ...] = ()) -> Path | None:
    """First existing photo for ``gid``: extra dirs, the user folder, then the package."""
    shipped = Path(str(resources.files("ge150.data").joinpath("photos")))
    for folder in (*extra_dirs, user_photo_dir(), shipped):
        for suffix in PHOTO_SUFFIXES:
            candidate = folder / f"{gid}{suffix}"
            if candidate.is_file():
                return candidate
    return None
