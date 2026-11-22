"""The user's guitars: what is plugged into the pedal also shapes the sound.

Each guitar is a plain record (brand, model, year, serial, woods, pickups, electronics,
strings, tuning...) kept in ``$XDG_CONFIG_HOME/ge150/guitars.json`` with the one in use.
:func:`identify` asks Claude or Codex (no tools) what a brand + model + serial number
probably is, as suggestions the user reviews before saving; :func:`context_text` is what the
AI assistant receives about the guitar in use.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import urllib.request
import uuid
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

from ge150.services import tone_ai

#: (field, label) in display order; every field is free text.
FIELDS = (("brand", "Marca"), ("model", "Modelo"), ("year", "Año"),
          ("serial", "Número de serie"), ("origin", "País / fábrica"),
          ("body", "Cuerpo (madera, forma)"), ("neck", "Mástil y diapasón"),
          ("scale", "Escala"), ("pickup_neck", "Pastilla del mástil"),
          ("pickup_middle", "Pastilla central"), ("pickup_bridge", "Pastilla del puente"),
          ("electronics", "Controles y selector"), ("bridge", "Puente"),
          ("strings", "Cuerdas"), ("tuning", "Afinación"), ("notes", "Notas"))
#: How a field was established, from surest to least sure.
EVIDENCE = {"oficial": "ficha oficial del fabricante",
            "verificado": "varias fuentes del modelo exacto",
            "deducido": "deducido (p. ej. del número de serie)",
            "probable": "probable, sin confirmar"}
SPEC_FIELDS = tuple(name for name, _ in FIELDS if name not in ("serial", "strings", "tuning",
                                                                "notes"))


@dataclass
class Guitar:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    brand: str = ""
    model: str = ""
    year: str = ""
    serial: str = ""
    origin: str = ""
    body: str = ""
    neck: str = ""
    scale: str = ""
    pickup_neck: str = ""
    pickup_middle: str = ""
    pickup_bridge: str = ""
    electronics: str = ""
    bridge: str = ""
    strings: str = ""
    tuning: str = ""
    notes: str = ""
    #: field -> how sure it is (see EVIDENCE); fields the user typed have none.
    evidence: dict[str, str] = field(default_factory=dict)
    #: the last identification: how it was done and its sources.
    report: str = ""
    #: local picture of the guitar (downloaded official photo or the user's own).
    image: str = ""

    @property
    def title(self) -> str:
        name = " ".join(p for p in (self.brand, self.model) if p) or "Guitarra sin nombre"
        return f"{name} ({self.year})" if self.year else name

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Guitar:
        known = {f.name for f in fields(cls)} - {"evidence"}
        guitar = cls()
        for key, value in data.items():
            if key in known:
                setattr(guitar, key, str(value))
        evidence = data.get("evidence")
        if isinstance(evidence, dict):
            guitar.evidence = {str(k): str(v) for k, v in evidence.items() if v in EVIDENCE}
        return guitar


def images_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "ge150" / "guitars"


#: Some shops refuse unknown clients; a browser-like agent gets the same public picture.
IMAGE_AGENT = "Mozilla/5.0 (X11; Linux x86_64) ge150-linux"
IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


def download_image(url: str, guitar_id: str) -> Path:
    """Fetch a guitar picture (https only, an image, at most 10 MB) next to its record."""
    if not url.startswith("https://"):
        raise ValueError(f"not an https image: {url[:80]}")
    request = urllib.request.Request(url, headers={"User-Agent": IMAGE_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        kind = response.headers.get_content_type()
        if kind not in IMAGE_TYPES:
            raise ValueError(f"not an image ({kind})")
        data = response.read(10 * 1024 * 1024 + 1)
    if len(data) > 10 * 1024 * 1024:
        raise ValueError("image too large")
    path = images_dir() / f"{guitar_id}{IMAGE_TYPES[kind]}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def set_own_image(guitar: Guitar, source: Path) -> Path:
    """Copy the user's own picture of ``guitar`` into the guitars folder."""
    suffix = source.suffix.lower() if source.suffix.lower() in (".jpg", ".jpeg", ".png",
                                                                 ".webp") else ".jpg"
    path = images_dir() / f"{guitar.id}{suffix}"
    path.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != path.resolve():
        shutil.copyfile(source, path)
    guitar.image = str(path)
    return path


def _config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "ge150" / "guitars.json"


class GuitarStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or _config_path()
        self.guitars: list[Guitar] = []
        self.active = ""  # id of the guitar in use, "" = none
        self.load()

    def load(self) -> None:
        try:
            data = json.loads(self.path.read_text())
        except (OSError, ValueError):
            return
        self.guitars = [Guitar.from_dict(g) for g in data.get("guitars", [])
                        if isinstance(g, dict)]
        self.active = str(data.get("active", ""))

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {"active": self.active, "guitars": [asdict(g) for g in self.guitars]}
        self.path.write_text(json.dumps(data, indent=1, ensure_ascii=False))

    def get(self, guitar_id: str) -> Guitar | None:
        return next((g for g in self.guitars if g.id == guitar_id), None)

    @property
    def current(self) -> Guitar | None:
        return self.get(self.active)

    def put(self, guitar: Guitar) -> None:
        index = next((i for i, g in enumerate(self.guitars) if g.id == guitar.id), None)
        if index is None:
            self.guitars.append(guitar)
        else:
            self.guitars[index] = guitar
        self.save()

    def remove(self, guitar_id: str) -> None:
        guitar = self.get(guitar_id)
        if guitar is not None and guitar.image and Path(guitar.image).parent == images_dir():
            Path(guitar.image).unlink(missing_ok=True)
        self.guitars = [g for g in self.guitars if g.id != guitar_id]
        if self.active == guitar_id:
            self.active = ""
        self.save()

    def use(self, guitar_id: str) -> None:
        self.active = guitar_id if self.get(guitar_id) else ""
        self.save()


def context_text(guitar: Guitar) -> str:
    """The guitar as the AI receives it (only the fields the user filled)."""
    rows = []
    for name, label in FIELDS:
        value = getattr(guitar, name)
        if not value or name == "serial":
            continue
        doubt = guitar.evidence.get(name) in ("deducido", "probable")
        rows.append(f"{label}: {value}" + (f" ({guitar.evidence[name]})" if doubt else ""))
    return f"Guitarra en uso: {guitar.title}. " + "; ".join(rows)


SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": [*SPEC_FIELDS, "image_url", "confidence", "explanation"],
    "properties": {**{name: {"type": "object", "additionalProperties": False,
                             "required": ["value", "evidence"],
                             "properties": {"value": {"type": "string"},
                                            "evidence": {"type": "string",
                                                         "enum": [*EVIDENCE, ""]}}}
                      for name in SPEC_FIELDS},
                   "image_url": {"type": "string"},
                   "confidence": {"type": "string", "enum": ["alta", "media", "baja"]},
                   "explanation": {"type": "string"}},
}

SYSTEM = """You identify electric guitars for a guitar-effects editor. Answer in Spanish.
Work in this order and use web search:
1. The maker's official spec sheet for the exact model code (with the colour code if given):
   woods, neck, fretboard, inlays, scale, radius, frets, pickups, controls, bridge. These are
   evidence "oficial". Keep each part in its field: inlay material is not the neck wood.
2. Country of manufacture: retailers' listings of that exact model code stating "Made in",
   cross-checked with the serial scheme. Two independent sources = "verificado". The usual
   country of a series is not evidence (one model is often built in several countries).
3. Serial number: decode it with serial-number guides; a year or factory read from it is
   "deducido". A factory attributed only by community guides is "probable".
Each field holds only the data, short and plain (e.g. "Super 58 (H), pasiva, Alnico"),
with its evidence level; write "No tiene" for a part the guitar does not have; keep the model
name as the user wrote it; leave value and evidence empty when you cannot support it, never
invent. In "explanation" say, briefly, how each uncertain field was established, any
disagreement between sources (do not hide it), what the user should check on the instrument,
and list the source URLs. "image_url": a direct link to an image file (jpg/png/webp) of this
model and colour, the whole guitar seen from the front, preferably from the maker's site; ""
if none. "confidence" is "alta" only when the specs are "oficial" and nothing
important is only "probable"."""


def identify(guitar: Guitar, provider: str = "", model: str = "") -> tuple[Guitar, str, str]:
    """Suggested specs for ``guitar`` (brand, model, serial...): (guitar, confidence, why).

    Only empty fields are filled, so whatever the user typed stays."""
    known = "\n".join(f"{label}: {getattr(guitar, name)}" for name, label in FIELDS
                      if getattr(guitar, name))
    backend = tone_ai.make_backend(provider, model)
    data = backend.run(f"Identifica esta guitarra:\n{known}", SCHEMA, SYSTEM, web=True)
    suggested = Guitar.from_dict(asdict(guitar))
    for name in SPEC_FIELDS:
        item = data.get(name)
        if not isinstance(item, dict):
            continue
        value = str(item.get("value") or "").strip()
        if value and not getattr(suggested, name):
            setattr(suggested, name, value)
            evidence = str(item.get("evidence") or "")
            if evidence in EVIDENCE:
                suggested.evidence[name] = evidence
    why = str(data.get("explanation", ""))
    suggested.report = why
    url = str(data.get("image_url") or "")
    if url and not suggested.image:
        with contextlib.suppress(OSError, ValueError):
            suggested.image = str(download_image(url, suggested.id))
    return suggested, str(data.get("confidence", "")), why
