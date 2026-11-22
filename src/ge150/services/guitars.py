"""The user's guitars: what is plugged into the pedal also shapes the sound.

Each guitar is a plain record (brand, model, year, serial, woods, pickups, electronics,
strings, tuning...) kept in ``$XDG_CONFIG_HOME/ge150/guitars.json`` with the one in use.
:func:`identify` asks Claude or Codex (no tools) what a brand + model + serial number
probably is, as suggestions the user reviews before saving; :func:`context_text` is what the
AI assistant receives about the guitar in use.
"""

from __future__ import annotations

import json
import os
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

    @property
    def title(self) -> str:
        name = " ".join(p for p in (self.brand, self.model) if p) or "Guitarra sin nombre"
        return f"{name} ({self.year})" if self.year else name

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Guitar:
        known = {f.name for f in fields(cls)}
        return cls(**{k: str(v) for k, v in data.items() if k in known})


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
        self.guitars = [g for g in self.guitars if g.id != guitar_id]
        if self.active == guitar_id:
            self.active = ""
        self.save()

    def use(self, guitar_id: str) -> None:
        self.active = guitar_id if self.get(guitar_id) else ""
        self.save()


def context_text(guitar: Guitar) -> str:
    """The guitar as the AI receives it (only the fields the user filled)."""
    rows = [f"{label}: {getattr(guitar, name)}" for name, label in FIELDS
            if getattr(guitar, name) and name != "serial"]
    return f"Guitarra en uso: {guitar.title}. " + "; ".join(rows)


SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": [*SPEC_FIELDS, "confidence", "explanation"],
    "properties": {**{name: {"type": "string"} for name in SPEC_FIELDS},
                   "confidence": {"type": "string", "enum": ["alta", "media", "baja"]},
                   "explanation": {"type": "string"}},
}

SYSTEM = ("You identify electric guitars for a guitar-effects editor. Use your knowledge of "
          "manufacturers' serial-number schemes and their catalogues. Answer in Spanish. "
          "Fill each field with the factory specification of that exact instrument (year, "
          "factory, woods, scale, each pickup with its model, controls, bridge). Search the web "
          "(the maker's spec sheets, serial decoders) to confirm the exact series. Each field "
          "holds only the data, short and plain (e.g. 'Ibanez Super 58, humbucker pasivo, "
          "alnico'): no doubts, sources or comments there, those go in 'explanation'. Write "
          "'No tiene' for a part the guitar does not have (e.g. a middle pickup on a two-pickup "
          "guitar). Keep the model name as the user wrote it. Leave a field empty when you "
          "cannot confirm it, never invent. Say in 'explanation' how you decoded "
          "the serial and what the user should check.")


def identify(guitar: Guitar, provider: str = "", model: str = "") -> tuple[Guitar, str, str]:
    """Suggested specs for ``guitar`` (brand, model, serial...): (guitar, confidence, why).

    Only empty fields are filled, so whatever the user typed stays."""
    known = "\n".join(f"{label}: {getattr(guitar, name)}" for name, label in FIELDS
                      if getattr(guitar, name))
    backend = tone_ai.make_backend(provider, model)
    data = backend.run(f"Identifica esta guitarra:\n{known}", SCHEMA, SYSTEM, web=True)
    suggested = Guitar.from_dict(asdict(guitar))
    for name in SPEC_FIELDS:
        value = str(data.get(name) or "").strip()
        if value and not getattr(suggested, name):
            setattr(suggested, name, value)
    return suggested, str(data.get("confidence", "")), str(data.get("explanation", ""))
